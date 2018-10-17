from __future__ import absolute_import
import binascii
import contextlib
import logging
import os
import struct
import types
import weakref
import functools
import datetime
from collections import namedtuple


_use_gevent = False
def use_gevent():
	global _use_gevent
	_use_gevent = True

class _sched_proxy(object):
	def __getattr__(self, name):
		_sched = None
		if _use_gevent:
			_sched = __import__("sched_gevent", globals(), level=1)
		else:
			_sched = __import__("sched_basic", globals(), level=1)
		if name in "subprocess socket Queue Lock Event spawn serve_forever".split():
			return getattr(_sched, name)
		raise AttributeError("No such attribute")

sched = _sched_proxy()

def default_wrapper(func):
	def wrap(*args, **kwargs):
		socket = sched.socket
		try:
			return func(*args, **kwargs)
		except socket.timeout:
			return None
		except socket.error as e:
			if e.errno in (os.errno.EAGAIN, os.errno.ECONNRESET, os.errno.EBADF):
				return b""
			elif e.errno in (os.errno.EINTR,):
				return None
			raise
		except KeyboardInterrupt:
			return b""
	return wrap


class ReadWrapper(object):
	def __init__(self, channel, read_wrap):
		self.channel = channel
		self.read_wrap = read_wrap
	
	def __enter__(self):
		self.installed_wrapper = self.channel.read_wrap
		self.channel.read_wrap = self
		return self.channel
	
	def __exit__(self, *args, **kwargs):
		self.channel.read_wrap = self.installed_wrapper
	
	def __call__(self, func):
		def wrap(*args, **kwargs):
			if self.channel.closed:
				return b""
			return self.read_wrap(func)(*args, **kwargs)
		return wrap


class Channel(object):
	'''
	Openflow abstract connection class
	
	This is not only for TCP but also for UDP.
	This is the reason that the name is not "Connection" but "Channel".
	You can subclass this to have instance members, of which lifecycle is 
	the same with channel.
	'''
	def __init__(self, *args, **kwargs):
		self._socket = kwargs.pop("socket", None) # dedicated socket
		self._sendto = kwargs.pop("sendto", None) # only if channel prefers sendto()
		self.reader = kwargs.pop("reader", None)
		self.read_wrap = kwargs.pop("read_wrap", default_wrapper)
		self.remote_address = kwargs.pop("remote_address", None)
		self.local_address = kwargs.pop("local_address", None)
		if self._socket:
			if self.remote_address is None:
				self.remote_address = self._socket.getpeername()
			if self.local_address is None:
				self.local_address = self._socket.getsockname()
			if hasattr(self._socket, "settimeout") and self._socket.gettimeout() == None:
				self._socket.settimeout(6)
	
	def attach(self, stream, **kwargs):
		self._socket = stream
		if hasattr(self._socket, "settimeout") and self._socket.gettimeout() == None:
			self._socket.settimeout(6)
		self.remote_address = stream.getpeername()
		self.local_address = stream.getsockname()
	
	@property
	def closed(self):
		# This is not self._socket.closed because in some use cases, 
		# self._socket is not available, for example with gevent.server.DatagramServer
		return self.remote_address is None
	
	def close(self):
		if self._socket:
			self._socket.close()
		
		if self.remote_address is not None:
			self.remote_address = None
	
	def send(self, message, **kwargs):
		if self._sendto:
			self._sendto(message, self.remote_address)
		elif self._socket:
			self._socket.send(message)
		else:
			raise ValueError("socket or sendto is required")
	
	def _recv(self, num):
		if self.reader:
			reader = self.reader
		else:
			reader = self._socket.recv
		return ReadWrapper(self, self.read_wrap)(reader)(num)


class Error(Exception):
	pass


class ChannelClose(Error):
	pass


class OpenflowBaseChannel(Channel):
	version = None # The negotiated version
	accept_versions = [4,] # defaults to openflow 1.3
	
	def __init__(self, *args, **kwargs):
		super(OpenflowBaseChannel, self).__init__(*args, **kwargs)
		self.buffer = b""
	
	def __iter__(self):
		while True:
			ret = self.recv()
			if ret:
				yield ret
			else:
				break
	
	def recv(self):
		required_len = 8
		while len(self.buffer) < required_len:
			tmp = super(OpenflowBaseChannel, self)._recv(8192)
			if tmp is None:
				continue
			elif len(tmp)==0:
				return tmp
			self.buffer += tmp
		
		p = struct.unpack_from("!BBHI", self.buffer)
		required_len = p[2]
		
		while len(self.buffer) < required_len:
			tmp = super(OpenflowBaseChannel, self)._recv(8192)
			if tmp is None:
				continue
			elif len(tmp)==0:
				return tmp
			self.buffer += tmp
		
		ret = self.buffer[0:required_len]
		self.buffer = self.buffer[required_len:]
		return ret


