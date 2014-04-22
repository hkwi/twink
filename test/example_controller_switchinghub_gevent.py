import logging
import twink
import twink.ovs
import twink.ofp4 as ofp4
import twink.ofp4.parse as ofp4parse
import twink.ofp4.build as b
import twink.ofp4.oxm as oxm

class TestChannel(twink.ovs.OvsChannel,
		twink.PortMonitorChannel,
		twink.JackinChannel,
		twink.LoggingChannel):
	accept_versions=[4,]
	init = False
	
	def handle_async(self, message, channel):
		if not self.init:
			return
		
		msg = ofp4parse.parse(message)
		if msg.header.type == ofp4.OFPT_PACKET_IN:
			print(msg)
			in_port = [o for o in oxm.parse_list(msg.match.oxm_fields) if o.oxm_field==oxm.OXM_OF_IN_PORT][0].oxm_value
			src_mac = ":".join(["%02x" % ord(a) for a in msg.data[6:12]])
			channel.add_flow("table=0,priority=2,idle_timeout=300,  dl_src=%s,in_port=%d,  actions=goto_table:1" % (src_mac, in_port))
			channel.add_flow("table=1,priority=2,idle_timeout=300,  dl_dst=%s,  actions=output:%d" % (src_mac, in_port))
			channel.send(b.ofp_packet_out(None, msg.buffer_id, in_port, None, [], None))
			
			print(self.ofctl("dump-flows"))
	
	def handle(self, message, channel):
		msg = ofp4parse.parse(message)
		if msg.header.type == ofp4.OFPT_HELLO:
			self.ofctl("add-group", "group_id=1,type=all,"+",".join(["bucket=output:%d" % port.port_no for port in self.ports]))
			self.add_flow("table=0,priority=1,  actions=controller,goto_table:1")
			self.add_flow("table=1,priority=3,  dl_dst=01:00:00:00:00:00/01:00:00:00:00:00,  actions=group:1")
			self.add_flow("table=1,priority=1,  actions=group:1")
			self.init = True


if __name__=="__main__":
	logging.basicConfig(level=logging.DEBUG)
	globals().update(twink.use_gevent())
	tcpserv = twink.StreamServer(("0.0.0.0", 6653))
	tcpserv.channel_cls = TestChannel
	twink.serve_forever(tcpserv)

