import binascii
import datetime
import logging
import os
import socket
import SocketServer
import struct
import types
import weakref


class Channel(object):
	'''
	Openflow abstract connection class, not only for TCP but also for UDP.
	This is the reason that the name is not "Connection" but "Channel".
	'''
	messages = None
	def __init__(self, *args, **kwargs):
		self._socket = kwargs.get("socket") # dedicated socket
		self._sendto = kwargs.get("sendto") # only if channel prefers sendto()
		self._peer = kwargs.get("peer")
	
	@property
	def closed(self):
		return self._peer is None
	
	def close(self):
		if self.messages:
			self.messages.close()
		
		if self._socket:
			self._socket.close()
			self._socket = None
		
		if self._peer:
			self._peer = None
	
	def send(self, message, **kwargs):
		if self._sendto:
			self._sendto(message, self._peer)
		elif self._socket:
			self._socket.send(message)
		else:
			raise ValueError("socket or sendto is required")
	
	def recv(self):
		return self.messages.next()
	
	def start(self):
		pass
	
	def loop(self):
		pass

class LoggingChannel(Channel):
	channel_log_name = "channel"
	send_log_name = "send"
	recv_log_name = "recv"
	
	def __init__(self, *args, **kwargs):
		super(LoggingChannel, self).__init__(*args, **kwargs)
		logging.getLogger(self.channel_log_name).info("%s connect" % self)
	
	def send(self, message, **kwargs):
		logging.getLogger(self.send_log_name).info("%s %s" % (self, binascii.b2a_hex(message)))
		return super(LoggingChannel, self).send(message, **kwargs)
	
	def recv(self):
		message = super(LoggingChannel, self).recv()
		logging.getLogger(self.recv_log_name).info("%s %s" % (self, binascii.b2a_hex(message)))
		return message
	
	def close(self):
		super(LoggingChannel, self).close()
		logging.getLogger(self.channel_log_name).info("%s close" % self)


class Error(Exception):
	pass


class OpenflowError(Error):
	def __init__(self, message):
		vals = list(struct.unpack_from("!BBHIHH", message))
		vals.append(binascii.b2a_hex(message[struct.calcsize("!BBHIHH"):]))
		o = zip("version oftype length xid etype ecode payload".split(), vals)
		super(OpenflowError, self).__init__("OFPT_ERROR %s" % repr(o))
		self.message = message

class OfpVersionMismatch(Error):
	pass


def parse_ofp_header(message):
	'''
	@return (version, oftype, message_len, xid)
	'''
	return struct.unpack_from("!BBHI", message)

def read_message(sized_read, interactive=False):
	'''
	generator for openflow message from bytestream reader.
	sized_read : function of `bytestr = func(size)`
	
	When resource is temporary unavailable, then empty string
	"" will be returned.
	This happens with nonblocking socket for example.
	'''
	OFP_HEADER_LEN = 8
	while True:
		message = bytearray()
		while len(message) < OFP_HEADER_LEN:
			ext = ""
			try:
				ext = sized_read(OFP_HEADER_LEN-len(message))
			except socket.error, e:
				if e.errno == os.errno.EAGAIN:
					yield ""
					continue
				elif e.errno == os.errno.ECONNRESET:
					break
				else:
					raise
			except KeyboardInterrupt:
				if interactive:
					yield ""
					continue
				else:
					raise
			if len(ext) == 0:
				break
			message += ext
		if len(message) == 0: # normal shutdown
			break
		assert len(message) == OFP_HEADER_LEN, "Read error in openflow message header."
		
		(version,oftype,message_len,x) = parse_ofp_header(bytes(message))
		while len(message) < message_len:
			ext = ""
			try:
				ext = sized_read(message_len-len(message))
			except socket.error, e:
				if e.errno == os.errno.EAGAIN:
					yield ""
					continue
				else:
					raise
			except KeyboardInterrupt:
				if interactive:
					yield ""
					continue
				else:
					raise
			if len(ext) == 0:
				break
			message += ext
		assert len(message) == message_len, "Read error in openflow message body."
		
		yield bytes(message) # freeze the message for ease in dump

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
		units = [0,]*(1 + version/32)
		for v in vset:
			units[v/32] |= 1<<(v%32)
		
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

