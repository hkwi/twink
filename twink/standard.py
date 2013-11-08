import logging
import SocketServer
import StringIO
import socket
from twink import *

class StandardChannel(Channel):
	def __init__(self, *args, **kwargs):
		self.socket = kwargs["socket"]
		self.peer = kwargs["peer"]
		self.server = kwargs["server"]
	
	def direct_send(self, message):
		if self.peer:
			self.socket.sendto(message, self.peer)
		else:
			self.socket.send(message)

class ChannelClose(Exception):
	# to normally close the channel by raising an exception
	pass

class StandardHandler(object):
	def __init__(self, *args, **kwargs):
		self.message_handler = kwargs.get("message_handler", easy_message_handler)
		self.channel_cls = kwargs.get("channel_cls", StandardChannel)

class DatagramHandler(StandardHandler):
	def __init__(self, *args, **kwargs):
		super(DatagramHandler, self).__init__(*args, **kwargs)
		self.channels = {}
	
	def __call__(self, request, peer, server):
		data, socket = request
		
		channel = self.channels.get(peer)
		if channel is None:
#			assert issubclass(self.channel_cls, DatagramChannel)
			channel = self.channel_cls(socket=socket, peer=peer, server=server)
			self.channels[peer] = channel
			
			channel.send(hello(channel.accept_versions), self.message_handler)
		
		fp = StringIO.StringIO(data)
		try:
			while True:
				message = read_message(fp.read)
				if message:
					try:
						channel.on_message(message)
					except:
						logging.error("message_handler failed", exc_info=True)
						channel.close()
				else:
					break
		finally:
			fp.close()

class StreamHandler(StandardHandler):
	# called per connection.
	def __call__(self, socket, peer, server):
		assert issubclass(self.channel_cls, StandardChannel)
		try:
			channel = self.channel_cls(socket=socket, peer=peer, server=server)
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
			while True:
				message = read_message(socket.recv)
				if message:
					channel.on_message(message)
				else:
					break
		except ChannelClose as e:
			logging.info(e)
		except:
			logging.info("message_handler failed", exc_info=True)
		finally:
			channel.close()
			socket.close()
		
		if channel.version is None:
			raise ChannelClose("closed before hello recv")

class UnixStreamClientChannel(SwitchChannel,StandardChannel):
#	accept_versions = [4,]
	def __init__(self, filename, callback=easy_message_handler):
		s = socket.socket(socket.AF_UNIX)
		s.connect(filename)
		super(UnixStreamClientChannel, self).__init__(socket=s, peer=None, server=None)
		self.send(hello(self.accept_versions), callback)

if __name__=="__main__":
	def handle_message(message, channel):
		(version, oftype, message_len, xid) = parse_ofp_header(message)
		ret = easy_message_handler(message, channel)
		if oftype==0:
			print "got hello"
		return ret
	
	logging.basicConfig(level=logging.DEBUG)
# 	serv = SocketServer.UDPServer(("0.0.0.0", 6633), DatagramHandler(
# 		channel_cls=type("SChannel",(SwitchChannel,LoggingChannel,StandardChannel),{"accept_versions":[4,]}),
# 		message_handler=handle_message))

	serv = SocketServer.UnixStreamServer("hoge.txt", StreamHandler(
		channel_cls=type("SChannel",(ControllerChannel,LoggingChannel,StandardChannel),{"accept_versions":[4,]}),
		message_handler=handle_message))

# 	serv = SocketServer.ThreadingTCPServer(("0.0.0.0", 6633), StreamHandler(
# 		channel_cls=type("SChannel",(ControllerChannel,LoggingChannel,StandardChannel),{"accept_versions":[4,]}),
# 		message_handler=handle_message))
	serv.serve_forever()
