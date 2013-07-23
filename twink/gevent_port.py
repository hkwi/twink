from __future__ import absolute_import
import struct
import logging
from gevent.server import StreamServer, DatagramServer
from twink import parse_ofp_header, Channel, ControllerChannel, LoggingChannel, default_message_handler, hello_handler, ofp_header_only
from twink.gevent import StreamChannel, DatagramChannel, StreamHandler, OpenflowDatagramServer, serve_forever

class PortMonitorChannel(Channel):
	version = None
	ports = []
	initial_set = None
	xid = None
	
	def set_ports(self, version, ports):
		self.initial_set = True
		self.version = version
		self.ports = ports
	
	def partial_set_ports(self, version, ports, xid, has_more):
		if self.initial_set:
			return
		
		if self.xid is None:
			self.xid = xid
		if self.xid != xid:
			return
		
		if self.version is None:
			self.version = version
		assert self.version == version
		
		self.ports.extend(ports)
		if not has_more:
			self.set_ports(version, self.ports)
	
	def update_port(self, reason, port):
		hit = [x for x in self.ports if x[0]==port[0]]
		if reason==0: # ADD
			assert not hit
			self.ports.append(port)
		elif reason==1: # DELETE
			assert hit
			self.ports.remove(hit[0])
		elif reason==2: # MODIFY
			assert hit
			self.ports.remove(hit[0])
			self.ports.append(port)
		else:
			assert False, "unknown reason %d" % reason
	
	def index(self):
		if self.version==1:
			return '''port_no hw_addr name
				config state
				curr advertised supported peer'''.split()
		else:
			return '''port_no hw_addr name
				config state
				curr advertised supported peer
				curr_speed max_speed'''.split()

def port_monitor(message, channel):
	if not isinstance(channel, PortMonitorChannel):
		return False
	
	ofp_port = "!H6s16sIIIIII" # ofp_port v1.0
	if channel.version != 1:
		ofp_port = "!I4x6s2x16sIIIIIIII"
	
	(version, oftype, length, xid) = parse_ofp_header(message)
	if oftype==0: # HELLO
		hello_handler(message, channel)
		if channel.version == 4:
			fmt = "!BBHIHH4x"
			assert struct.calcsize(fmt)==16, "openflow 1.3 spec"
			channel.send(struct.pack(fmt, channel.version, 
				18, # MULTIPART_REQUEST
				16, # struct.calcsize(fmt)
				hms_xid(), 
				13, # PORT_DESC
				0, # not REQ_MORE
				), None)
		else:
			channel.send(ofp_header_only(5), None) # FEATURES_REQUEST
	elif oftype==19 and channel.version == 4: # MULTIPART_REPLY
		(mptype, flags) = struct.unpack_from("!HH4x", message, offset=8)
		if mptype==13:
			offset = 16
			ports = []
			while offset < length:
				ports.append(struct.unpack(message, ofp_port, offset=offset))
				offset += struct.calcsize(ofp_port)
			channel.partial_set_ports(version, ports, xid, flags&1)
	elif oftype==6: # FEATURES_REPLY
		if channel.version != 4:
			fmt = "!BBHIQIB3x"
			assert struct.calcsize(fmt) % 8 == 0
			offset = struct.calcsize(fmt+"II")
			ports = []
			while offset < length:
				ports.append(struct.unpack_from(ofp_port, message, offset=offset))
				offset += struct.calcsize(ofp_port)
			channel.set_ports(version, ports)
	elif oftype==12: # PORT_STATUS
		p = struct.unpack_from("!B7x"+ofp_port[1:], message, offset=8)
		channel.update_port(p[0], p[1:])

if __name__=="__main__":
	class BaseChannel(PortMonitorChannel):
		def set_ports(self, version, ports):
			super(BaseChannel, self).set_ports(version, ports)
			print ports
		
		def update_port(self, reason, port):
			super(BaseChannel, self).update_port(reason, port)
			print self.ports
	
	def message_handler(message, channel):
		ret = default_message_handler(message, channel)
		if not ret:
			ret = port_monitor(message, channel)
		return ret
	
	logging.basicConfig(level=logging.DEBUG)
	address = ("0.0.0.0", 6633)
	appconf = {"accept_versions":[1], "message_handler":message_handler}
	tcpserv = StreamServer(address, handle=StreamHandler(
		channel_cls=type("SChannel", (StreamChannel, BaseChannel, ControllerChannel, LoggingChannel), {}),
		**appconf))
	udpserv = OpenflowDatagramServer(address,
		channel_cls=type("DChannel", (DatagramChannel, BaseChannel, ControllerChannel, LoggingChannel), {}),
		**appconf)
	serve_forever(tcpserv, udpserv)
