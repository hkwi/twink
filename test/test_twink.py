import unittest
import struct
import twink

def timeout_pause(func):
	def wrap(*args, **kwargs):
		try:
			return func(*args, **kwargs)
		except twink.sched.socket.timeout:
			return b""
	return wrap

class ChannelTestCase(unittest.TestCase):
	def test_pair1(self):
		a,b = twink.sched.socket.socketpair()
		
		x = twink.Channel(socket=a)
		y = twink.Channel(socket=b)
		
		x.send(struct.pack("!BBHI", 4, 0, 8, 0))
		x.close()
		
		assert len(y._recv(8192)) == 8
		assert len(y._recv(8192)) == 0
		
		y.close()

	def test_pair2(self):
		a,b = twink.sched.socket.socketpair()
		
		x = twink.Channel(socket=a)
		y = twink.Channel(socket=b, read_wrap=timeout_pause)
		
		x.send(struct.pack("!BBHI", 4, 0, 8, 0))
		
		assert len(y._recv(8192)) == 8
		assert len(y._recv(8192)) == 0
		
		x.close()
		y.close()

	def test_pair3(self):
		a,b = twink.sched.socket.socketpair()
		
		x = twink.Channel(socket=a)
		y = twink.Channel(socket=b)
		
		x.send(struct.pack("!BBHI", 4, 0, 8, 0))
		
		with twink.ReadWrapper(y, timeout_pause):
			assert len(y._recv(8192)) == 8
			assert len(y._recv(8192)) == 0
		
		x.close()
		y.close()


class OpenflowBaseChannelTestCase(unittest.TestCase):
	def test_pair1(self):
		a,b = twink.sched.socket.socketpair()
		
		x = twink.OpenflowBaseChannel(socket=a)
		y = twink.OpenflowBaseChannel(socket=b)
		
		x.send(struct.pack("!BBHI", 4, 0, 8, 0))
		x.close()
		
		assert len(y.recv()) == 8
		assert len(y.recv()) == 0
		
		x.close()
		y.close()

	def test_pair2(self):
		a,b = twink.sched.socket.socketpair()
		
		x = twink.OpenflowBaseChannel(socket=a)
		y = twink.OpenflowBaseChannel(socket=b, read_wrap=timeout_pause)
		
		x.send(struct.pack("!BBHI", 4, 0, 8, 0))
		
		assert len(y.recv()) == 8
		assert len(y.recv()) == 0
		
		x.close()
		y.close()

	def test_pair3(self):
		a,b = twink.sched.socket.socketpair()
		
		x = twink.OpenflowBaseChannel(socket=a)
		y = twink.OpenflowBaseChannel(socket=b)
		
		x.send(struct.pack("!BBHI", 4, 0, 8, 0))
		
		with twink.ReadWrapper(y, timeout_pause):
			assert len(y.recv()) == 8
			assert len(y.recv()) == 0
		
		x.close()
		y.close()


class OpenflowChannelTestCase(unittest.TestCase):
	def test_pair1(self):
		a,b = twink.sched.socket.socketpair()
		
		x = twink.OpenflowChannel()
		y = twink.OpenflowChannel()
		
		x.attach(a)
		y.attach(b)
		
		with twink.ReadWrapper(y, timeout_pause):
			msg = y.recv()
			assert y.version == 4
			assert len(msg) > 0
			p = struct.unpack_from("!BBHI", msg)
			assert p[1] == 0 # HELLO
			assert len(y.recv()) == 0
		
		x.close()
		y.close()


class TypesCapture(object):
	def __init__(self):
		self.types = []
	
	def __call__(self, message, channel):
		p = twink.parse_ofp_header(message)
		self.types.append(p[1])

class AutoEchoChannelTestCase(unittest.TestCase):
	def test_pair1(self):
		a,b = twink.sched.socket.socketpair()
		
		x = twink.AutoEchoChannel()
		x.handle = TypesCapture()
		y = twink.OpenflowChannel()
		
		x.attach(a)
		y.attach(b)
		
		y.recv()
		y.send(twink.ofp_header_only(2, version=y.version))
		y.send(twink.ofp_header_only(5, version=y.version))
		
		with twink.ReadWrapper(x, timeout_pause):
			x.loop()
		
		assert 0 in x.handle.types
		assert 5 in x.handle.types
		
		assert twink.parse_ofp_header(y.recv())[1] == 3
		x.close()
		y.close()


def auto_echo(msg, ch):
	p = twink.parse_ofp_header(msg)
	if p[1] == 2:
		ch.send(twink.ofp_header_only(3, version=ch.version, xid=p[3]))

class OpenflowServerChannelTestCase(unittest.TestCase):
	def test_pair1(self):
		a,b = twink.sched.socket.socketpair()
		
		x = twink.OpenflowChannel(socket=a)
		y = type("OpenflowServerChannelTestCaseY", (twink.OpenflowServerChannel,), {})(socket=b)
		y.handle = auto_echo
		
		x.start()
		y.start()
		yth = twink.sched.spawn(y.loop)
		
		assert len(x.recv()) > 0
		assert x.version == 4
		x.send(twink.ofp_header_only(2, version=x.version))
		p = twink.parse_ofp_header(x.recv())
		assert p[1] == 3
		
		x.close()
		y.close()
		yth.join(0.5)


