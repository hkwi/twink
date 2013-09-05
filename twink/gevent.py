from __future__ import absolute_import
import logging
import StringIO
import os
import os.path
from collections import namedtuple
from twink import *
from gevent import spawn
from gevent.event import Event, AsyncResult
from gevent.queue import Queue
from gevent.server import StreamServer, DatagramServer
from gevent.socket import socket, AF_UNIX, AF_INET, AF_INET6, SOCK_STREAM, error, EBADF

class StreamChannel(Channel):
	socket = None
	
	def __init__(self, *args, **kwargs):
		# put the vars required for __repr__ before calling super()
		self.socket = kwargs["socket"]
		self.sockfamily = self.socket.family
		self.sockname = self.socket.getsockname()
		self.peername = self.socket.getpeername()
		super(StreamChannel, self).__init__(*args, **kwargs)
	
	def direct_send(self, message):
		self.socket.send(message)
	
	@property
	def closed(self):
		return self.socket.closed
	
	def close(self):
		super(StreamChannel, self).close()
		return self.socket.close()
	
	def __repr__(self):
		if self.sockfamily in (AF_INET, AF_INET6):
			return "tcp %s:%d-%s:%d" % (self.sockname[0:2]+self.peername[0:2])
		elif self.sockfamily == AF_UNIX:
			return "unix %s-%x" % (self.unix_path, id(self))
		else:
			return repr(self.socket)

class DatagramChannel(Channel):
	server = None
	address = None
	
	def __init__(self, *args, **kwargs):
		# put the vars required for __repr__ before calling super()
		self.server = kwargs["server"]
		self.address = kwargs["address"]
		super(DatagramChannel, self).__init__(*args, **kwargs)
	
	def direct_send(self, message):
		self.server.sendto(message, self.address)
	
	def close(self):
		super(DatagramChannel, self).close()
		del(self.server.channels[self.address])
	
	def __repr__(self):
		if self.server.socket.family in (AF_INET, AF_INET6):
			return "udp %s:%d-%s:%d" % self.sockinfo
		elif self.socket.family == AF_UNIX:
			return "unix %s-%x" % (self.unix_path, id(self))
		else:
			return repr(self.socket)


class StreamClient(object):
	def __init__(self, *args, **kwargs):
		self.message_handler = kwargs.get("message_handler", easy_message_handler)
		self.channel_cls = kwargs.get("channel_cls", StreamChannel)
		self.socket = kwargs["socket"]
	
	def run(self):
		socket = self.socket
		assert issubclass(self.channel_cls, StreamChannel)
		channel = self.channel_cls(socket=socket)
		
		channel.send(hello(channel.accept_versions), self.message_handler)
		
		try:
			while not socket.closed:
				message = read_message(socket.recv)
				if message:
					spawn(channel.on_message, message)
				else:
					break
		finally:
			channel.close()
			socket.close()
	
	def stop(self):
		self.socket.close()
	
	def start(self):
		th = spawn(self.run)
		try:
			Event().wait()
		finally:
			spawn(self.stop)
			th.join()


class ServerHandler(object):
	def __init__(self, *args, **kwargs):
		self.message_handler = kwargs.get("message_handler", easy_message_handler)
		self.channel_cls = kwargs.get("channel_cls", StreamChannel)


class StreamHandler(ServerHandler):
	def __call__(self, socket, address):
		assert issubclass(self.channel_cls, StreamChannel)
		try:
			channel = self.channel_cls(socket=socket)
		except ChannelClose as e:
			logging.info(e)
			socket.close()
			return
		except:
			logging.info("unhandled error", exc_info=True)
			socket.close()
			return
		
		channel.send(hello(channel.accept_versions), self.message_handler)
		
		try:
			while not socket.closed:
				message = read_message(socket.recv)
				if message:
					spawn(self.channel_message, channel, message)
				else:
					break
		finally:
			channel.close()
			socket.close()

	def channel_message(self, channel, message):
		try:
			channel.on_message(message)
		except ChannelClose as e:
			logging.info(e)
			channel.close()
			return
		except:
			logging.info("message_handler failed", exc_info=True)
			channel.close()
			return


