from __future__ import absolute_import
from . import *
import logging
import SocketServer

# serv = SocketServer.ThreadingTCPServer(("0.0.0.0", 6633),
# 	type("Handler", (SocketServer.StreamRequestHandler, ControllerChannel,LoggingChannel,StandardChannel),{"accept_versions":[4,]}),
# 	message_handler=handle_message)

if __name__ == "__main__":
	logging.basicConfig(level=logging.DEBUG)
	serv = ChannelStreamServer(("0.0.0.0", 6633), StreamRequestHandler)
	serv.channel_cls = type("TcpChannel",(ControllerChannel, AutoEchoChannel, LoggingChannel),{"accept_versions":[4,]})
	serv.serve_forever()

# serv = ChannelUDPServer(("0.0.0.0", 6633), DatagramRequestHandler)
# serv.channel_cls = type("UdpChannel",(ControllerChannel, LoggingChannel),{"accept_versions":[4,]})

# serv = type("DatagramServer", (ChannelUDPServer, ThreadingUDPServer), {
# 		"channel_cls": type("SChannel",(SwitchChannel,LoggingChannel,StandardChannel),{"accept_versions":[4,]})
# 	})(("0.0.0.0", 6633), DatagramRequestHandler)

##
## INTERACTIVE MODE
##

# import socket
# from twink2 import *
# s=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# s.connect(("localhost",6633))
# ch=type("TcpChannel",(AutoEchoChannel, LoggingChannel),{"accept_versions":[4,]})()
# ch.attach(s)
# ch.recv()
# 
# 
# import socket
# from twink2 import *
# s=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
# s.connect("unknown-c0.monitor")
# ch=type("TcpChannel",(AutoEchoChannel, LoggingChannel),{"accept_versions":[4,]})()
# ch.attach(s)
# ch.recv()
# ch.send(ofp_header_only(2, version=4))
# 
# 
# import socket
# from twink2 import *
# s2=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# s2.bind(("localhost",6633))
# s2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
# s2.listen(1)
# s,a=s2.accept()
# ch=type("TcpChannel",(ControllerChannel, AutoEchoChannel, LoggingChannel),{"accept_versions":[4,]})()
# ch.attach(s)
# ch.recv()
