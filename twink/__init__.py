import datetime
import time
import weakref
import struct
import types
import logging
import binascii

def parse_ofp_header(message):
	'''
	@return (version, oftype, message_len, xid)
	'''
	return struct.unpack_from("!BBHI", message)

def read_message(sized_read):
	'''
	sized_read : function of `bytestr = func(size)`
	'''
	OFP_HEADER_LEN = 8
	message = bytearray()
	while len(message) < OFP_HEADER_LEN:
		try:
			ext = sized_read(OFP_HEADER_LEN-len(message))
		except:
			ext = ""
		if len(ext) == 0:
			break
		message += ext
	if len(message) == 0: # normal shutdown
		return None
	assert len(message) == OFP_HEADER_LEN, "Read error in openflow message header."
	
	(version,oftype,message_len,x) = parse_ofp_header(bytes(message))
	while len(message) < message_len:
		ext = sized_read(message_len-len(message))
		if len(ext) == 0:
			break
		message += ext
	assert len(message) == message_len, "Read error in openflow message body."
	
	return bytes(message) # freeze the message for ease in dump

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
				version = [1.0, 1.1, 1.2, 1.3].index(version) + 1
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


class Error(Exception):
	pass


class OpenflowError(Error):
	def __init__(self, message):
		vals = list(struct.unpack_from("!BBHIHH", message))
		vals.append(binascii.b2a_hex(message[struct.calcsize("!BBHIHH"):]))
		o = zip("version oftype length xid etype ecode payload".split(), vals)
		super(OpenflowError, self).__init__("OFPT_ERROR %s" % repr(o))
		self.message = message


class Channel(object):
	ctime = None
	version = None # The negotiated openflow version
	accept_versions = None
	
	def __init__(self, *args, **kwargs):
		self.ctime = time.time()
	
	@property
	def closed(self):
		return False
	
	def close(self):
		pass
	
	def send(self, message, message_handler):
		'''
		Interface for application side.
		
		message_handler is a function or a bound method. The signature is
		func(message, channel). message_handler may raise CallbackDeadError
		if callback is not available any further.
		'''
		pass
	
	def on_message(self, message):
		'''
		Interface for inner connection side
		'''
		(version, oftype, length, xid) = parse_ofp_header(message)
		if oftype==2: # ECHO
			self.send(struct.pack("!BBHI", self.version, 3, 8+length, xid)+message, None)
			return True
		elif oftype==0: # HELLO
			accept_versions = ofp_version_normalize(self.accept_versions)
			if not accept_versions:
				accept_versions = set([1,])
			cross_versions = parse_hello(message) & accept_versions
			if cross_versions:
				self.version = max(cross_versions)
			else:
				print accept_versions
				ascii_txt = "Accept versions: %s" % ["- 1.0 1.1 1.2 1.3".split()[x] for x in list(accept_versions)]
				self.send(struct.pack("!BBHIHH", max(accept_versions), 1,
					struct.calcsize("!BBHIHH")+len(ascii_txt), hms_xid(),
					0, 0) + ascii_txt, None)
				self.close()
				return True


class LoggingChannel(Channel):
	def __init__(self, *args, **kwargs):
		super(LoggingChannel, self).__init__(*args, **kwargs)
		self.channel_log_name = kwargs.get("channel_log_name", "channel")
		self.send_log_name = kwargs.get("send_log_name", "send")
		self.recv_log_name = kwargs.get("recv_log_name", "recv")
		
		logging.getLogger(self.channel_log_name).info("%s open" % self)
	
	def send(self, message, message_handler):
		logging.getLogger(self.send_log_name).info("%s %s" % (self, binascii.b2a_hex(message)))
		return super(LoggingChannel, self).send(message, message_handler)
	
	def on_message(self, message):
		logging.getLogger(self.recv_log_name).info("%s %s" % (self, binascii.b2a_hex(message)))
		return super(LoggingChannel, self).on_message(message)
	
	def close(self):
		logging.getLogger(self.channel_log_name).info("%s close" % self)
		return super(LoggingChannel, self).close()


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


class ControllerChannel(Channel, WeakCallbackCaller):
	datapath = None
	auxiliary = None
	
	def __init__(self, *args, **kwargs):
		super(ControllerChannel, self).__init__(*args, **kwargs)
		self.seq = []
	
	def send(self, message, message_handler):
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
						msg = ofp_header_only(20, version=self.version, xid=bxid) # OFPT_BARRIER_REQUEST=20 (v1.3)
					super(ControllerChannel, self).send(msg, None)
					self.direct_send(msg)
					
					self.seq.append(Barrier(bxid))
					self.seq.append(Chunk(message_handler))
			elif isinstance(seq_last, Barrier):
				self.seq.append(Chunk(callback))
			else:
				assert False, "seq element must be Chunk or Barrier"
		else:
			if self.callback != message_handler:
				self.seq.append(Chunk(message_handler))
			self.callback = message_handler
		
		super(ControllerChannel, self).send(message, message_handler)
		self.direct_send(message)
	
	def on_message(self, message):
		(version, oftype, length, xid) = parse_ofp_header(message)
		if oftype==6: # FEATURES_REPLY
			if self.version < 4:
				(self.datapath,) = struct.unpack_from("!Q", message, offset=8)
			else:
				(self.datapath,_1,_2,self.auxiliary) = struct.unpack_from("!QIBB", message, offset=8)
		
		if super(ControllerChannel, self).on_message(message):
			return True
		
		if self.seq:
			if (oftype==19 and version==1) or (oftype==21 and version!=1): # is barrier
				chunk_drop = False
				for e in self.seq:
					if isinstance(e, Barrier):
						if e.xid == xid:
							self.seq = self.seq[self.seq.index(e)+1:]
							if e.callback:
								try:
									e.callback(message, self)
								except CallbackDeadError:
									pass # This should not happen
							return
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


def easy_message_handler(message, channel):
	(version, oftype, length, xid) = parse_ofp_header(message)
	if oftype==10: # PACKET_IN
		(buffer_id,) = struct.unpack_from("!I", message, offset=8)
		# Some switch use PACKET_IN as ECHO_REQUEST, so responding to it with action "DROP"
		if version==1:
			msg = struct.pack("!IHH", buffer_id, 0xffff, 0) # OFPP_NONE=0xffff
		else:
			msg = struct.pack("!IIHHI", buffer_id, 0xffffffff, 0, 0, 0) # OFPP_CONTROLLER=0xffffffff
		channel.send(struct.pack("!BBHI", version, 13, 8+len(msg), xid)+msg, None) # OFPT_PACKET_OUT=13
		return True