class OpenflowDatagramServer(DatagramServer, ServerHandler):
	def __init__(self, *args, **kwargs):
		dgram_kwargs = dict([x for x in kwargs.items() if x[0] in ["handle", "spawn"]])
		DatagramServer.__init__(self, args[0], **dgram_kwargs)
		ServerHandler.__init__(self, *args, **kwargs)
		self.channels = {}
	
	def handle(self, data, address):
		# fetch for pseudo channel that holds connection values (datapath, etc.)
		channel = self.channels.get(address)
		if channel is None:
			assert issubclass(self.channel_cls, DatagramChannel)
			channel = self.channel_cls(server=self, address=address)
			self.channels[address] = channel
			
			channel.send(hello(channel.accept_versions), self.message_handler)
		
		fp = StringIO.StringIO(data)
		try:
			while True:
				message = read_message(fp.read)
				if message:
					spawn(self.channel_message, channel, message)
				else:
					break
		finally:
			fp.close()
	
	def channel_message(self, channel, message):
		try:
			channel.on_message(message)
		except:
			logging.error("message_handler failed", exc_info=True)
			channel.close()

class SyncContext(object):
	def __init__(self):
		self.results = {}
	
	def prepare(self, xid=None):
		if xid is None:
			xid = hms_xid()
		self.results[xid] = result = AsyncResult()
		return (xid, result)
	
	def simple_request(self, channel, ofp_type):
		(xid, result) = self.prepare()
		channel.send(ofp_header_only(ofp_type, version=channel.version, xid=xid), self)
		try:
			return result.get()
		finally:
			self.release(xid)
	
	def close(self):
		for k,v in self.results.items():
			v.set_exception(error(EBADF, "connection closed"))
		self.results = {}
	
	def release(self, xid):
		if not self.results[xid].ready():
			self.results[xid].set(None)
		del(self.results[xid])
	
	def __call__(self, message, channel):
		assert isinstance(channel, SyncChannel)
		(version, oftype, message_len, xid) = parse_ofp_header(message)
		if xid in self.results:
			if oftype == 1:
				self.results[xid].set_exception(OpenflowError(message))
			else:
				if self.results[xid].ready():
					message = self.results[xid].get() + message
				self.results[xid].set(message)


class SyncChannel(ControllerChannel):
	def __init__(self, *args, **kwargs):
		super(SyncChannel, self).__init__(*args, **kwargs)
		self._sync = SyncContext()
	
	def echo(self):
		return self._sync.simple_request(self, 2)
	
	def feature(self):
		return self._sync.simple_request(self, 5)
	
	def get_config(self):
		return self._sync.simple_request(self, 7)
	
	def stats(self, stype, payload):
		if self.version==4:
			raise NotImplemented("openflow version compatibility")
		(xid, result) = self._sync.prepare()
		if self.version==1:
			self.send(struct.pack("!BBHIHH", self.version, 16, 12+len(payload), xid, stype, 0)+payload, None) # OFPT_STATS_REQUEST=16 (v1.0)
		else:
			self.send(struct.pack("!BBHIHH4x", self.version, 18, 12+len(payload), xid, stype, 0)+payload, None) # OFPT_STATS_REQUEST=18 (v1.1, v1.2)
		return result.get()
	
	def barrier(self):
		if self.version==1:
			return self._sync.simple_request(self, 18) # OFPT_BARRIER_REQUEST=18 (v1.0)
		else:
			return self._sync.simple_request(self, 20) # OFPT_BARRIER_REQUEST=20 (v1.1, v1.2, v1.3)
	
	def queue_get_config(self, port):
		(xid, result) = self._sync.prepare()
		if self.version==1:
			self.send(struct.pack("!BBHIH2x", self.version, 20, 12, xid, port), None) # OFPT_QUEUE_GET_CONFIG_REQUEST=20 (v1.0)
		else:
			self.send(struct.pack("!BBHII4x", self.version, 22, 16, xid, port), None) # OFPT_QUEUE_GET_CONFIG_REQUEST=22 (v1.1, v1.2, v1.3)
		return result.get()
	
	def role(self, role, generation_id):
		if self.version in (1,2):
			raise NotImplemented("openflow version compatibility")
		(xid, result) = self._sync.prepare()
		self.send(struct.pack("!BBHII4xQ", self.version, 24, 24, xid, role, generation_id), None) # OFPT_ROLE_REQUEST=24 (v1.2, v1.3)
		return result.get()
	
	def get_async(self):
		if self.version!=4:
			raise NotImplemented("openflow version compatibility")
		return self._sync.simple_request(self, 26) # OFPT_GET_ASYNC_REQUEST=26 (v1.3)
	
	def single(self, message):
		return self.multi([message,]).pop()
	
	def multi(self, messages):
		prepared = []
		for message in messages:
			(version, oftype, length, xid) = parse_ofp_header(message)
			prepared.append(self._sync.prepare(xid=xid))
			self.send(message, None)
		self.barrier()
		for (xid, result) in prepared:
			self._sync.release(xid)
		return [result.get() for (xid, result) in prepared]
	
	def close(self):
		super(SyncChannel, self).close()
		self._sync.close()
	
	def on_message(self, message):
		self._sync(message, self)
		return super(SyncChannel, self).on_message(message)


