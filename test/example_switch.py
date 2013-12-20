import binascii
import twink
import twink.gevent
from twink.ofp4 import *
import twink.ofp4.parse as p
import twink.ofp4.build as b
import twink.ofp4.oxm as oxm

import logging
logging.basicConfig(level=logging.DEBUG)

def switch_proc(message, channel):
	msg = p.parse(message)
	if msg.header.type == OFPT_FEATURES_REQUEST:
		channel.send(b.ofp_switch_features(b.ofp_header(4, OFPT_FEATURES_REPLY, 0, msg.header.xid), 1, 2, 3, 0, 0xF))
	elif msg.header.type == OFPT_GET_CONFIG_REQUEST:
		channel.send(b.ofp_switch_config(b.ofp_header(4, OFPT_GET_CONFIG_REPLY, 0, msg.header.xid), 0, 0xffe5))
	elif msg.header.type == OFPT_MULTIPART_REQUEST:
		if msg.type == OFPMP_FLOW:
			channel.send(b.ofp_multipart_reply(b.ofp_header(4, OFPT_MULTIPART_REPLY, 0, msg.header.xid),
				msg.type, 0, [
					b.ofp_flow_stats(None, 0, 10, 20, 30, 40, 50, 0, 1, 2, 3,
						b.ofp_match(None, None, "".join([
							oxm.build(None, oxm.OXM_OF_IN_PORT, None, None, 222),
							oxm.build(None, oxm.OXM_OF_ETH_SRC, None, None, binascii.a2b_hex("00112233"))])),
						[b.ofp_instruction_actions(OFPIT_APPLY_ACTIONS, None, [
							b.ofp_action_output(None, None, 1111, OFPCML_MAX)]),
						]),]))
	# should be more

##
## Open vSwitch style openflow switch
##
## TCP server openflow switch
##
serv = twink.gevent.ChannelStreamServer(("0.0.0.0", 6653), spawn=100)
serv.channel_cls = type("Switch", (
	twink.AutoEchoChannel,
	twink.LoggingChannel), {
		"accept_versions": [4,],
		"handle": staticmethod(switch_proc)
	})
serv.serve_forever()

##
## normal openflow switch
##
## TCP client openflow switch
##
# import socket
# s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# s.connect(("localhost", 6653))
# ch = type("Switch", (
# 	twink.AutoEchoChannel,
# 	twink.LoggingChannel), {
# 		"accept_versions": [4,],
# 		"handle": staticmethod(switch_proc)
# 	})()
# ch.attach(s)
# ch.loop()

