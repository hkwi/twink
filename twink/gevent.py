from __future__ import absolute_import
from . import *
import gevent.event
import gevent.server
import gevent.pool
import gevent.monkey
import gevent.subprocess


class ParallelMixin(ParallelChannel):
	spawn = gevent.spawn
	subprocess = gevent.subprocess
	event = gevent.event.Event
	
	def jackin_server(self, path):
		s = gevent.socket.socket(gevent.socket.AF_UNIX, gevent.socket.SOCK_STREAM)
		s.bind(path)
		s.listen(50)
		serv = ChannelStreamServer(s, spawn=50)
		serv.channel_cls = type("JackinChannel",(AutoEchoChannel, LoggingChannel, JackinChildChannel),{
			"accept_versions":[self.version,],
			"parent": self })
		return serv.start, serv.stop, serv.address
	
	def monitor_server(self, path):
		s = gevent.socket.socket(gevent.socket.AF_UNIX, gevent.socket.SOCK_STREAM)
		s.bind(path)
		s.listen(50)
		serv = ChannelStreamServer(s, spawn=50)
		serv.channel_cls = type("MonitorChannel",(AutoEchoChannel, LoggingChannel, ChildChannel),{
			"accept_versions":[self.version,],
			"parent": self })
		return serv.start, serv.stop, serv.address
	
	def temp_server(self):
		serv = ChannelStreamServer(("127.0.0.1",0), spawn=50)
		serv.channel_cls = type("JackinChannel",(AutoEchoChannel, LoggingChannel, JackinChildChannel),{
			"accept_versions":[self.version,],
			"parent": self })
		serv.start() # serv.address will be replaced
		return serv.start, serv.stop, serv.address


# fortunatelly, gevent server handle is a duck.
class ChannelStreamServer(gevent.server.StreamServer):
	channel_cls = None # we must be override
	def __init__(self, *args, **kwargs):
		super(ChannelStreamServer, self).__init__(*args, **kwargs)
		self.channels = set()
	
	def handle(self, *args):
		socket, client_address = args
		ch = self.channel_cls(
			socket=socket,
			remote_address=client_address,
			local_address=self.address)
		ch.messages = read_message(socket.recv)
		self.channels.add(ch)
		ch.start()
		ch.loop()
		if not ch.closed:
			ch.close()
		self.channels.remove(ch)
	
	def close(self):
		for ch in tuple(self.channels):
			ch.close()
		super(ChannelStreamServer, self).close()


class ChannelDatagramServer(gevent.server.DatagramServer):
	channel_cls = None # we must be override
	def __init__(self, *args, **kwargs):
		super(ChannelDatagramServer, self).__init__(*args, **kwargs)
		self.channels = set()
	
	def handle(self, *args):
		data, client_address = args
		
		ch = None
		for tmp in self.channels:
			if tmp.remote_address == client_address:
				ch = tmp
				break
		
		if ch is None:
			ch = self.channel_cls(
				sendto=self.sendto,
				remote_address=client_address,
				local_address=self.address)
			self.channels.add(ch)
			ch.start()
		
		f = StringIO.StringIO(data)
		ch.messages = read_message(f.read)
		try:
			ch.loop()
			if f.tell() < len(data):
				warnings.warn("%d bytes not consumed" % (len(data)-f.tell()))
		except Exception,e:
			logging.error(str(e), exc_info=True)
		finally:
			ch.messages = None
			if ch.closed:
				self.channels.remove(ch)
	
	def close(self):
		for ch in tuple(self.channels):
			ch.close()
		super(ChannelDatagramServer, self).close()

def serve_forever(*servers, **opts):
	for server in servers:
		server.start()
	try:
		opts.get("main", gevent.event.Event()).wait()
	finally:
		stop_timeout=opts.get("stop_timeout")
		for th in [gevent.spawn(x.stop, timeout=stop_timeout) for x in servers]:
			th.join()


if __name__=="__main__":
	logging.basicConfig(level=logging.DEBUG)
	pool = gevent.pool.Pool(50)
	# use spawn=pool or spawn=int kwarg to make sure Channel.close called.
	tcpserv = ChannelStreamServer(("0.0.0.0", 6653), spawn=pool)
	tcpserv.channel_cls = type("TcpChannel", (
		BranchingMixin, SyncChannel, MonitorChannel, JackinChannel,
		ControllerChannel,
		AutoEchoChannel,
		LoggingChannel,
		HandleInSpawnChannel), {"accept_versions":[4,]})
	udpserv = ChannelDatagramServer(("0.0.0.0", 6653), spawn=pool)
	udpserv.channel_cls = type("UdpChannel", (
		BranchingMixin, SyncChannel, MonitorChannel, JackinChannel,
		ControllerChannel,
		AutoEchoChannel,
		LoggingChannel,
		HandleInSpawnChannel), {"accept_versions":[4,]})
	
	serve_forever(tcpserv, udpserv)