class LoggingChannel(OpenflowBaseChannel):
	channel_log_name = "channel"
	send_log_name = "send"
	recv_log_name = "recv"
	remote = ""
	
	def __init__(self, *args, **kwargs):
		super(LoggingChannel, self).__init__(*args, **kwargs)
		if self.remote_address:
			self.remote = " from %s" % self.remote_address[0]
		logging.getLogger(self.channel_log_name).info("%s connect%s" % (self, self.remote))
	
	def send(self, message, **kwargs):
		logging.getLogger(self.send_log_name).debug("%s %s" % (self, binascii.b2a_hex(message)))
		return super(LoggingChannel, self).send(message, **kwargs)
	
	def recv(self):
		message = super(LoggingChannel, self).recv()
		if message: # ignore b"" and None
			logging.getLogger(self.recv_log_name).debug("%s %s" % (self, binascii.b2a_hex(message)))
		return message
	
	def close(self):
		if not self.closed:
			super(LoggingChannel, self).close()
			logging.getLogger(self.channel_log_name).info("%s close%s" % (self, self.remote))


class OpenflowChannel(OpenflowBaseChannel):
	_start = None
	
	def attach(self, stream, **kwargs):
		super(OpenflowBaseChannel, self).attach(stream, **kwargs)
		if kwargs.get("autostart", True):
			self.start()
	
	def start(self):
		if self._start is None:
			self.send(hello(self.accept_versions))
			self._start = True
	
	def recv(self):
		message = super(OpenflowChannel, self).recv()
		if message:
			(version, oftype, length, xid) = parse_ofp_header(message)
			if oftype==0: # HELLO
				accept_versions = ofp_version_normalize(self.accept_versions)
				if not accept_versions:
					accept_versions = set([1,])
				cross_versions = parse_hello(message) & accept_versions
				if cross_versions:
					self.version = max(cross_versions)
				else:
					ascii_txt = "Accept versions: %s" % ["- 1.0 1.1 1.2 1.3 1.4".split()[x] for x in list(accept_versions)]
					self.send(struct.pack("!BBHIHH", max(accept_versions), 1,
						struct.calcsize("!BBHIHH")+len(ascii_txt), hms_xid(),
						0, 0) + ascii_txt.encode("ASCII"))
					raise ChannelClose(ascii_txt)
		return message


def parse_ofp_header(message):
	'''
	@return (version, oftype, message_len, xid)
	'''
	return struct.unpack_from("!BBHI", message)


def ofp_header_only(oftype, version=1, xid=None):
	if xid is None:
		xid = hms_xid()
	return struct.pack("!BBHI", version, oftype, 8, xid)


def hms_xid():
	'''Xid looks readable datetime like format when logged as int.'''
	now = datetime.datetime.now()
	candidate = int(("%02d"*3+"%04d") % (now.hour, now.minute, now.second, now.microsecond/100))
	if hasattr(hms_xid, "dedup"):
		if hms_xid.dedup >= candidate:
			candidate = hms_xid.dedup+1
	setattr(hms_xid, "dedup", candidate)
	return candidate


def ofp_version_normalize(versions):
	if isinstance(versions, list) or isinstance(versions, tuple) or isinstance(versions, set):
		vset = set()
		for version in versions:
			if isinstance(version, float):
				version = [1.0, 1.1, 1.2, 1.3, 1.4].index(version) + 1
			assert isinstance(version, int), "unknown version %s" % version
			vset.add(version)
		return vset
	elif versions is None:
		return set()
	assert False, "unknown versions %s" % versions