class OpenflowChannel(Channel):
	version = None
	accept_versions = [4,] # just for default value
	handle = None
	
	def attach(self, stream_socket, autostart=True, interactive=True):
		self._socket = stream_socket
		self._peer = stream_socket.getpeername()
		self.messages = read_message(stream_socket.recv, interactive=interactive)
		if autostart:
			self.start()
	
	def start(self):
		self.send(hello(self.accept_versions))
	
	def loop(self):
		while not self.closed:
			try:
				message = self.recv()
			except StopIteration:
				message = None
			
			if not message:
				break # exit the loop for next loop()
			
			self.handle_proxy(self.handle)(message)
	
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
						0, 0) + ascii_txt)
					self.close()
					raise OfpVersionMismatch(ascii_txt)
		return message
	
	def handle_proxy(self, handle):
		# decorator this allows stacking
		return handle

class AutoEchoChannel(OpenflowChannel):
	def handle_proxy(self, handle):
		def intercept(message):
			if message:
				(version, oftype, length, xid) = parse_ofp_header(message)
				if oftype==2: # ECHO
					self.send(struct.pack("!BBHI", self.version, 3, length, xid)+message[8:])
				else:
					super(AutoEchoChannel, self).handle_proxy(handle)(message)
		return intercept


class CallbackDeadError(Error):
	pass


class CallbackWeakRef(object):
	'''
	Python 3.4 will have WeakMethod, which we need.
	'''
	func = None
	obj = None
	def __init__(self, callback):
		if callback:
			if isinstance(callback, types.MethodType):
				self.obj = weakref.ref(callback.im_self)
				self.name = callback.im_func.func_name
			else:
				self.func = weakref.ref(callback)
	
	def __call__(self):
		if self.func:
			return self.func()
		elif self.obj is not None:
			obj = self.obj()
			if obj is not None:
				return getattr(obj, self.name)


class WeakCallbackCaller(object):
	cbref = lambda self:None
	
	@property
	def callback(self):
		return self.cbref()
	
	@callback.setter
	def callback(self, message_handler):
		if message_handler and self.cbref() is None:
			self.cbref = CallbackWeakRef(message_handler)


class Barrier(WeakCallbackCaller):
	def __init__(self, xid, message_handler=None):
		self.callback = message_handler
		self.xid = xid


class Chunk(WeakCallbackCaller):
	def __init__(self, message_handler):
		self.callback = message_handler


