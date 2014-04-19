import twink
import twink.threading
import threading
import socket
import logging
import signal
import binascii
import unittest

signal_stop = lambda: True
signal.signal(signal.SIGINT, lambda num,fr:signal_stop())

def dummy_handle(message, channel):
	pass
#	print "dummy", binascii.b2a_hex(message), channel

class BasicTestCase(unittest.TestCase):
	def test_io(self):
		global signal_stop
		
		# blocking server
		serv = twink.ChannelStreamServer(("localhost",0), twink.StreamRequestHandler)
		serv.channel_cls = type("TcpChannel",(twink.ControllerChannel, twink.LoggingChannel),{
				"accept_versions":[4,],
				"handle":staticmethod(dummy_handle)})
		serv_thread = threading.Thread(target=serv.serve_forever)
		serv_thread.start()
		
		signal_stop = serv.shutdown
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.connect(serv.server_address)
			ch = type("Client", (twink.OpenflowChannel, twink.LoggingChannel), {"accept_versions":[4,]})()
			ch.attach(s)
			msg = ch.recv()
			assert msg
			version, oftype, l, xid = twink.parse_ofp_header(msg)
			assert version==4
		except:
			logging.error("client error", exc_info=True)
		finally:
			ch.close()
		
		threading.Event().wait(0.1) # wait for serv.loop reads the buffer
		serv.shutdown()
		serv_thread.join()

	def wtest_echo(self):
		global signal_stop
		
		# blocking server
		serv = twink.ChannelStreamServer(("localhost",0), twink.StreamRequestHandler)
		serv.channel_cls = type("Server",(twink.ControllerChannel, twink.AutoEchoChannel, twink.LoggingChannel),{
				"accept_versions":[4,],
				"handle":staticmethod(dummy_handle)})
		serv_thread = threading.Thread(target=serv.serve_forever)
		serv_thread.start()
		
		signal_stop = serv.shutdown
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.connect(serv.server_address)
			ch = type("Client", (twink.OpenflowChannel, twink.LoggingChannel), {"accept_versions":[4,]})()
			ch.attach(s)
			msg = ch.recv()
			assert msg
			version, oftype, l, xid = twink.parse_ofp_header(msg)
			assert version==4
			ch.send(twink.ofp_header_only(2, version=4))
			msg = ch.recv()
			assert msg
			version, oftype, l, xid = twink.parse_ofp_header(msg)
			assert oftype == 3
		except:
			logging.error("client error", exc_info=True)
		finally:
			ch.close()
	
		serv.shutdown()
		serv_thread.join()


	def wtest_interactive(self):
		b = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		b.bind(("localhost",0))
		b.listen(1)
	
		c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		c.connect(b.getsockname())
	
		s,a = b.accept()
	
		server = type("Server", (twink.OpenflowChannel, twink.LoggingChannel), {})()
		client = type("Client", (twink.OpenflowChannel, twink.LoggingChannel), {})()
	
		server.attach(s)
		client.attach(c)
		
		version, oftype, l, xid = twink.parse_ofp_header(server.recv())
		assert oftype==0
		version, oftype, l, xid = twink.parse_ofp_header(client.recv())
		assert oftype==0
		
		client.send(twink.ofp_header_only(2, version=client.version))
		version, oftype, l, xid = twink.parse_ofp_header(server.recv())
		assert oftype==2
		
		server.send(twink.ofp_header_only(3, version=server.version))
		version, oftype, l, xid = twink.parse_ofp_header(client.recv())
		assert oftype==3
	
		server.close()
		client.close()
	
		c.close()
		s.close()
		b.close()

if __name__=="__main__":
	logging.basicConfig(level=logging.WARN)
	unittest.main()
