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
			th = threading.Thread(target=self._handle_in_parallel, args=args)
			args.extend([handle, message, channel])
			th.start()
		return intercept
	
	def _handle_in_parallel(self, handle, message, channel):
		try:
			super(HandleInThreadChannel, self).handle_proxy(handle)(message, channel)
		except ChannelClose:
			channel.close()
		except:
			logging.error("handle error", exc_info=True)
			channel.close()


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
		return serv, th.start, serv.shutdown, serv.server_address
	
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
	
	for serv in servers:
		th = threading.Thread(target=serv.serve_forever)
		th.daemon = True
		th.start()
	try:
		while not ev.is_set():
			ev.wait(timeout=0.5)
	finally:
		for serv in servers:
			serv.server_close()
			serv.shutdown()


if __name__=="__main__":
	logging.basicConfig(level=logging.DEBUG)
	def msg_handle(message, channel):
		if message:
			(version, oftype, length, xid) = parse_ofp_header(message)
			if oftype==0:
				channel.feature()
	
	class TestTcpServer(ChannelStreamServer, SocketServer.ThreadingTCPServer):
		# TCPServer is not a child of new style object, so don't use type()
		pass
	tcpserv = TestTcpServer(("0.0.0.0", 6633), StreamRequestHandler)
	tcpserv.channel_cls = type("TcpChannel", (
		SyncChannel,
		BranchingMixin,
		JackinChannel,
		MonitorChannel,
		ControllerChannel,
		AutoEchoChannel, LoggingChannel, HandleInThreadChannel),{
			"accept_versions":[4,],
			"handle":staticmethod(msg_handle) })
	serve_forever(tcpserv)
