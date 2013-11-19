from __future__ import absolute_import
from . import *
import signal
import SocketServer
import threading
import subprocess

class HandleInThreadChannel(OpenflowChannel):
	def handle_proxy(self, handle):
		def intercept(message, channel):
			args = []
			th = threading.Thread(target=self.handle_in_thread, args=args)
			args.extend([th, handle, message, channel])
			th.start()
		return intercept
	
	def handle_in_thread(self, th, handle, message, channel):
		try:
			super(HandleInThreadChannel, self).handle_proxy(handle)(message, channel)
		except ChannelClose:
			channel.close()
		except:
			channel.close()
			raise


class BranchingMixin(object):
	subprocess = subprocess
	event = threading.Event
	
	def jackin_server(self, path, channels):
		class JackinServer(SocketServer.ThreadingUnixStreamServer, ChannelStreamServer): pass
		serv = JackinServer(path, StreamRequestHandler)
		serv.channel_cls = type("JackinChannel",(AutoEchoChannel, LoggingChannel, JackinChildChannel),{
			"accept_versions":[self.version,],
			"parent": self,
			"channels": channels })
		th = threading.Thread(target=serv.serve_forever)
		th.daemon = True
		return serv, th.start, serv.shutdown, serv.server_address
	
	def monitor_server(self, path, channels):
		class MonitorServer(SocketServer.ThreadingUnixStreamServer, ChannelStreamServer): pass
		serv = MonitorServer(path, StreamRequestHandler)
		serv.channel_cls = type("MonitorChannel",(AutoEchoChannel, LoggingChannel, ChildChannel),{
			"accept_versions":[self.version,],
			"parent": self,
			"channels": channels })
		th = threading.Thread(target=serv.serve_forever)
		th.daemon = True
		return serv, th.start, serv.shutdown. serv.server_address
	
	def temp_server(self, channels):
		class TempServer(SocketServer.ThreadingMixIn, ChannelStreamServer): pass
		serv = TempServer(("127.0.0.1",0), StreamRequestHandler)
		serv.channel_cls = type("TempChannel",(AutoEchoChannel, LoggingChannel, JackinChildChannel),{
			"accept_versions":[self.version,],
			"parent": self,
			"channels": channels })
		th = threading.Thread(target=serv.serve_forever)
		th.daemon = True
		return serv, th.start, serv.shutdown, serv.server_address


def serve_forever(*servers, **opts):
	ev = opts.get("main")
	if not ev:
		ev = threading.Event()
		signal.signal(signal.SIGINT, lambda num,fr: ev.set())
	
	threads = [threading.Thread(target=serv.serve_forever) for serv in servers]
	for th in threads:
#		th.daemon = True
		th.start()
	try:
		while not ev.is_set():
			ev.wait(timeout=0.5)
	finally:
		for serv in servers:
			serv.server_close()
			serv.shutdown()
		for th in threads:
			if threading.current_thread() != th:
				th.join()


if __name__=="__main__":
	logging.basicConfig(level=logging.DEBUG)
	class TestTcpServer(ChannelStreamServer, SocketServer.ThreadingTCPServer):
		# TCPServer is not a child of new style object, so don't use type()
		pass
	tcpserv = TestTcpServer(("0.0.0.0", 6633), StreamRequestHandler)
	tcpserv.channel_cls = type("TcpChannel",(BranchingMixin, ControllerChannel, AutoEchoChannel, LoggingChannel, HandleInThreadChannel),{"accept_versions":[4,]})
	serve_forever(tcpserv)