class PortMonitorContext(object):
	def __init__(self):
		self.ports_init = Event()
		self.ports = []
		self.multi = {}
	
	def get_ports(self, channel):
		if not self.ports_init.is_set():
			if channel.version == 4:
				xid = hms_xid()
				self.multi[xid] = []
				channel.send(struct.pack("!BBHIHH4x", channel.version, 
					18, # MULTIPART_REQUEST (v1.3)
					16, # struct.calcsize(fmt)==16
					xid, 
					13, # PORT_DESC
					0, # no REQ_MORE
					), None)
			else:
				channel.send(ofp_header_only(5, version=channel.version), None) # FEATURES_REQUEST
			self.ports_init.wait()
		return self.ports
	
	def update_port(self, reason, port):
		ports = self.ports
		hit = [x for x in ports if x[0]==port[0]] # check with port_no(0)
		if reason==0: # ADD
			if self.ports_init.is_set():
				assert not hit
			ports.append(port)
		elif reason==1: # DELETE
			if self.ports_init.is_set():
				assert hit
			if hit:
				assert len(hit) == 1
				ports.remove(hit.pop())
		elif reason==2: # MODIFY
			if self.ports_init.is_set():
				assert hit
			if hit:
				assert len(hit) == 1
				ports.remove(hit.pop())
			ports.append(port)
		else:
			assert False, "unknown reason %d" % reason
		self.ports = ports
	
	def __call__(self, message, channel):
		assert isinstance(channel, PortMonitorChannel)
		
		ofp_port = "!H6s16sIIIIII" # ofp_port v1.0
		ofp_port_names = '''port_no hw_addr name
			config state
			curr advertised supported peer'''
		if channel.version != 1:
			ofp_port = "!I4x6s2x16sIIIIIIII"
			ofp_port_names = '''port_no hw_addr name
				config state
				curr advertised supported peer
				curr_speed max_speed'''
		
		(version, oftype, length, xid) = parse_ofp_header(message)
		if xid in self.multi and oftype==19: # MULTIPART_REPLY
			assert channel.version == 4
			(mptype, flags) = struct.unpack_from("!HH4x", message, offset=8)
			if mptype==13:
				ports = self.multi[xid]
				offset = 16
				while offset < length:
					port = list(struct.unpack_from(ofp_port, message, offset=offset))
					port[2] = port[2].partition('\0')[0]
					ports.append(namedtuple("ofp_port", ofp_port_names)(*port))
					offset += struct.calcsize(ofp_port)
				
				if not flags&1:
					self.ports = ports
					self.ports_init.set()
					del(self.multi[xid])
		elif oftype==6 and channel.version != 4: # FEATURES_REPLY
			fmt = "!BBHIQIB3x"
			assert struct.calcsize(fmt) % 8 == 0
			offset = struct.calcsize(fmt+"II")
			ports = []
			while offset < length:
				port = list(struct.unpack_from(ofp_port, message, offset=offset))
				port[2] = port[2].partition('\0')[0]
				ports.append(namedtuple("ofp_port", ofp_port_names)(*port))
				offset += struct.calcsize(ofp_port)
			self.ports = ports
			self.ports_init.set()
		elif oftype==12: # PORT_STATUS
			p = struct.unpack_from("!B7x"+ofp_port[1:], message, offset=8)
			reason = p[0]
			port = list(p[1:])
			port[2] = port[2].partition('\0')[0]
			self.update_port(reason, namedtuple("ofp_port", ofp_port_names)(*port))


