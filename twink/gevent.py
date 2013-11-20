from __future__ import absolute_import
from . import *
import gevent.event
import gevent.server
import gevent.pool
import gevent.monkey
import gevent.subprocess

class HandleInSpawnChannel(OpenflowChannel):
	def handle_proxy(self, handle):
		if handle:
			def intercept(message, channel):
				def closing_intercept(message, channel):
					try:
						handle(message, channel)
					except ChannelClose:
						channel.close()
					except:
						channel.close()
						raise
				gevent.spawn(closing_intercept, message, channel)
			return intercept
		return handle


class BranchingMixin(object):
	subprocess = gevent.subprocess
	event = gevent.event.Event
	
	def jackin_server(self, path, channels):
		s = gevent.socket.socket(gevent.socket.AF_UNIX, gevent.socket.SOCK_STREAM)
		s.bind(path)
		s.listen(50)
		serv = ChannelStreamServer(s, spawn=50)
		serv.channel_cls = type("JackinChannel",(AutoEchoChannel, LoggingChannel, JackinChildChannel),{
			"accept_versions":[self.version,],
			"parent": self,
			"channels": self.jackin_channels })
		return serv, serv.start, serv.stop, serv.address
	
	def monitor_server(self, path, channels):
		s = gevent.socket.socket(gevent.socket.AF_UNIX, gevent.socket.SOCK_STREAM)
		s.bind(path)
		s.listen(50)
		serv = ChannelStreamServer(s, spawn=50)
		serv.channel_cls = type("MonitorChannel",(AutoEchoChannel, LoggingChannel, ChildChannel),{
			"accept_versions":[self.version,],
			"parent": self,
			"channels": channels })
		return serv, serv.start, serv.stop, serv.address
	
	def temp_server(self, channels):
		serv = ChannelStreamServer(("127.0.0.1",0), spawn=50)
		serv.channel_cls = type("JackinChannel",(AutoEchoChannel, LoggingChannel, JackinChildChannel),{
			"accept_versions":[self.version,],
			"parent": self,
			"channels": self.jackin_channels })
		serv.start() # serv.address will be replaced
		return serv, serv.start, serv.stop, serv.address


# fortunatelly, gevent server handle is a duck.
class ChannelStreamServer(gevent.server.StreamServer):
	channel_cls = None
	def handle(self, *args):
		socket, client_address = args
		ch = self.channel_cls(
			socket=socket,
			remote_address=client_address,
			local_address=self.address)
		ch.messages = read_message(socket.recv)
		ch.start()
		ch.loop()
		ch.close()

class ChannelDatagramServer(gevent.server.DatagramServer):
	channel_cls = None
	channels = None
	def handle(self, *args):
		data, client_address = args
		
		if self.channels is None:
			self.channels = {}
		
		ch = self.channels.get(client_address)
		if ch is None:
			ch = self.channel_cls(
				sendto=self.sendto,
				remote_address=client_address,
				local_address=self.address)
			self.channels[client_address] = ch
			ch.start()
		
		f = StringIO.StringIO(data)
		ch.messages = read_message(f.read)
		ch.loop()
		
		if f.tell() < len(data):
			warnings.warn("%d bytes not consumed" % (len(data)-f.tell()))
		ch.messages = None


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
	tcpserv = ChannelStreamServer(("0.0.0.0", 6633), spawn=pool)
	tcpserv.channel_cls = type("TcpChannel", (
		BranchingMixin, SyncChannel, MonitorChannel, JackinChannel,
		ControllerChannel,
		AutoEchoChannel,
		LoggingChannel,
		HandleInSpawnChannel), {"accept_versions":[4,]})
	udpserv = ChannelDatagramServer(("0.0.0.0", 6633), spawn=pool)
	udpserv.channel_cls = type("UdpChannel", (
		BranchingMixin, SyncChannel, MonitorChannel, JackinChannel,
		ControllerChannel,
		AutoEchoChannel,
		LoggingChannel,
		HandleInSpawnChannel), {"accept_versions":[4,]})
	
	serve_forever(tcpserv, udpserv)

