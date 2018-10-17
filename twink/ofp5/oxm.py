from __future__ import absolute_import
import struct
from collections import namedtuple
from . import _enum_base

ofp_oxm_class = type("ofp_oxm_class", (_enum_base,), {
	"prefix": "OFPXMC",
	"numbers": {
		"NXM_0":          0x0000,
		"NXM_1":          0x0001,
		"OPENFLOW_BASIC": 0x8000,
		"EXPERIMENTER":   0xFFFF }
	})(globals())

oxm_ofb_match_fields = type("oxm_ofb_match_fields", (_enum_base,), {
	"prefix": "OXM_OF",
	"numbers": '''IN_PORT IN_PHY_PORT METADATA
		ETH_DST ETH_SRC ETH_TYPE VLAN_VID VLAN_PCP
		IP_DSCP IP_ECN IP_PROTO IPV4_SRC IPV4_DST
		TCP_SRC TCP_DST UDP_SRC UDP_DST SCTP_SRC SCTP_DST
		ICMPV4_TYPE ICMPV4_CODE
		ARP_OP ARP_SPA ARP_TPA ARP_SHA ARP_THA
		IPV6_SRC IPV6_DST IPV6_FLABEL
		ICMPV6_TYPE ICMPV6_CODE
		IPV6_ND_TARGET IPV6_ND_SLL IPV6_ND_TLL
		MPLS_LABEL MPLS_TC MPLS_BOS
		PBB_ISID TUNNEL_ID IPV6_EXTHDR PBB_UCA'''
	})(globals())

ofp_vlan_id = type("ofp_vlan_id", (_enum_base,), {
	"prefix": "OFPVID",
	"bitshifts": { "PRESENT":12, "NONE":-1 }
	})(globals())

ofp_ipv6exthdr_flags = type("ofp_ipv6exthdr_flags", (_enum_base,), {
	"prefix": "OFPIEH",
	"bitshifts": "NONEXT ESP AUTH DEST FRAG ROUTER HOP UNREP UNSEQ"
	})(globals())

def _bits(oxm_field):
	if oxm_field in (OXM_OF_IN_PORT, OXM_OF_IN_PHY_PORT):
		bits = "I"
	elif oxm_field in (OXM_OF_METADATA, OXM_OF_TUNNEL_ID):
		bits = "Q"
	elif oxm_field in (OXM_OF_ETH_DST, OXM_OF_ETH_SRC, OXM_OF_ARP_SHA, OXM_OF_ARP_THA,
			OXM_OF_IPV6_ND_SLL, OXM_OF_IPV6_ND_TLL):
		bits = "6s"
	elif oxm_field in (OXM_OF_ETH_TYPE, OXM_OF_VLAN_VID,
			OXM_OF_TCP_SRC, OXM_OF_TCP_DST, OXM_OF_UDP_SRC, OXM_OF_UDP_DST,
			OXM_OF_SCTP_SRC, OXM_OF_SCTP_DST, OXM_OF_ARP_OP, OXM_OF_IPV6_EXTHDR):
		bits = "H"
	elif oxm_field in (OXM_OF_IPV4_SRC, OXM_OF_IPV4_DST,
			OXM_OF_ARP_SPA, OXM_OF_ARP_TPA):
		bits = "4s"
	elif oxm_field in (OXM_OF_IPV6_SRC, OXM_OF_IPV6_DST, OXM_OF_IPV6_ND_TARGET):
		bits = "16s"
	elif oxm_field in (OXM_OF_PBB_ISID, ):
		bits = "3s"
	else:
		bits = "B"
	return bits

def parse(message, offset=0):
	(oxm_class, p, oxm_length) = struct.unpack_from("!HBB", message, offset)
	oxm_field = p>>1
	oxm_hasmask = p&1
	offset += 4
	
	if oxm_class != OFPXMC_OPENFLOW_BASIC:
		raise ValueError("only OFPXMC_OPENFLOW_BASIC is supported")
	
	bits = _bits(oxm_field)
	
	if oxm_hasmask:
		assert oxm_length == struct.calcsize("!"+bits*2)
		return namedtuple("oxm", "oxm_class oxm_field oxm_hasmask oxm_length oxm_value oxm_mask")(
			oxm_class, oxm_field, oxm_hasmask, oxm_length, *struct.unpack_from("!"+bits*2, message, offset))
	else:
		assert oxm_length == struct.calcsize(bits)
		return namedtuple("oxm", "oxm_class oxm_field oxm_hasmask oxm_length oxm_value")(
			oxm_class, oxm_field, oxm_hasmask, oxm_length, *struct.unpack_from("!"+bits, message, offset))

def parse_list(message, offset=0):
	ret = []
	while offset < len(message):
		m = parse(message, offset)
		ret.append(m)
		offset += 4 + m.oxm_length
	return ret

def build(oxm_class, oxm_field, oxm_hasmask, oxm_length, oxm_value, oxm_mask=None):
	if oxm_class is None:
		oxm_class = OFPXMC_OPENFLOW_BASIC
	assert oxm_class == OFPXMC_OPENFLOW_BASIC
	
	bits = _bits(oxm_field)
	
	if oxm_hasmask:
		oxm_hasmask = 1
	else:
		oxm_hasmask = 0
	
	if oxm_mask is None:
		if oxm_hasmask:
			oxm_mask = 0
	else:
		oxm_hasmask = 1
	
	if oxm_hasmask:
		oxm_length = struct.calcsize("!"+bits*2)
		return struct.pack("!HBB"+bits*2, oxm_class, (oxm_field<<1)+oxm_hasmask, oxm_length, oxm_value, oxm_mask)
	else:
		oxm_length = struct.calcsize("!"+bits)
		return struct.pack("!HBB"+bits, oxm_class, (oxm_field<<1)+oxm_hasmask, oxm_length, oxm_value)

