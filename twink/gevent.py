from __future__ import absolute_import
import logging
import StringIO
from twink import *
from gevent import spawn
from gevent.event import Event
from gevent.queue import Queue
from gevent.server import StreamServer, DatagramServer

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
		self.accept_versions = ofp_version_normalize(kwargs.get("accept_versions", [1,]))
		self.message_handler = kwargs.get("message_handler", default_message_handler)
		self.channel_cls = kwargs.get("channel_cls", StreamChannel)


class StreamHandler(ServerHandler):
	def __call__(self, socket, address):
		assert issubclass(self.channel_cls, StreamChannel)
		channel = self.channel_cls(socket=socket)
		
		channel.send(hello(self.accept_versions), self.message_handler)
		
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
			channel = self.channel_cls(server=self, address=address)
			self.channels[address] = channel
			
			channel.send(hello(self.accept_versions), self.message_handler)
		
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
	logging.basicConfig(level=logging.DEBUG)
	address = ("0.0.0.0", 6633)
	appconf = {"accept_versions":[1,]}
	tcpserv = StreamServer(address, handle=StreamHandler(
		channel_cls=type("SChannel", (ControllerChannel, LoggingChannel, StreamChannel), {}),
		accept_versions=[1]))
	udpserv = OpenflowDatagramServer(address,
		hannel_cls=type("DChannel", (ControllerChannel, LoggingChannel, DatagramChannel), {}),
		accept_versions=[1])
	serve_forever(tcpserv, udpserv)
