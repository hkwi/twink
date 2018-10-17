import unittest
import socket
from twink import OpenflowChannel, use_gevent
from twink.ovs import *

from twink.ofp4 import *
import twink.ofp4.parse as p
import twink.ofp4.build as b

@unittest.skipUnless(ofctl, "ovs-ofctl not in PATH")
class OvsTestCase(unittest.TestCase):
	def test_add_flow(self):
		converted = rule2ofp("in_port=1,actions=drop")[0]
		flow = p.parse(converted)
		assert flow.header.type == OFPT_FLOW_MOD
		assert flow.match.oxm_fields
		assert not flow.instructions
		
		converted = rule2ofp("in_port=1,actions=drop", version=1)[0]
		v1msg = struct.unpack_from("!BBHI", converted)
		assert v1msg[0] == 1
		assert v1msg[1] == 14
		
		converted = rule2ofp("in_port=1,actions=drop", version=2)[0]
		v1msg = struct.unpack_from("!BBHI", converted)
		assert v1msg[0] == 2
		assert v1msg[1] == 14
		
		converted = rule2ofp("in_port=1,actions=drop", version=3)[0]
		v1msg = struct.unpack_from("!BBHI", converted)
		assert v1msg[0] == 3
		assert v1msg[1] == 14

if __name__=="__main__":
	import os
	if os.environ.get("USE_GEVENT"):
		use_gevent()
# 	import logging
# 	logging.basicConfig(level=logging.DEBUG)
	unittest.main()