class ControllerChannel(OpenflowChannel, WeakCallbackCaller):
	datapath = None
	auxiliary = None
	seq = None
	
	def send(self, message, **kwargs):
		if self.seq is None:
			self.seq = []
		
		message_handler = kwargs.get("callback")
		if not message_handler:
			message_handler = super(ControllerChannel, self).handle_proxy(self.handle)
		
		(version, oftype, length, xid) = parse_ofp_header(message)
		if (oftype==18 and version==1) or (oftype==20 and version!=1): # OFPT_BARRIER_REQUEST
			self.seq.append(Barrier(xid, message_handler))
		elif self.seq:
			seq_last = self.seq[-1]
			if isinstance(seq_last, Chunk):
				if seq_last.callback != message_handler:
					bxid = hms_xid()
					if self.version==1:
						msg = ofp_header_only(18, version=1, xid=bxid) # OFPT_BARRIER_REQUEST=18 (v1.0)
					else:
						msg = ofp_header_only(20, version=self.version, xid=bxid) # OFPT_BARRIER_REQUEST=20 (v1.1--v1.4)
					super(ControllerChannel, self).send(msg)
					
					self.seq.append(Barrier(bxid))
					self.seq.append(Chunk(message_handler))
			elif isinstance(seq_last, Barrier):
				self.seq.append(Chunk(message_handler))
			else:
				assert False, "seq element must be Chunk or Barrier"
		else:
			if self.callback != message_handler:
				self.seq.append(Chunk(message_handler))
			self.callback = message_handler
		
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
	
	def handle_proxy(self, handle):
		def intercept(message):
			(version, oftype, length, xid) = parse_ofp_header(message)
			if self.seq:
				if (oftype==19 and version==1) or (oftype==21 and version!=1): # is barrier
					chunk_drop = False
					for e in self.seq:
						if isinstance(e, Barrier):
							if e.xid == xid:
								self.seq = self.seq[self.seq.index(e)+1:]
								if e.callback:
									try:
										return e.callback(message, self)
									except CallbackDeadError:
										pass # This should not happen
								return True
							else:
								assert False, "missing barrier(xid=%d) before barrier(xid=%d)" % (e.xid, xid)
						elif isinstance(e, Chunk):
							assert chunk_drop==False, "dropping multiple chunks at a time"
							chunk_drop = True
					assert False, "got unknown barrier xid"
				else:
					e = self.seq[0]
					if isinstance(e, Chunk):
						if e.callback:
							try:
								return e.callback(message, self)
							except CallbackDeadError:
								del(self.seq[0])
			
			if self.callback:
				return self.callback(message, self)
			
			logging.warn("No callback found for handling message %s" % binascii.b2a_hex(message))
		return intercept


class ChildChannel(OpenflowChannel):
	parent = None # must be set
	channels = None # might be set to set()
	def __init__(self, *args, **kwargs):
		super(ChildChannel, self).__init__(*args, **kwargs)
		if self.channels is not None:
			self.channels.add(self)
	
	def close(self):
		super(ChildChannel, self).close()
		if self.channels is not None:
			self.channels.remove(self)
	
	def handle(self, message):
		pass # ignore all messages


class JackinChildChannel(ChildChannel):
	def handle(self, message):
		(version, oftype, length, xid) = parse_ofp_header(message)
		if oftype!=0:
			self.parent.send(message, callback=self.cbfunc)
	
	def cbfunc(self, message, origin_channel):
		self.send(message)


#
# SocketServer.TCPServer, SocketServer.UnixStreamServer
#
class ChannelStreamServer(SocketServer.TCPServer):
	# You can Mixin this class as:
	# serv = type("Serv", (ThreadingTCPServer,ChannelStreamServer), {})(("localhost",6633). StreamHandler)
	allow_reuse_address = True
	channel_cls = None
	def channel_handle(self, request, client_address):
		ch = self.channel_cls(
			socket=request,
			peer=client_address)
		ch.messages = read_message(request.recv)
		ch.start()
		try:
			ch.loop()
		except Exception,e:
			logging.error(str(e), exc_info=True)
		finally:
			ch.close()


#
# SocketServer.UDPServer
#
class ChannelUDPServer(SocketServer.UDPServer):
	allow_reuse_address = True
	channel_cls = None
	def channel_handle(self, request, client_address):
		if self.channels is None:
			self.channels = {}
		
		ch = self.channels.get(client_address)
		if ch is None:
			ch = self.channel_cls(
				sendto=self.sendto,
				peer=client_address)
			self.channels[client_address] = ch
			ch.start()
		
		(data, socket) = request
		f = StringIO.StringIO(data)
		ch.messages = read_message(f.read)
		ch.loop()
		
		if f.tell() < len(data):
			warnings.warn("%d bytes not consumed" % (len(data)-f.tell()))
		ch.messages = None


# handlers
class ChannelHandler(SocketServer.BaseRequestHandler):
	def handle(self):
		self.server.channel_handle(self.request, self.client_address)

class DatagramRequestHandler(ChannelHandler, SocketServer.DatagramRequestHandler):
	pass

class StreamRequestHandler(ChannelHandler, SocketServer.StreamRequestHandler):
	pass