class PortMonitorChannel(ControllerChannel):
	''' Monitors openflow switch port changes. '''
	def __init__(self, *args, **kwargs):
		super(PortMonitorChannel, self).__init__(*args, **kwargs)
		self._port_monitor = PortMonitorContext()
	
	@property
	def ports(self):
		return self._port_monitor.get_ports(self)
	
	def on_message(self, message):
		'''
		Interface for inner connection side
		'''
		self._port_monitor(message, self)
		return super(PortMonitorChannel, self).on_message(message)


class ProxyChannel(Channel):
	'''accepts controller connection and proxies it to upstream switch'''
	def to_downstream(self, message, channel):
		self.send(message, None)
	
	def send(self, message, message_handler):
		super(ProxyChannel, self).send(message, message_handler)
		self.direct_send(message)
	
	def on_message(self, message):
		super(ProxyChannel, self).on_message(message)
		if ord(message[1]) != 0: # no HELLO
			return self.upstream.send(message, self.to_downstream)


class PassiveChannel(Channel):
	'''accepts monitor controller connection and proxies down messages from upstream switch'''
	hello = False
	def to_downstream(self, message, channel):
		if self.hello:
			self.send(message, None)
	
	def send(self, message, message_handler):
		super(PassiveChannel, self).send(message, message_handler)
		self.direct_send(message)
	
	def on_message(self, message):
		(version, oftype, length, xid) = parse_ofp_header(message)
		if oftype==0:
			self.hello = True
		
		if super(PassiveChannel, self).on_message(message):
			return True
		# Clients are not allowed to send requests to upstream
		if oftype!=0:
			self.send(struct.pack("!BBHIHH", self.version, 1, 12, xid, 1, 5), None)
			self.close()
	
	@property
	def unix_path(self):
		return self.context.proxy_path


class ContextChannel(Channel):
	@property
	def unix_path(self):
		return self.context.proxy_path


class RegisterBackChannel(ContextChannel):
	def __init__(self, *args, **kwargs):
		self.registry.append(self)
		super(RegisterBackChannel, self).__init__(*args, **kwargs)
	
	def close(self):
		if self in self.registry:
			self.registry.remove(self)
		super(RegisterBackChannel, self).close()
	
	@property
	def unix_path(self):
		return self.context.proxy_path


class UnixContext(object):
	channel_parents = (StreamChannel,)
	suffix = "sock"
	server = None
	proxy_path = None
	proxy_sock = None
	
	def __init__(self, parent, **kwargs):
		self.parent = parent
		try:
			self.backlog = parent.backlog
		except AttributeError:
			self.backlog = 50
		
		try:
			self.socket_dir = parent.socket_dir
		except AttributeError:
			self.socket_dir = None
	
	def channel_args(self):
		return {"accept_versions": [self.parent.version,]}
	
	def start_proxy(self):
		self.proxy_sock = proxy_sock = socket(AF_UNIX, SOCK_STREAM)
		self.proxy_path = self.sync()
		proxy_sock.bind(self.proxy_path)
		proxy_sock.listen(self.backlog)
		self.server = serv = StreamServer(proxy_sock, handle=StreamHandler(
			channel_cls=type("UnixChannel", self.channel_parents, self.channel_args())),
			spawn=100)
		serv.start()
	
	def socket_path(self, path):
		if self.socket_dir:
			path = os.path.join(self.socket_dir, path)
		return os.path.abspath(path)
	
	def sync(self):
		# PID is used to escape the conflict in case accidentally multiple connection was opened
		# for the same datapath in different process
		old = self.socket_path("unknown-%x.%s" % (os.getpid(), self.suffix))
		if self.parent.datapath:
			new = self.socket_path("%x-%x.%s" % (self.parent.datapath, os.getpid(), self.suffix))
			if self.proxy_path and self.proxy_path == old:
				os.rename(old, new)
				self.proxy_path = new
			return new
		return old
	
	def close(self):
		if self.server:
			self.server.stop() # XXX: this does not close jackin connections
		if self.proxy_sock:
			self.proxy_sock.close()
		if self.proxy_path:
			os.remove(self.proxy_path)
			self.proxy_path = None


class JackinContext(UnixContext):
	channel_parents = (StreamChannel, ProxyChannel, ContextChannel, LoggingChannel)
	suffix = "jackin"
	
	def channel_args(self):
		return {
			"accept_versions": [self.parent.version,],
			"context":self,
			"upstream":self.parent
			}


