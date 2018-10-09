import twink
import binascii
import unittest
import socket
import twink.ofp4 as ofp4
import twink.ofp4.parse as p
import twink.ofp4.build as b

class TestChannel(twink.ControllerChannel):
	def __init__(self, default_callback=lambda *a:None, **kwargs):
		self.handle = default_callback
		super(TestChannel, self).__init__(**kwargs)

class ParallelTest(unittest.TestCase):
	def setUp(self):
		self.sc, self.ss = socket.socketpair()
	
	def tearDown(self):
		self.sc.close()
		self.ss.close()
	
	def test_barrier_1(self):
		results = []
		
		sc, ss = self.sc, self.ss
		serv = TestChannel(socket=ss)
		serv.start()
		sc.send(sc.recv(1024)) # echo back HELLO
		serv.recv() # consume HELLO
		
		cb1 = lambda *a: results.append(("cb1", a))
		cb2 = lambda *a: results.append(("cb2", a))
		
		echo = b.ofp_header(version=4,type=2,xid=1,length=8)
		serv.send(echo, callback=cb1)
		pkt = sc.recv(1024)
		b1 = p.parse(pkt[:8])
		assert b1.header.type == ofp4.OFPT_BARRIER_REQUEST
		assert echo == pkt[8:], pkt[8:]

		echo = b.ofp_header(version=4,type=2,xid=2,length=8)
		serv.send(echo, callback=cb2)
		pkt = sc.recv(1024)
		b2 = p.parse(pkt[:8])
		assert b2.header.type == ofp4.OFPT_BARRIER_REQUEST
		assert echo == pkt[8:], pkt[8:]

		echo = b.ofp_header(version=4,type=2,xid=3,length=8)
		serv.send(echo, callback=cb1)
		pkt = sc.recv(1024)
		b3 = p.parse(pkt[:8])
		assert b3.header.type == ofp4.OFPT_BARRIER_REQUEST
		assert echo == pkt[8:], pkt[8:]

		sc.send(b.ofp_header(version=4,
			type=ofp4.OFPT_BARRIER_REPLY,
			xid=b1.header.xid,
			length=8))
		sc.send(b.ofp_header(version=4,type=3,xid=1,length=8))
		sc.send(b.ofp_header(version=4,
			type=ofp4.OFPT_BARRIER_REPLY,
			xid=b2.header.xid,
			length=8))
		sc.send(b.ofp_header(version=4,type=3,xid=2,length=8))
		sc.send(b.ofp_header(version=4,
			type=ofp4.OFPT_BARRIER_REPLY,
			xid=b3.header.xid,
			length=8))
		sc.send(b.ofp_header(version=4,type=3,xid=3,length=8))
		sc.close()

		serv.loop()
		assert [r[0] for r in results] == ["cb1", "cb2", "cb1"], [r[0] for r in results]


	def test_barrier_2(self):
		results = []
		
		sc, ss = self.sc, self.ss
		serv = TestChannel(socket=ss,
			default_callback=lambda *a: results.append(("cb1", a)))
		serv.start()
		sc.send(sc.recv(1024)) # echo back HELLO
		serv.recv() # consume HELLO

		cb1 = None
		cb2 = lambda *a: results.append(("cb2", a))

		echo = b.ofp_header(version=4,type=2,xid=1,length=8)
		serv.send(echo, callback=cb1)
		pkt = sc.recv(1024)
		assert pkt==echo, pkt

		echo = b.ofp_header(version=4,type=2,xid=2,length=8)
		serv.send(echo, callback=cb2)
		pkt = sc.recv(1024)
		b1 = p.parse(pkt[:8])
		assert b1.header.type == ofp4.OFPT_BARRIER_REQUEST
		assert echo == pkt[8:], pkt[8:]

		echo = b.ofp_header(version=4,type=2,xid=3,length=8)
		serv.send(echo, callback=cb1)
		pkt = sc.recv(1024)
		b2 = p.parse(pkt[:8])
		assert b2.header.type == ofp4.OFPT_BARRIER_REQUEST
		assert echo == pkt[8:], pkt[8:]

		sc.send(b.ofp_header(version=4,type=3,xid=1,length=8))
		sc.send(b.ofp_header(version=4,
			type=ofp4.OFPT_BARRIER_REPLY,
			xid=b1.header.xid,
			length=8))
		sc.send(b.ofp_header(version=4,type=3,xid=2,length=8))
		sc.send(b.ofp_header(version=4,
			type=ofp4.OFPT_BARRIER_REPLY,
			xid=b2.header.xid,
			length=8))
		sc.send(b.ofp_header(version=4,type=3,xid=3,length=8))
		sc.close()

		serv.loop()
		assert [r[0] for r in results
			if p.parse(r[1][0]).header.type!=ofp4.OFPT_BARRIER_REPLY] == ["cb1", "cb2", "cb1"], results

if __name__=="__main__":
	import os
	if os.environ.get("USE_GEVENT"):
		twink.use_gevent()
	unittest.main()
