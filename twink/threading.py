from __future__ import absolute_import
from . import *
import signal
import SocketServer
import threading
import subprocess
try:
	from Queue import Queue as queue
except:
	from queue import queue

__all__=("ParallelMixin","serve_forever")

class Threadlet(object):
	started = False
	def __init__(self, func, *args, **kwargs):
		self.result = queue()
		def wrap():
			try:
				self.result.put((func(*args, **kwargs), None), False)
			except Exception, e:
				self.result.put((None, e), False)
		
		self.thread = threading.Thread(target=wrap)
	
	def start(self):
		self.thread.start()
		self.started = True
	
	def join(self, timeout=None):
		if self.started:
			return self.thread.join(timeout)
		assert False, "join() called before start()"
	
	def get(self, block=True, timeout=None):
		if self.started:
			if self.result:
				self.pair = self.result.get(block, timeout)
			self.result = None
			if self.pair[1] is None:
				return self.pair[0]
			else:
				raise self.pair[1]


class ParallelMixin(ParallelChannel):
	subprocess = subprocess
	event = threading.Event
	lock_cls = threading.RLock
	
	def __init__(self, *args, **kwargs):
		super(ParallelMixin, self).__init__(*args, **kwargs)
	
	def spawn(self, func, *args, **kwargs):
		th = Threadlet(func, *args, **kwargs)
		th.start()
		return th
	
	def jackin_server(self, path):
		class JackinServer(ChannelUnixStreamServer):
			channel_cls = type("JackinChannel",(AutoEchoChannel, LoggingChannel, JackinChildChannel),{
				"accept_versions":[self.version,],
				"parent": self })
		
		serv = JackinServer(path, StreamRequestHandler)
		return Threadlet(serv.serve_forever).start, serv.shutdown, serv.server_address
	
	def monitor_server(self, path):
		class MonitorServer(ChannelUnixStreamServer):
			channel_cls = type("MonitorChannel",(AutoEchoChannel, LoggingChannel, ChildChannel),{
				"accept_versions":[self.version,],
				"parent": self })
		
		serv = MonitorServer(path, StreamRequestHandler)
		return Threadlet(serv.serve_forever).start, serv.shutdown, serv.server_address
	
	def temp_server(self):
		class TempServer(ChannelStreamServer):
			channel_cls = type("TempChannel",(AutoEchoChannel, LoggingChannel, JackinChildChannel),{
				"accept_versions":[self.version,],
				"parent": self })
		
		serv = TempServer(("127.0.0.1",0), StreamRequestHandler)
		return Threadlet(serv.serve_forever).start, serv.shutdown, serv.server_address


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
	tcpserv = TestTcpServer(("0.0.0.0", 6653), StreamRequestHandler)
	tcpserv.channel_cls = type("TcpChannel", (
		SyncChannel,
		JackinChannel,
		MonitorChannel,
		ControllerChannel,
		AutoEchoChannel,
		LoggingChannel,
		ParallelMixin),{
			"accept_versions":[4,],
			"handle":staticmethod(msg_handle) })
	serve_forever(tcpserv)
