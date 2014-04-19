import twink
import twink.gevent
import gevent.socket
import SocketServer
import logging
import gevent

main_ev = gevent.event.Event()

def server_handle(message, channel):
	assert message
	version, oftype, l, xid = twink.parse_ofp_header(message)
	if oftype == 0:
		msg = channel.echo()
		if msg:
			version, oftype, l, xid = twink.parse_ofp_header(msg)
			channel.close()
			gevent.spawn(lambda:main_ev.set())

def client_handle(message, channel):
	pass
#	print len(message), channel

def test_io():
	global main_ev
	main_ev.clear()
	
	logging.basicConfig(level=logging.DEBUG)
	class TestTcpServer(twink.ChannelStreamServer, SocketServer.ThreadingTCPServer):
		# TCPServer is not a child of new style object, so don't use type()
		pass
	serv = twink.gevent.ChannelStreamServer(("127.0.0.1", 0), spawn=10)
	serv.channel_cls = type("TcpChannel", (
		twink.gevent.ParallelMixin,
		twink.SyncChannel,
		twink.ControllerChannel,
		twink.AutoEchoChannel,
		twink.LoggingChannel
		),{
			"accept_versions":[4,],
			"handle":staticmethod(server_handle)})
	serv.start()
	
	try:
		s = gevent.socket.socket(gevent.socket.AF_INET, gevent.socket.SOCK_STREAM)
		s.connect(serv.address)
		ch = type("Client", (
		twink.gevent.ParallelMixin,
		twink.AutoEchoChannel,
		twink.LoggingChannel
		),{
			"accept_versions":[4,],
			"handle":staticmethod(client_handle)})()
		ch.attach(s)
		ch.loop()
		
		main_ev.wait(timeout=4)
	except:
		logging.error("client error", exc_info=True)
	finally:
		ch.close()
	
	serv.stop()

if __name__=="__main__":
	logging.basicConfig(level=logging.WARN)
	test_io()
