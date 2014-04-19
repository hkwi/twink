import unittest
import socket
import threading
from twink import OpenflowChannel
from twink.threading import ParallelMixin
from twink.ovs import *

from twink.ofp4 import *
import twink.ofp4.parse as p
import twink.ofp4.build as b

class OvsTestCase(unittest.TestCase):
	def test_add_flow(self):
		converted = rule2ofp("in_port=1,actions=drop")
		flow = p.parse(converted)
		assert flow.header.type == OFPT_FLOW_MOD
		assert flow.match.oxm_fields
		assert not flow.instructions
		
		converted = rule2ofp("in_port=1,actions=drop", version=1)
		v1msg = struct.unpack_from("!BBHI", converted)
		assert v1msg[0] == 1
		assert v1msg[1] == 14
		
		converted = rule2ofp("in_port=1,actions=drop", version=2)
		v1msg = struct.unpack_from("!BBHI", converted)
		assert v1msg[0] == 2
		assert v1msg[1] == 14
		
		converted = rule2ofp("in_port=1,actions=drop", version=3)
		v1msg = struct.unpack_from("!BBHI", converted)
		assert v1msg[0] == 3
		assert v1msg[1] == 14

if __name__=="__main__":
# 	import logging
# 	logging.basicConfig(level=logging.DEBUG)
	unittest.main()

