from __future__ import absolute_import
from . import *
from . import parse as p
from . import build as b
from . import oxm

msg = p.parse(b.ofp_hello(None, []))
assert msg.elements == []
msg = p.parse(b.ofp_hello(None, [b.ofp_hello_elem_versionbitmap(None, None, [1,2,3,4,5])]))
assert msg.elements[0].bitmaps == (1,2,3,4,5)

msg = p.parse(b.ofp_error_msg(None, OFPET_BAD_REQUEST, OFPBRC_BAD_VERSION, None))
assert msg.type == OFPET_BAD_REQUEST
assert msg.code == OFPBRC_BAD_VERSION

msg = p.parse(b.ofp_switch_features(None, 0x4649, 300, 23, 0, 0))
assert msg.datapath_id == 0x4649
assert msg.n_buffers == 300
assert msg.n_tables == 23
assert msg.auxiliary_id == 0
assert msg.capabilities == 0

msg = p.parse(b.ofp_switch_config(b.ofp_header(None, OFPT_SET_CONFIG, None, None), OFPC_FRAG_REASM, None))
assert msg.flags == OFPC_FRAG_REASM
assert msg.miss_send_len == OFPCML_NO_BUFFER

msg = p.parse(b.ofp_packet_out(None, 45, 12, None, [
	b.ofp_action_output(None, None, OFPP_TABLE, OFPCML_MAX)], None))
assert msg.buffer_id == 45
assert msg.in_port == 12
assert len(msg.actions) == 1
action = msg.actions[0]
assert action.type == OFPAT_OUTPUT
assert action.port == OFPP_TABLE
assert action.max_len == OFPCML_MAX

msg = p.parse(b.ofp_flow_mod(None, 3, 0xFF, 0, OFPFC_ADD, 0, 300, 20, 45, OFPP_ANY, OFPG_ANY, 0, 7,
	b.ofp_match(None, None, b"".join([
		oxm.build(None, oxm.OXM_OF_IN_PORT, None, None, 12),
		oxm.build(None, oxm.OXM_OF_ETH_SRC, None, None, b"\xff\xff\xff\xff\xff\xff")])),
	[ b.ofp_instruction_actions(OFPIT_APPLY_ACTIONS, None, [
		b.ofp_action_push(OFPAT_PUSH_VLAN, None, 0x8100),
		b.ofp_action_set_field(None, None, oxm.build(None, oxm.OXM_OF_VLAN_VID, None, None, 612)),
		b.ofp_action_output(None, None, 5, OFPCML_MAX)]), ]))
assert msg.cookie == 3
assert msg.cookie_mask == 0xFF
assert msg.command == OFPFC_ADD
assert msg.out_port == OFPP_ANY
assert msg.importance == 7
match = msg.match
assert match.type == OFPMT_OXM
oxms = oxm.parse_list(match.oxm_fields)
assert len(oxms) == 2
assert oxms[0].oxm_field == oxm.OXM_OF_IN_PORT
assert oxms[0].oxm_value == 12
assert oxms[1].oxm_field == oxm.OXM_OF_ETH_SRC
assert oxms[1].oxm_value == b"\xff\xff\xff\xff\xff\xff"
assert len(msg.instructions) == 1
inst = msg.instructions[0]
assert inst.type == OFPIT_APPLY_ACTIONS
assert len(inst.actions) == 3

msg = p.parse(b.ofp_multipart_request(None, OFPMP_FLOW, 0,
	b.ofp_flow_stats_request(0, None, None, 1, 0xFF, None)))
assert msg.type == OFPMP_FLOW
body = msg.body
assert body.cookie == 1
assert body.cookie_mask == 0xFF