class BarrieredReply(object):
	def __init__(self):
		self.msgs = []
	
	def __call__(self, message, channel):
		p = twink.parse_ofp_header(message)
		if p[1] == 20:
			for msg in self.msgs:
				q = twink.parse_ofp_header(msg)
				if q[1] == 2:
					channel.send(twink.ofp_header_only(3, version=channel.version, xid=q[3]))
			channel.send(twink.ofp_header_only(21, version=channel.version, xid=p[3]))
			self.msgs = []
		else:
			self.msgs.append(message)


class ControllerChannelTestCase2(unittest.TestCase):
	def test_pair1(self):
		a,b = twink.sched.socket.socketpair()
		
		x = type("ControllerChannelTestCaseX", (twink.OpenflowServerChannel,twink.LoggingChannel), {})(socket=a)
		x.handle = BarrieredReply()
		y = twink.ControllerChannel(socket=b)
		y.handle = lambda msg, ch: None
		
		x.start()
		y.start()
		xth = twink.sched.spawn(x.loop)
		
		result = dict(flag1=0, flag2=0)
		def cb1(message, ch):
			result["flag1"] += 1
		
		flag2 = 0
		def cb2(message, ch):
			result["flag2"] += 1
		
		y.recv()
		y.send(twink.ofp_header_only(2, version=y.version), callback=cb1)
		y.send(twink.ofp_header_only(2, version=y.version), callback=cb2)
		y.send(twink.ofp_header_only(20, version=y.version))
		with twink.ReadWrapper(y, timeout_pause):
			y.loop()
		
		assert result["flag1"] == 1
		assert result["flag2"] == 1
		
		x.close()
		y.close()
		
		xth.join(0.5)

class StreamServerTestCase(unittest.TestCase):
	def test_server(self):
		s = twink.sched.socket.socket(twink.sched.socket.AF_INET, twink.sched.socket.SOCK_STREAM)
		s.bind(("127.0.0.1", 0))
		serv = type("S", (twink.StreamServer,), dict(
			channel_cls=type("Sc", (twink.AutoEchoChannel, twink.LoggingChannel), 
				dict(handle=staticmethod(lambda a,b:None)))))(s)
		serv.start()
		
		c = twink.sched.socket.socket(twink.sched.socket.AF_INET, twink.sched.socket.SOCK_STREAM)
		c.connect(s.getsockname())
		ch = type("Cc", (twink.OpenflowChannel, twink.LoggingChannel), {})()
		ch.attach(c)
		x = ch.recv()
		assert ch.version
		ch.send(twink.ofp_header_only(2, version=ch.version))
		assert twink.parse_ofp_header(ch.recv())[1] == 3
		ch.close()
		serv.stop()

class SampleApp(object):
	def __call__(self, message, channel):
		hdr = twink.parse_ofp_header(message)
		if hdr[1] == 0:
			channel.send(twink.ofp_header_only(2, version=channel.version))
			channel.send(twink.ofp_header_only(20, version=channel.version))
		elif hdr[1] == 21:
			channel.close()

class ControllerChannelTestCase(unittest.TestCase):
	def test_pair1(self):
		a,b = twink.sched.socket.socketpair()
		
		x = type("C", (twink.ControllerChannel, twink.OpenflowServerChannel), {})(socket=a)
		x.handle = SampleApp()
		y = twink.OpenflowChannel(socket=b)
		
		x.start()
		xth = twink.sched.spawn(x.loop)
		
		y.start()
		with twink.ReadWrapper(y, timeout_pause):
			msgs = [m for m in y]
		
		assert len(msgs) == 3
		
		x.close()
		y.close()
		
		xth.join(0.5)

class SyncChannelTestCase(unittest.TestCase):
	def switch_reactor(self, message, channel):
		import twink.ofp4.parse as ofp4p
		import twink.ofp4.build as ofp4b
		msg = ofp4p.parse(message)
		if msg.header.type==18 and msg.type==13:
			channel.send(ofp4b.ofp_multipart_reply(ofp4b.ofp_header(4, 19, None, msg.header.xid),
				13, 0, ()))
	
	def controller(self, message, channel):
		import twink.ofp4.parse as ofp4p
		import twink.ofp4.build as ofp4b
		msg = ofp4p.parse(message)
		if msg.header.type==0:
			assert len(channel.ports) == 0
			channel.close()
	
	def test_pair1(self):
		a,b = twink.sched.socket.socketpair()
		
		x = twink.PortMonitorChannel(socket=a)
		x.handle = self.controller
		y = type("SyncChannelTestCaseY", (twink.OpenflowServerChannel,), {})(socket=b)
		y.handle = self.switch_reactor
		
		x.start()
		y.start()
		xl = twink.sched.spawn(x.loop)
		yl = twink.sched.spawn(y.loop)
		
		xl.join()
		yl.join()
		x.close()
		y.close()


if __name__=="__main__":
#	import logging
#	logging.basicConfig(level=logging.DEBUG)
	import os
	if os.environ.get("USE_GEVENT"):
		twink.use_gevent()
	unittest.main()
