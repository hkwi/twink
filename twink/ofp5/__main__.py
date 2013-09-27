from __future__ import absolute_import
from . import *
from . import parse as p
from . import build as b

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