def hello(versions, **kwargs):
	xid = kwargs.get("xid", hms_xid())
	if versions:
		vset = ofp_version_normalize(versions)
	else:
		vset = set((1,))
	version = max(vset)
	
	if version < 4:
		return struct.pack("!BBHI", version, 0, 8, xid)
	else:
		units = [0,]*(1 + version//32)
		for v in vset:
			units[v//32] |= 1<<(v%32)
		
		versionbitmap_length = 4 + len(units)*4
		fmt = "!BBHIHH%dI%dx" % (len(units), 8*((len(units)-1)%2))
		return struct.pack(fmt, version, 0, struct.calcsize(fmt), xid, # HELLO
			1, versionbitmap_length, *units) # VERSIONBITMAP


def parse_hello(message):
	(version, oftype, length, xid) = parse_ofp_header(message)
	assert oftype==0 # HELLO
	versions = set()
	if length == 8:
		versions.add(version)
	else:
		(subtype, sublength) = struct.unpack_from("!HH", message, offset=8)
		assert subtype == 1 # VERSIONBITMAP
		units = struct.unpack_from("!%dI" % (sublength/4 - 1), message, offset=12)
		for idx,unit in zip(range(len(units)),units):
			for s in range(32):
				if unit&(1<<s):
					versions.add(idx*32 + s)
	return versions


class OpenflowServerChannel(OpenflowChannel):
	def loop(self):
		try:
			for message in self:
				if not message:
					break
				
				self.handle_proxy(self.handle)(message, self)
		except ChannelClose:
			self.close()
	
	def handle_proxy(self, handle):
		return handle
	
	def handle(self, message, channel):
		logging.getLogger(__name__).warn("check MRO")
		pass

class AutoEchoChannel(OpenflowServerChannel):
	'''
	AuthEchoChannel steals ECHO_REQUEST and automatically send echo response.
	'''
	def handle_proxy(self, handle):
		def intercept(message, channel):
			if message:
				(version, oftype, length, xid) = parse_ofp_header(message)
				if oftype==2: # ECHO
					self.send(struct.pack("!BBHI", self.version, 3, length, xid)+message[8:])
				else:
					super(AutoEchoChannel, self).handle_proxy(handle)(message, channel)
		return intercept


class WeakCallbackCaller(object):
	id = None
	cbref = None
	meth = None
	
	def ref(self, callable):
		self.id = id(callable)
		try:
			self.cbref = weakref.ref(callable.__self__)
			self.meth = callable.__func__
		except AttributeError:
			self.cbref = weakref.ref(callable)
	
	@property
	def callback(self):
		if self.cbref:
			r = self.cbref()
			if r:
				if self.meth:
					return functools.partial(self.meth, r)
				return r


class Barrier(WeakCallbackCaller):
	def __init__(self, xid, message_handler):
		if message_handler:
			self.ref(message_handler)
		self.xid = xid


class Chunk(WeakCallbackCaller):
	def __init__(self, message_handler):
		if message_handler:
			self.ref(message_handler)


class ControllerChannel(OpenflowServerChannel):
	datapath = None
	auxiliary = None
	
	def __init__(self, *args, **kwargs):
		super(ControllerChannel, self).__init__(*args, **kwargs)
		self.seq_lock = sched.Lock()
		self.seq = []
	
	def send(self, message, **kwargs):
		callback = kwargs.get("callback") # callable object
		if callback is None:
			callback = self.callback
		else:
			assert isinstance(callback, object)
			assert callable(callback)
		
		bmsg = None
		with self.seq_lock:
			(version, oftype, length, xid) = parse_ofp_header(message)
			if (oftype==18 and version==1) or (oftype==20 and version!=1): # OFPT_BARRIER_REQUEST
				self.seq.append(Barrier(xid, callback))
			elif self.seq:
				seq_last = self.seq[-1]
				if isinstance(seq_last, Chunk):
					if seq_last.id != id(callback):
						bxid = hms_xid()
						if self.version==1:
							bmsg = ofp_header_only(18, version=1, xid=bxid) # OFPT_BARRIER_REQUEST=18 (v1.0)
						else:
							bmsg = ofp_header_only(20, version=self.version, xid=bxid) # OFPT_BARRIER_REQUEST=20 (v1.1--v1.4)
						
						self.seq.append(Barrier(bxid, self.callback))
						self.seq.append(Chunk(callback))
				elif isinstance(seq_last, Barrier):
					self.seq.append(Chunk(callback))
				else:
					assert False, "seq element must be Chunk or Barrier"
			elif self.callback != callback:
				bxid = hms_xid()
				if self.version==1:
					bmsg = ofp_header_only(18, version=1, xid=bxid) # OFPT_BARRIER_REQUEST=18 (v1.0)
				else:
					bmsg = ofp_header_only(20, version=self.version, xid=bxid) # OFPT_BARRIER_REQUEST=20 (v1.1--v1.4)
				
				self.seq.append(Barrier(bxid, self.callback))
				self.seq.append(Chunk(callback))
		
		if bmsg:
			super(ControllerChannel, self).send(bmsg)
		super(ControllerChannel, self).send(message)
	
	def recv(self):
		message = super(ControllerChannel, self).recv()
		if message:
			(version, oftype, length, xid) = parse_ofp_header(message)
			if oftype==6: # FEATURES_REPLY
				if self.version < 4:
					(self.datapath,) = struct.unpack_from("!Q", message, offset=8) # v1.0--v1.2
				else:
					(self.datapath,_1,_2,self.auxiliary) = struct.unpack_from("!QIBB", message, offset=8) # v1.3--v1.4
		return message
	
	def callback(self, message, channel):
		return super(ControllerChannel, self).handle_proxy(self.handle)(message, channel)
	
	def handle_proxy(self, handle):
		def intercept(message, channel):
			(version, oftype, length, xid) = parse_ofp_header(message)
			
			if hasattr(self, "handle_async") and oftype in (10,11,12):
				# bypass method call for async message
				return super(ControllerChannel, self).handle_proxy(self.handle_async)(message, channel)
			
			callback = None
			with self.seq_lock:
				if self.seq:
					if (oftype==19 and version==1) or (oftype==21 and version!=1): # is barrier
						chunk_drop = False
						for e in self.seq:
							if isinstance(e, Barrier):
								if e.xid == xid:
									self.seq = self.seq[self.seq.index(e)+1:]
									callback = e.callback
								else:
									assert False, "missing barrier(xid=%x) before barrier(xid=%x)" % (e.xid, xid)
								break
							elif isinstance(e, Chunk):
								assert chunk_drop==False, "dropping multiple chunks at a time"
								chunk_drop = True
						if callback is None:
							assert False, "got unknown barrier xid=%x" % xid
					elif isinstance(self.seq[0], Chunk):
						callback = self.seq[0].callback
					else:
						callback = self.callback
				else:
					callback = self.callback
			
			if callback:
				return callback(message, self)
			
			logging.getLogger(__name__).warn("No callback found for handling message %s" % binascii.b2a_hex(message))
		return intercept


class RateLimit(object):
	def __init__(self, size):
		self.size = size
		
		self.cold_lock = sched.Lock()
		self.cold = []
		
		self.loop_lock = sched.Lock()
	
	def spawn(self, func, *args, **kwargs):
		with self.cold_lock:
			self.cold.append((func, args, kwargs))
		
		sched.spawn(self.loop)
	
	def loop(self):
		with self.loop_lock:
			while len(self.cold) > 0:
				hot_lock = sched.Lock()
				hot = []
				children = {}
				while len(hot) < self.size and len(self.cold) > 0:
					task = None
					with self.cold_lock:
						task = self.cold.pop(0)
					
					if task:
						(func, args, kwargs) = task
						def proxy():
							func(*args, **kwargs)
							with hot_lock:
								hot.remove(task)
						hot.append(task)
						children[id(task)] = sched.spawn(proxy)
					
					for task_id,job in tuple(children.items()):
						running = False
						with hot_lock:
							if task_id in [id(task) for task in hot]:
								running = True
						
						if running:
							job.join(3)
						else:
							chilren.pop(task)
						
						break


class ParallelChannel(OpenflowServerChannel):
	# mixin for parent channel
	socket_dir = None
	async_rate = 0
	
	def __init__(self, *args, **kwargs):
		super(ParallelChannel, self).__init__(*args, **kwargs)
		self.close_lock = sched.Lock()
		self.async_pool = RateLimit(self.async_rate)
	
	def close(self):
		with self.close_lock:
			super(ParallelChannel, self).close()
	
	def handle_proxy(self, handle):
		def intercept(message, channel):
			def proxy(message, channel):
				try:
					handle(message, channel)
				except ChannelClose:
					logging.getLogger(__name__).info("closing", exc_info=True)
					channel.close()
				except:
					logging.getLogger(__name__).error("handle error", exc_info=True)
					channel.close()
			
			rated_call = False
			if self.async_rate:
				(version, oftype, length, xid) = parse_ofp_header(message)
				if oftype in (10, 11, 12):
					rated_call = True
			
			if rated_call:
				self.async_pool.spawn(proxy, message, channel)
			else:
				sched.spawn(proxy, message, channel)
		return super(ParallelChannel, self).handle_proxy(intercept)
	
	def socket_path(self, path):
		if self.socket_dir:
			path = os.path.join(self.socket_dir, path)
		return os.path.abspath(path)
	
	def helper_path(self, suffix):
		old = self.socket_path("unknown-%x.%s" % (id(self), suffix))
		if self.datapath:
			new = self.socket_path("%x-%x.%s" % (self.datapath, id(self), suffix))
			try:
				os.rename(old, new)
			except OSError:
				pass
			return new
		return old
	
	def override_required(self, *args, **kwargs):
		raise Error("Concrete MixIn required")


def bound_socket(info, socktype):
	socket = sched.socket
	if isinstance(info, socket.socket):
		return info
	elif isinstance(info, tuple) or isinstance(info, list):
		infos = [o for o in socket.getaddrinfo(*info) if o[1]==socktype or o[1]==0]
		(family, socktype, proto, canonname, sockaddr) = infos[0]
		s = socket.socket(family, socktype)
		s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		s.bind(sockaddr)
		return s
	elif isinstance(info, str):
		s = socket.socket(socket.AF_UNIX, socktype)
		s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		s.bind(info)
		return s
	else:
		raise ValueError("unexpected %s" % info)


def stream_socket(info):
	return bound_socket(info, sched.socket.SOCK_STREAM)


def dgram_socket(info):
	return bound_socket(info, sched.socket.SOCK_DGRAM)


class StreamServer(object):
	channel_cls = None
	def __init__(self, bound_sock, **kwargs):
		self.accepting = False
		self.sock = stream_socket(bound_sock)
		self.channels_lock = sched.Lock()
		self.channels = set()
		self.server_address = self.sock.getsockname()
	
	def start(self):
		self.accepting = True
		sock = self.sock
		sock.settimeout(6)
		sock.listen(10)
		sched.spawn(self.run)
	
	def run(self):
		try:
			while self.accepting:
				try:
					s = self.sock.accept()
				except sched.socket.timeout:
					continue
				try:
					ch = self.channel_cls(socket=s[0], remote_address=s[1], read_wrap=self.read_wrap)
					ch.start()
				except Exception as e:
					logging.getLogger(__name__).error("Channel setup failed for %s %s" % (s[1], e), exc_info=True)
					s[0].close()
					continue
				
				sched.spawn(self._loop_runner, ch)
		finally:
			self.sock.close()
	
	def _loop_runner(self, ch):
		with self.channels_lock:
			self.channels.add(ch)
		ch.loop()
		ch.close()
		with self.channels_lock:
			self.channels.remove(ch)
	
	def read_wrap(self, func):
		def wrap(*args, **kwargs):
			if self.accepting==False:
				return b""
			return default_wrapper(func)(*args, **kwargs)
		return wrap
	
	def stop(self):
		self.accepting = False
		for ch in list(self.channels):
			ch.close()


class DgramServer(object):
	channel_cls = None
	def __init__(self, bound_sock):
		self.accepting = False
		self.sock = dgram_socket(bound_sock)
		self.remotes_lock = sched.Lock()
		self.remotes = {}
		self.remote_locks = {}
	
	def start(self):
		self.accepting = True
		sched.spawn(self.run)
	
	def run(self):
		sock = self.sock
		while self.accepting:
			try:
				data,remote_address = sock.recv()
			except sched.socket.timeout:
				continue
			
			with self.remotes_lock:
				if remote_address in self.remotes:
					ch = self.remotes[remote_address]
					lock = self.remote_locks[remote_address]
				else:
					ch = self.channel_cls(sendto=sock.sendto, remote_address=remote_address, local_address=sock.getsockname())
					ch.start()
					self.remotes[remote_address] = ch
					lock = sched.Lock()
					self.remote_locks[remote_address] = lock
			
			sched.spawn(self.locked_loop, ch, lock, data)
		sock.close()
	
	def locked_loop(self, ch, lock, data):
		with lock:
			ch.reader = StringIO.StringIO(data).read
			ch.loop()
	
	def stop(self):
		self.accepting = False


class ParentChannel(ControllerChannel, ParallelChannel):
	jackin = False
	monitor = False
	jackin_shutdown = None
	monitor_shutdown = None
	monitors = set()
	
	def close(self):
		if self.jackin_shutdown:
			self.jackin_shutdown()
			try:
				os.remove(self.helper_path("jackin"))
			except OSError:
				pass
		
		if self.monitor_shutdown:
			self.monitor_shutdown()
			try:
				os.remove(self.helper_path("monitor"))
			except OSError:
				pass
		
		super(ParentChannel, self).close()
	
	def recv(self):
		message = super(ParentChannel, self).recv()
		if message:
			(version, oftype, length, xid) = parse_ofp_header(message)
			if oftype==0:
				if self.jackin:
					serv, addr = self.jackin_server()
					self.jackin_shutdown = serv.stop
					serv.start() # start after assignment especially for pthread
				
				if self.monitor:
					serv, addr = self.monitor_server()
					self.monitor_shutdown = serv.stop
					self.monitors = serv.channels
					serv.start() # start after assignment especially for pthread
			else:
				if oftype==6: # FEATURES_REPLY
					if self.jackin:
						self.helper_path("jackin")
					if self.monitor:
						self.helper_path("monitor")
				
				for ch in list(self.monitors):
					ch.send(message)
		
		return message
	
	def jackin_server(self):
		path = self.helper_path("jackin")
		serv = type("JackinServer", (StreamServer,), dict(
			channel_cls = type("JackinCChannel",(JackinChildChannel, AutoEchoChannel, LoggingChannel),{
				"accept_versions":[self.version,],
				"parent": self })))(path)
		return serv, path
	
	def monitor_server(self):
		path = self.helper_path("monitor")
		serv = type("MonitorServer", (StreamServer,), dict(
			channel_cls = type("MonitorCChannel",(ChildChannel, AutoEchoChannel, LoggingChannel),{
				"accept_versions":[self.version,],
				"parent": self })))(path)
		return serv, path
	
	def temp_server(self):
		s = sched.socket.socket(sched.socket.AF_INET, sched.socket.SOCK_STREAM)
		s.setsockopt(sched.socket.SOL_SOCKET, sched.socket.SO_REUSEADDR, 1)
		s.bind(("127.0.0.1", 0))
		serv = type("TempServer", (StreamServer,), dict(
			channel_cls = type("TempCChannel",(JackinChildChannel, AutoEchoChannel, LoggingChannel),{
				"accept_versions":[self.version,],
				"parent": self })))(s)
		return serv.start, serv.stop, s.getsockname()

class JackinChannel(ParentChannel):
	'''
	MonitorChannel opens unix domain sockets for openflow operators(jackin programs),
	such as ovs-ofctl.
	'''
	jackin = True


class MonitorChannel(ParentChannel):
	'''
	MonitorChannel opens unix domain sockets for openflow message listeners(monitors).
	'''
	monitor = True


class ChildChannel(OpenflowChannel):
	parent = None # must be set
	
	def send(self, message, **kwargs):
		try:
			super(ChildChannel, self).send(message, **kwargs)
		except:
			logging.getLogger(__name__).warn("child channel send error %s" % binascii.b2a_hex(message), exc_info=True)
			self.close()
	
	def handle(self, message, channel):
		pass # ignore all messages


class JackinChildChannel(ChildChannel):
	def __init__(self, *args, **kwargs):
		super(JackinChildChannel, self).__init__(*args, **kwargs)
	
	def handle(self, message, channel):
		(version, oftype, length, xid) = parse_ofp_header(message)
		if oftype!=0:
			# send to upstream(parent), callback is downstream(self)
			self.parent.send(message, callback=self.sendto_child)
	
	def sendto_child(self, message, upstream_channel):
		self.send(message)
	
	def close(self):
		super(JackinChildChannel, self).close()


class SyncTracker(object):
	def __init__(self, xid, ev):
		self.xid = xid
		self.ev = ev
		self.data = None


class SyncChannel(ParallelChannel):
	'''
	SyncChannel adds synchronous methods.
	'''
	def __init__(self, *args, **kwargs):
		super(SyncChannel, self).__init__(*args, **kwargs)
		self.syncs = {}
		self.syncs_lock = sched.Lock()
	
	def recv(self):
		message = super(SyncChannel, self).recv()
		if message:
			(version, oftype, length, xid) = parse_ofp_header(message)
			if xid in self.syncs:
				x = self.syncs[xid]
				if (version==1 and oftype==17) or (version!=1 and oftype==19): # multipart
					with self.syncs_lock:
						if x.data is None:
							x.data = message
						else:
							x.data += message
					if not struct.unpack_from("!H", message, offset=10)[0] & 1:
						x.ev.set()
				else:
					x.data = message
					x.ev.set()
		return message
	
	def send_sync(self, message, **kwargs):
		(version, oftype, length, xid) = parse_ofp_header(message)
		x = SyncTracker(xid, sched.Event())
		with self.syncs_lock:
			self.syncs[x.xid] = x
		self.send(message, **kwargs)
		x.ev.wait(timeout=kwargs.get("timeout", 10))
		with self.syncs_lock:
			self.syncs.pop(x.xid)
		return x.data
	
	def _sync_simple(self, req_oftype, res_oftype):
		message = self.send_sync(ofp_header_only(req_oftype, version=self.version))
		if message:
			(version, oftype, length, xid) = parse_ofp_header(message)
			if oftype != res_oftype:
				raise OpenflowError(message)
		else:
			raise ChannelClose("no response")
		return message
	
	def close(self):
		if self.syncs is not None:
			for k,x in tuple(self.syncs.items()):
				x.data = ""
				x.ev.set()
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
	
	def single(self, message, **kwargs):
		return self.multi((message,), **kwargs).pop()
	
	def multi(self, messages, **kwargs):
		prepared = []
		for message in messages:
			(version, oftype, length, xid) = parse_ofp_header(message)
			x = SyncTracker(xid, sched.Event())
			with self.syncs_lock:
				self.syncs[x.xid] = x
			self.send(message, **kwargs)
			prepared.append(xid)
		
		self.barrier()
		results = []
		for xid in prepared:
			if xid in self.syncs:
				results.append(self.syncs[xid].data)
				with self.syncs_lock:
					self.syncs.pop(xid)
			else:
				results.append(None)
		return results


class PortMonitorChannel(ControllerChannel, ParallelChannel):
	'''
	PortMonitorChannel exposes `ports` property, which will be synced with the openflow switch.
	'''
	def __init__(self, *args, **kwargs):
		super(PortMonitorChannel, self).__init__(*args, **kwargs)
		self.timeout = kwargs.get("timeout", 6.0)
		self._ports_lock = sched.Lock()
		self._ports = []
		self._ports_init = sched.Event()
		self._port_monitor_multi = dict()
		
		self._attach = weakref.WeakValueDictionary()
		self._detach = weakref.WeakValueDictionary()
	
	def recv(self):
		message = super(PortMonitorChannel, self).recv()
		if message:
			ofp_port = "!H6s16sIIIIII" # ofp_port v1.0
			ofp_port_names = '''port_no hw_addr name
				config state
				curr advertised supported peer'''
			if self.version in (2,3,4):
				ofp_port = "!I4x6s2x16sIIIIIIII"
				ofp_port_names = '''port_no hw_addr name
					config state
					curr advertised supported peer
					curr_speed max_speed'''
			elif self.version == 5:
				ofp_port = "!IH2x6s2x6sII"
				ofp_port_names = '''port_no length hw_addr name
					config state'''
			
			(version, oftype, length, xid) = parse_ofp_header(message)
			if xid in self._port_monitor_multi and oftype==19: # MULTIPART_REPLY
				assert self.version in (4,5)
				(mptype, flags) = struct.unpack_from("!HH4x", message, offset=8)
				if mptype==13: # OFPMP_PORT_DESC
					ports = self._port_monitor_multi[xid]
					offset = 16
					while offset < length:
						port = list(struct.unpack_from(ofp_port, message, offset=offset))
						port[2] = port[2].partition(b'\0')[0]
						ports.append(namedtuple("ofp_port", ofp_port_names)(*port))
						offset += struct.calcsize(ofp_port)
				
					if not flags&1:
						with self._ports_lock:
							self._ports_replace(ports)
							self._ports_init.set()
							del(self._port_monitor_multi[xid])
			elif oftype==6 and self.version != 4: # FEATURES_REPLY
				fmt = "!BBHIQIB3x"
				assert struct.calcsize(fmt) % 8 == 0
				offset = struct.calcsize(fmt+"II")
				ports = []
				while offset < length:
					port = list(struct.unpack_from(ofp_port, message, offset=offset))
					port[2] = port[2].partition(b'\0')[0]
					ports.append(namedtuple("ofp_port", ofp_port_names)(*port))
					offset += struct.calcsize(ofp_port)
				with self._ports_lock:
					self._ports_replace(ports)
					self._ports_init.set()
			elif oftype==12: # PORT_STATUS
				p = struct.unpack_from("!B7x"+ofp_port[1:], message, offset=8)
				reason = p[0]
				port = list(p[1:])
				port[2] = port[2].partition(b'\0')[0]
				self._update_port(reason, namedtuple("ofp_port", ofp_port_names)(*port))
		return message
	
	def _update_port(self, reason, port):
		with self._ports_lock:
			ports = list(self._ports)
			hit = [x for x in ports if x[0]==port[0]] # check with port_no(0)
			if reason==0: # ADD
				if self._ports_init.is_set():
					assert not hit
				ports.append(port)
				
				s = self._attach.get(port.port_no, self._attach.get(port.name))
				if s:
					s.set(port)
					self._attach.pop(s)
			elif reason==1: # DELETE
				if self._ports_init.is_set():
					assert hit
				if hit:
					assert len(hit) == 1
					ports.remove(hit.pop())
				
				s = self._detach.get(port.port_no, self._detach.get(port.name))
				if s:
					s.set(port)
					self._detach.pop(s)
			elif reason==2: # MODIFY
				if self._ports_init.is_set():
					assert hit
				if hit:
					assert len(hit) == 1
					old = hit.pop()
					idx = ports.index(old)
					ports.remove(old)
					ports.insert(idx, port)
				else:
					ports.append(port)
			else:
				assert False, "unknown reason %d" % reason
			self._ports = ports
	
	@property
	def ports(self):
		if not self._ports_init.is_set():
			if self.version in (4, 5):
				xid = hms_xid()
				with self._ports_lock:
					self._port_monitor_multi[xid] = []
				self.send(struct.pack("!BBHIHH4x", self.version, 
					18, # MULTIPART_REQUEST (v1.3, v1.4)
					16, # struct.calcsize(fmt)==16
					xid, 
					13, # PORT_DESC
					0, # no REQ_MORE
					))
			else:
				self.send(ofp_header_only(5, version=self.version)) # FEATURES_REQUEST
			self._ports_init.wait(timeout=self.timeout)
		return tuple(self._ports)
	
	def _ports_replace(self, new_ports):
		old_ports = self._ports
		
		old_nums = set([p.port_no for p in old_ports])
		old_names = set([p.name for p in old_ports])
		new_nums = set([p.port_no for p in new_ports])
		new_names = set([p.name for p in new_ports])
		
		for port in old_ports:
			if port.port_no in old_nums-new_nums:
				s = self._detach.get(port.port_no)
				if s:
					s.set(port)
					self._detach.pop(s)
			if port.name in old_names-new_names:
				s = self._detach.get(port.name)
				if s:
					s.set(port)
					self._detach.pop(s)
		
		for port in new_ports:
			if port.port_no in new_nums-old_nums:
				s = self._attach.get(port.port_no)
				if s:
					s.set(port)
					self._attach.pop(s)
			if port.name in new_names-old_names:
				s = self._attach.get(port.name)
				if s:
					s.set(port)
					self._attach.pop(s)
		
		self._ports = new_ports
	
	def close(self):
		self._ports_init.set() # unlock the event
		super(PortMonitorChannel, self).close()
	
	def wait_attach(self, num_or_name, timeout=10):
		for port in self._ports:
			if port.port_no == num_or_name or port.name == num_or_name:
				return port
		
		with self._ports_lock:
			if num_or_name not in self._attach:
				result = self._attach[num_or_name] = sched.Event()
			else:
				result = self._attach[num_or_name]
		
		if result.wait(timeout=timeout):
			for port in self._ports:
				if port.port_no == num_or_name or port.name == num_or_name:
					return port
	
	def wait_detach(self, num_or_name, timeout=10):
		hit = False
		for port in self._ports:
			if port.port_no == num_or_name or port.name == num_or_name:
				hit = True
		if not hit:
			return num_or_name # already detached
		
		with self._ports_lock:
			if num_or_name not in self._detach:
				result = self._detach[num_or_name] = sched.Event()
			else:
				result = self._detach[num_or_name]
		
		if result.wait(timeout=timeout):
			return num_or_name
