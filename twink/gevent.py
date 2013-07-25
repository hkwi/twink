from __future__ import absolute_import
import logging
import StringIO
from twink import *
from gevent import spawn
from gevent.event import Event, AsyncResult
from gevent.queue import Queue
from gevent.server import StreamServer, DatagramServer
from gevent.socket import error, EBADF

class StreamChannel(Channel):
	socket = None
	
	def __init__(self, *args, **kwargs):
		# put the vars required for __repr__ before calling super()
		self.socket = kwargs["socket"]
		self.sockname = self.socket.getsockname()
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
		return "tcp %s:%d" % self.sockname

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
		return "udp %s:%s" % self.address


class ServerHandler(object):
	def __init__(self, *args, **kwargs):
		self.message_handler = kwargs.get("message_handler", easy_message_handler)
		self.channel_cls = kwargs.get("channel_cls", StreamChannel)
		self.channel_opts = kwargs.get("channel_opts", {})


class StreamHandler(ServerHandler):
	def __call__(self, socket, address):
		assert issubclass(self.channel_cls, StreamChannel)
		channel = self.channel_cls(socket=socket, **self.channel_opts)
		
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
		except:
			logging.error("message_handler failed", exc_info=True)
			channel.close()


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
			channel = self.channel_cls(server=self, address=address, **self.channel_opts)
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
	
	def prepare(self):
		xid = hms_xid()
		self.results[xid] = result = AsyncResult()
		return (xid, result)
	
	def simple_request(self, channel, ofp_type):
		(xid, result) = self.prepare()
		channel.send(ofp_header_only(ofp_type, version=channel.version, xid=xid), self)
		return result.get()
	
	def close(self):
		for k,v in self.results.items():
			v.set_exception(error(EBADF, "connection closed"))
		self.results = {}
	
	def __call__(self, message, channel):
		assert isinstance(channel, SyncChannel)
		(version, oftype, message_len, xid) = parse_ofp_header(message)
		if xid in self.results:
			if oftype == 1:
				self.results[xid].set_exception(OpenflowError(message))
			else:
				self.results[xid].set(message)
		if channel.callback:
			try:
				return channel.callback(message, channel)
			except CallbackDeadError:
				pass # This should not happen


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
			self.send(struct.pack("!BBHIHH", self.version, 16, 12+len(payload), xid, stype, 0)+payload, self._sync) # OFPT_STATS_REQUEST=16 (v1.0)
		else:
			self.send(struct.pack("!BBHIHH4x", self.version, 18, 12+len(payload), xid, stype, 0)+payload, self._sync) # OFPT_STATS_REQUEST=18 (v1.1, v1.2)
		return result.get()
	
	def barrier(self):
		if self.version==1:
			return self._sync.simple_request(self, 18) # OFPT_BARRIER_REQUEST=18 (v1.0)
		else:
			return self._sync.simple_request(self, 20) # OFPT_BARRIER_REQUEST=20 (v1.1, v1.2, v1.3)
	
	def queue_get_config(self, port):
		(xid, result) = self._sync.prepare()
		if self.version==1:
			self.send(struct.pack("!BBHIH2x", self.version, 20, 12, xid, port), self._sync) # OFPT_QUEUE_GET_CONFIG_REQUEST=20 (v1.0)
		else:
			self.send(struct.pack("!BBHII4x", self.version, 22, 16, xid, port), self._sync) # OFPT_QUEUE_GET_CONFIG_REQUEST=22 (v1.1, v1.2, v1.3)
		return result.get()
	
	def role(self, role, generation_id):
		if self.version in (1,2):
			raise NotImplemented("openflow version compatibility")
		(xid, result) = self._sync.prepare()
		self.send(struct.pack("!BBHII4xQ", self.version, 24, 24, xid, role, generation_id), self._sync) # OFPT_ROLE_REQUEST=24 (v1.2, v1.3)
		return result.get()
	
	def get_async(self):
		if self.version!=4:
			raise NotImplemented("openflow version compatibility")
		return self._sync.simple_request(self, 26) # OFPT_GET_ASYNC_REQUEST=26 (v1.3)
	
	def close(self):
		super(SyncChannel, self).close()
		self._sync.close()


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
			assert not hit
			ports.append(port)
		elif reason==1: # DELETE
			assert hit
			ports.remove(hit[0])
		elif reason==2: # MODIFY
			assert hit
			ports.remove(hit[0])
			ports.append(port)
		else:
			assert False, "unknown reason %d" % reason
		self.ports = ports
	
	def __call__(self, message, channel):
		assert isinstance(channel, PortMonitorChannel)
		
		ofp_port = "!H6s16sIIIIII" # ofp_port v1.0
		if channel.version != 1:
			ofp_port = "!I4x6s2x16sIIIIIIII"
		
		(version, oftype, length, xid) = parse_ofp_header(message)
		if xid in self.multi and oftype==19: # MULTIPART_REPLY
			assert channel.version == 4
			(mptype, flags) = struct.unpack_from("!HH4x", message, offset=8)
			if mptype==13:
				ports = self.multi[xid]
				offset = 16
				while offset < length:
					ports.append(struct.unpack(message, ofp_port, offset=offset))
					offset += struct.calcsize(ofp_port)
				
				if flags&1:
					self.ports = ports
					self.ports_init.set()
					del(self.multi[xid])
		elif oftype==6 and channel.version != 4: # FEATURES_REPLY
			fmt = "!BBHIQIB3x"
			assert struct.calcsize(fmt) % 8 == 0
			offset = struct.calcsize(fmt+"II")
			ports = []
			while offset < length:
				ports.append(struct.unpack_from(ofp_port, message, offset=offset))
				offset += struct.calcsize(ofp_port)
			self.ports = ports
			self.ports_init.set()
		elif oftype==12: # PORT_STATUS
			p = struct.unpack_from("!B7x"+ofp_port[1:], message, offset=8)
			self.update_port(p[0], p[1:])


class PortMonitorChannel(ControllerChannel):
	def __init__(self, *args, **kwargs):
		super(PortMonitorChannel, self).__init__(*args, **kwargs)
		self._port_monitor = PortMonitorContext()
	
	@property
	def ports(self):
		return self._port_monitor.get_ports(self)
	
	def port_index(self):
		if self.version==1:
			return '''port_no hw_addr name
				config state
				curr advertised supported peer'''.split()
		else:
			return '''port_no hw_addr name
				config state
				curr advertised supported peer
				curr_speed max_speed'''.split()
	
	def on_message(self, message):
		'''
		Interface for inner connection side
		'''
		self._port_monitor(message, self)
		return super(PortMonitorChannel, self).on_message(message)


def serve_forever(*servers, **opts):
	for server in servers:
		server.start()
	try:
		Event().wait()
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
	tcpserv = StreamServer(address, handle=StreamHandler(
		channel_cls=type("SChannel", (StreamChannel, PortMonitorChannel, SyncChannel, LoggingChannel), {}),
		channel_opts = {"accept_versions": [1, 4]},
		message_handler=message_handler))
	udpserv = OpenflowDatagramServer(address,
		channel_cls=type("DChannel", (DatagramChannel, PortMonitorChannel, SyncChannel, LoggingChannel), {}),
		channel_opts = {"accept_versions": [1, 4]},
		message_handler=message_handler)
	serve_forever(tcpserv, udpserv)
