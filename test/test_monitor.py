import twink
import logging
import signal
import binascii
import unittest
import twink.ofp4 as ofp4
import twink.ofp4.build as b
import twink.ofp4.parse as p

context = {}

signal.signal(signal.SIGINT, lambda num,fr:context["stop"]())

class TestChannel(twink.MonitorChannel, twink.LoggingChannel):
	accept_versions=[4,]
	def handle(self, msg, ch):
		context["channel"] = ch

	def loop(self):
		try:
			super(TestChannel, self).loop()
		except Exception as e:
			context["loop_error"] = e

class MonitorTestCase(unittest.TestCase):
	def setUp(self):
		context["loop_error"] = None

	def test_io(self):
		def handle(msg, ch):
			context["channel"] = ch

		# blocking server
		serv = twink.StreamServer(("localhost",0))
		serv.channel_cls = TestChannel
		serv_thread = twink.sched.spawn(serv.start)
		
		context["stop"] = serv.stop
		ch = None

		socket = twink.sched.socket
		s = socket.create_connection(serv.server_address[:2])
		ch = type("Client", (twink.OpenflowChannel, twink.LoggingChannel), {"accept_versions":[4,]})()
		ch.attach(s)
		msg = ch.recv()
		assert msg
		version, oftype, l, xid = twink.parse_ofp_header(msg)
		assert version==4

		twink.sched.Event().wait(0.3)

		mon = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		mon.connect("unknown-%x.monitor" % id(context["channel"]))
		m = type("Client", (twink.OpenflowChannel, twink.LoggingChannel), {"accept_versions":[4,]})()
		m.attach(mon)
		assert p.parse(m.recv()).header.type == ofp4.OFPT_HELLO
		
		msg = b.ofp_header(version=4, type=2, xid=2, length=8)
		ch.send(msg)
		assert m.recv() == msg
		mon.close()
		ch.send(b.ofp_header(version=4, type=2, xid=3, length=8))
		assert m.recv() == b""
	
		ch.close()

		twink.sched.Event().wait(0.1) # wait for serv.loop reads the buffer
		serv.stop()
		serv_thread.join()

		assert context["loop_error"] is None, context["loop_error"]


if __name__=="__main__":
	import os
	if os.environ.get("USE_GEVENT"):
		twink.use_gevent()
	logging.basicConfig(level=logging.WARN)
	unittest.main()

