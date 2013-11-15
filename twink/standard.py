from __future__ import absolute_import
from . import *
import os
import os.path
import SocketServer
import threading

class Xid(object):
	def __init__(self, xid=None):
		if xid is None:
			xid = hms_xid()
		self.xid = xid
		self.ev = threading.Event()
		self.data = None

class SyncChannel(OpenflowChannel):
	syncs = None
	def recv(self):
		message = super(SyncChannel, self).recv()
		if message:
			(version, oftype, length, xid) = parse_ofp_header(message)
			if self.syncs is None:
				self.syncs = {}
			if xid in self.syncs:
				x = self.xyncs[xid]
				x.data = message
				x.ev.set()
		return message
	
	def send_sync(self, message, **kwargs):
		(version, oftype, length, xid) = parse_ofp_header(message)
		x = Xid(xid=xid)
		self.syncs[x.xid] = x
		self.send(message, **kwargs)
		x.ev.wait()
		del(self.syncs[x.xid])
		return x.data
	
	def _sync_simple(self, req_oftype, res_oftype):
		message = self.send_sync(ofp_header_only(req_oftype, version=self.version))
		(version, oftype, length, xid) = parse_ofp_header(message)
		if oftype == res_oftype:
			return message
		else:
			raise OpenflowError(message)
	
	def close(self):
		if self.syncs is not None:
			for k,x in self.syncs.items():
				x.data = ""
				x.ev.set()
			self.syncs = None
		super(SyncChannel, self).close()
	
	def echo(self):
		return self._sync_simple(2, 3)
	
	def feature(self):
		return self._sync_simple(5, 6)
	
	def get_config(self):
		return self._sync_simple(7, 8)
	
	def barrier(self):
		if self.version==1:
			return self._sync_simple(18, 19) # OFPT_BARRIER_REQUEST=18 (v1.0)
		else:
			return self._sync_simple(20, 21) # OFPT_BARRIER_REQUEST=20 (v1.1, v1.2, v1.3)


class HandleInThreadChannel(OpenflowChannel):
	def handle_proxy(self, handle):
		def intercept(message):
			if not hasattr(self, "threads_lock"):
				self.threads_lock = threading.Lock()
				self.threads = []
			
			args = []
			th = threading.Thread(target=self.handle_in_thread, args=args)
			args.extend([th, handle, message])
			with self.threads_lock:
				self.threads.append(th)
			th.start()
		return intercept
	
	def handle_in_thread(self, th, handle, message):
		try:
			super(HandleInThreadChannel, self).handle_proxy(handle)(message)
		finally:
			if hasattr(self, "threads_lock"):
				with self.threads_lock:
					self.threads.remove(th)
	
	def close(self):
		super(HandleInThreadChannel, self).close()
		if hasattr(self, "threads_lock"):
			with self.threads_lock:
				for th in self.threads:
					th.join()
				self.threads = []


class BranchingChannel(OpenflowChannel):
	socket_dir = None
	def socket_path(self, path):
		if self.socket_dir:
			path = os.path.join(self.socket_dir, path)
		return os.path.abspath(path)
	
	def helper_path(self, suffix):
		old = self.socket_path("unknown-%x.%s" % (os.getpid(), suffix))
		if self.datapath:
			new = self.socket_path("%x-%x.%s" % (self.datapath, os.getpid(), suffix))
			if os.stat(old):
				os.rename(old, new)
			return new
		return old


class JackinChannel(BranchingChannel):
	jackin = None
	jackin_channels = None
	def close(self):
		super(JackinChannel, self).close()
		if self.jackin_channels:
			for ch in self.jackin_channels:
				ch.close()
		if self.jackin:
			self.jackin.shutdown()
			os.remove(self.jackin_path())
	
	def handle_proxy(self, handle):
		def intercept(message):
			super(JackinChannel, self).handle_proxy(handle)(message)
			
			(version, oftype, length, xid) = parse_ofp_header(message)
			if oftype==0:
				if self.jackin_channels is None:
					self.jackin_channels = set()
				
				class JackinServer(SocketServer.ThreadingUnixStreamServer, ChannelStreamServer): pass
				serv = JackinServer(self.jackin_path(), StreamRequestHandler)
				serv.channel_cls = type("JackinChannel",(AutoEchoChannel, LoggingChannel, JackinChildChannel),{
					"accept_versions":[self.version,],
					"parent": self,
					"channels": self.jackin_channels })
				th = threading.Thread(target=serv.serve_forever)
				th.daemon = True
				th.start()
				self.jackin = serv
		
		return intercept
	
	def jackin_path(self):
		return self.helper_path("jackin")


class MonitorChannel(BranchingChannel):
	monitor = None
	monitor_channels = None
	def close(self):
		super(MonitorChannel, self).close()
		if self.monitor_channels:
			for ch in self.monitor_channels:
				ch.close()
		if self.monitor:
			self.monitor.shutdown()
			os.remove(self.monitor_path())
	
	def recv(self):
		message = super(MonitorChannel, self).recv()
		if self.monitor_channels:
			for ch in self.monitor_channels:
				ch.send(message)
		return message
	
	def handle_proxy(self, handle):
		def intercept(message):
			super(MonitorChannel, self).handle_proxy(handle)(message)
			
			(version, oftype, length, xid) = parse_ofp_header(message)
			if oftype==0:
				if self.monitor_channels is None:
					self.monitor_channels = set()
				
				class MonitorServer(SocketServer.ThreadingUnixStreamServer, ChannelStreamServer): pass
				serv = MonitorServer(self.monitor_path(), StreamRequestHandler)
				serv.channel_cls = type("MonitorChannel",(AutoEchoChannel, LoggingChannel, ChildChannel),{
					"accept_versions":[self.version,],
					"parent": self,
					"channels": self.monitor_channels })
				th = threading.Thread(target=serv.serve_forever)
				th.daemon = True
				th.start()
				self.monitor = serv
		
		return intercept
	
	def monitor_path(self):
		return self.helper_path("monitor")


if __name__=="__main__":
	logging.basicConfig(level=logging.DEBUG)
	class TestServer(ChannelStreamServer, SocketServer.ThreadingTCPServer):
		# TCPServer is not a child of new style object, so don't use type()
		pass
	serv = TestServer(("0.0.0.0", 6633), StreamRequestHandler)
	serv.channel_cls = type("TcpChannel",(SyncChannel, MonitorChannel, JackinChannel, ControllerChannel, AutoEchoChannel, LoggingChannel, HandleInThreadChannel),{"accept_versions":[4,]})
	serv.serve_forever()