class JackinChannel(Channel):
	def __init__(self, *args, **kwargs):
		super(JackinChannel, self).__init__(*args, **kwargs)
		self._jackin = JackinContext(self, **kwargs)
	
	def close(self):
		self._jackin.close()
		super(JackinChannel, self).close()
	
	def on_message(self, message):
		if super(JackinChannel, self).on_message(message):
			return True
		
		(version, oftype, length, xid) = parse_ofp_header(message)
		if oftype==0: # HELLO
			self._jackin.start_proxy()
		elif oftype==6: # FEATURE
			self._jackin.sync()


class MonitorContext(UnixContext):
	channel_parents = (StreamChannel, PassiveChannel, RegisterBackChannel, ContextChannel, LoggingChannel)
	suffix = "monitor"
	
	def __init__(self, parent, **kwargs):
		super(MonitorContext, self).__init__(parent, **kwargs)
		self.monitor_channels = []
	
	def channel_args(self):
		return {
			"accept_versions": [self.parent.version,],
			"context":self,
			"registry":self.monitor_channels
			}
	
	def notify(self, message):
		for channel in self.monitor_channels:
			channel.send(message, None)


class MonitorChannel(Channel):
	def __init__(self, *args, **kwargs):
		super(MonitorChannel, self).__init__(*args, **kwargs)
		self._monitor = MonitorContext(self, **kwargs)
	
	def close(self):
		self._monitor.close()
		super(MonitorChannel, self).close()
	
	def on_message(self, message):
		self._monitor.notify(message)
		if super(MonitorChannel, self).on_message(message):
			return True
		
		(version, oftype, length, xid) = parse_ofp_header(message)
		if oftype==0: # HELLO
			self._monitor.start_proxy()
		elif oftype==6: # FEATURE
			self._monitor.sync()
	
	@property
	def unix_path(self):
		return self._monitor.proxy_path


class PingingChannel(Channel):
	def __init__(self, *args, **kwargs):
		super(PingingChannel, self).__init__(*args, **kwargs)
		self._ping = Event()
		spawn(self.ping)
	
	def ping(self):
		while True:
			self._ping.wait(timeout=20)
			if self._ping.is_set():
				break
			else:
				self.send(struct.pack("!BBHI", self.version, 2, 8, hms_xid()), None)

	def close(self):
		self._ping.set()
		super(PingingChannel, self).close()

class ChannelClose(Exception):
	# to normally close the channel by raising an exception
	pass

def serve_forever(*servers, **opts):
	for server in servers:
		server.start()
	try:
		opts.get("main", Event()).wait()
	finally:
		stop_timeout=opts.get("stop_timeout")
		for th in [spawn(x.stop, timeout=stop_timeout) for x in servers]:
			th.join()

if __name__=="__main__":
	def message_handler(message, channel):
		(version, oftype, message_len, xid) = parse_ofp_header(message)
		ret = easy_message_handler(message, channel)
		if oftype==0:
			print "echo", binascii.b2a_hex(channel.echo())
			print "feature", binascii.b2a_hex(channel.feature())
			print "get_config", binascii.b2a_hex(channel.get_config())
			print "barrier", binascii.b2a_hex(channel.barrier())
			for port in channel.ports:
				print "port", port
				try:
					print "queue_get_config", binascii.b2a_hex(channel.queue_get_config(port[0]))
				except OpenflowError, e:
					print e
		return ret
	
	logging.basicConfig(level=logging.DEBUG)
	address = ("0.0.0.0", 6633)
	# use spawn=pool or spawn=int kwarg to make sure Channel.close called.
	tcpserv = StreamServer(address, handle=StreamHandler(
		channel_cls=type("SChannel",
			(StreamChannel, PortMonitorChannel, SyncChannel, PingingChannel, JackinChannel, MonitorChannel, LoggingChannel),
			{"accept_versions": [1, 4]}),
		message_handler=message_handler),
		spawn = 1000 )
	udpserv = OpenflowDatagramServer(address,
		channel_cls=type("DChannel",
			(DatagramChannel, PortMonitorChannel, SyncChannel, PingingChannel, JackinChannel, MonitorChannel, LoggingChannel),
			{"accept_versions": [1, 4]}),
		message_handler=message_handler,
		spawn = 1000 )
	serve_forever(tcpserv, udpserv)
