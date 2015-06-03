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
		PBB_ISID TUNNEL_ID IPV6_EXTHDR'''
	})(globals())

ofp_vlan_id = type("ofp_vlan_id", (_enum_base,), {
	"prefix": "OFPVID",
	"bitshifts": { "PRESENT":12, "NONE":-1 }
	})(globals())

ofp_ipv6exthdr_flags = type("ofp_ipv6exthdr_flags", (_enum_base,), {
	"prefix": "OFPIEH",
	"bitshifts": "NONEXT ESP AUTH DEST FRAG ROUTER HOP UNREP UNSEQ"
	})(globals())

STRATOS_EXPERIMENTER_ID = 0xFF00E04D

stratos_oxm_fields = type("stratos_oxm_fields", (_enum_base,), {
	"prefix": "STRATOS_OXM_FIELD",
	"numbers": "BASIC RADIOTAP"})(globals())

stratos_basic_exp = type("stratos_basic_exp", (_enum_base,), {
	"prefix": "STROXM_BASIC",
	"numbers": '''UNKNOWN
		DOT11
		DOT11_FRAME_CTRL
		DOT11_ADDR1
		DOT11_ADDR2
		DOT11_ADDR3
		DOT11_ADDR4
		DOT11_SSID
		DOT11_ACTION_CATEGORY
		DOT11_PUBLIC_ACTION
		DOT11_TAG
		DOT11_TAG_VENDOR'''
	})(globals())

stratos_radiotap_exp = type("stratos_radiotap_exp", (_enum_base,), {
	"prefix": "STROXM_RADIOTAP",
	"numbers": {'''TSFT
			FLAGS
			RATE
			CHANNEL
			FHSS
			DBM_ANTSIGNAL
			DBM_ANTNOISE
			LOCK_QUALITY
			TX_ATTENUATION
			DB_TX_ATTENUATION
			DBM_TX_POWER
			ANTENNA
			DB_ANTSIGNAL
			DB_ANTNOISE
			RX_FLAGS
			TX_FLAGS
			RTS_RETRIES
			DATA_RETRIES
		''': 0, "MCS AMPDU_STATUS":19}
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

def _stratos_basic_bits(etype):
	if etype in (STROXM_BASIC_DOT11, STROXM_BASIC_DOT11_PUBLIC_ACTION, STROXM_BASIC_DOT11_TAG):
		return "B"

def _stratos_radiotap_bits(etype):
	if etype in (STROXM_RADIOTAP_FLAGS, STROXM_RADIOTAP_RATE, STROXM_RADIOTAP_ANTENNA,
			STROXM_RADIOTAP_DB_ANTSIGNAL, STROXM_RADIOTAP_DB_ANTNOISE,
			STROXM_RADIOTAP_RTS_RETRIES, STROXM_RADIOTAP_DATA_RETRIES):
		return "B"
	elif etype in (STROXM_RADIOTAP_DBM_ANTSIGNAL, STROXM_RADIOTAP_DBM_ANTNOISE, STROXM_RADIOTAP_DBM_TX_POWER):
		return "b"
	elif etype in (STROXM_RADIOTAP_LOCK_QUALITY, STROXM_RADIOTAP_RX_FLAGS, STROXM_RADIOTAP_TX_FLAGS,
			STROXM_RADIOTAP_TX_ATTENUATION, STROXM_RADIOTAP_DB_TX_ATTENUATION):
		return "H"
	elif etype in (STROXM_RADIOTAP_TSFT,):
		return "Q"

oxm = namedtuple("oxm", "oxm_class oxm_field oxm_hasmask oxm_length oxm_value oxm_mask")
stratos = namedtuple("stratos", "oxm_class oxm_field oxm_hasmask oxm_length exp exp_type value mask")

def parse(message, offset=0):
	(oxm_class, p, oxm_length) = struct.unpack_from("!HBB", message, offset)
	oxm_field = p>>1
	oxm_hasmask = p&1
	offset += 4
	
	if oxm_class == OFPXMC_OPENFLOW_BASIC:
		bits = _bits(oxm_field)
		
		if oxm_hasmask:
			assert oxm_length == struct.calcsize("!"+bits*2)
			return oxm(oxm_class, oxm_field, oxm_hasmask, oxm_length, *struct.unpack_from("!"+bits*2, message, offset))
		else:
			assert oxm_length == struct.calcsize(bits)
			return oxm(oxm_class, oxm_field, oxm_hasmask, oxm_length, struct.unpack_from("!"+bits, message, offset)[0], None)
	elif oxm_class == OFPXMC_EXPERIMENTER:
		exp = struct.unpack_from("!I", message, offset)[0]
		offset += 4
		if exp == STRATOS_EXPERIMENTER_ID:
			exp_type = struct.unpack_from("!H", message, offset)[0]
			offset += 2
			
			packs = None
			if oxm_field == STRATOS_OXM_FIELD_BASIC:
				bits = _stratos_basic_bits(exp_type)
				if bits:
					if oxm_hasmask:
						packs = "!"+bits*2
					else:
						packs = "!"+bits
			elif oxm_field == STRATOS_OXM_FIELD_RADIOTAP:
				bits = _stratos_radiotap_bits(exp_type)
				if bits:
					if oxm_hasmask:
						packs = "<"+bits*2
					else:
						packs = "<"+bits
			
			if packs is None:
				if oxm_hasmask:
					bits = "%ds" % (oxm_length - 6)/2
					packs = "!"+bits * 2
				else:
					bits = "%ds" % (oxm_length - 6)
					packs = "!"+bits
			
			vs = list(struct.unpack_from(packs, message, offset))
			if not oxm_hasmask:
				vs.append(None)
			
			return stratos(oxm_class, oxm_field, oxm_hasmask, oxm_length, exp, exp_type, *vs)
		else:
			raise ValueError("unsupported Experimenter ID")
	else:
		raise ValueError("only OFPXMC_OPENFLOW_BASIC or some OFPXMC_EXPERIMENTER is supported")

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
	
	# convert to pack integer
	if oxm_hasmask:
		oxm_hasmask = 1
	else:
		oxm_hasmask = 0
	
	if oxm_mask is None:
		if oxm_hasmask:
			oxm_mask = 0
	else:
		oxm_hasmask = 1
	
	bits = _bits(oxm_field)
	if oxm_hasmask:
		oxm_length = struct.calcsize("!"+bits*2)
		return struct.pack("!HBB"+bits*2, oxm_class, (oxm_field<<1)+oxm_hasmask, oxm_length, oxm_value, oxm_mask)
	else:
		oxm_length = struct.calcsize("!"+bits)
		return struct.pack("!HBB"+bits, oxm_class, (oxm_field<<1)+oxm_hasmask, oxm_length, oxm_value)

def build_stratos(oxm_class, oxm_field, oxm_hasmask, oxm_length, exp, exp_type, oxm_value, oxm_mask=None):
	if oxm_class is None:
		oxm_class = OFPXMC_EXPERIMENTER
	
	if exp == STRATOS_EXPERIMENTER_ID:
		packs = None
		if oxm_field == STRATOS_OXM_FIELD_BASIC:
			bits = _stratos_basic_bits(exp_type)
			if oxm_hasmask:
				packs = "!"+bits
			else:
				packs = "!"+bits*2
		elif oxm_field == STRATOS_OXM_FIELD_RADIOTAP:
			bits = _stratos_radiotap_bits(exp_type)
			if oxm_hasmask:
				packs = "<"+bits
			else:
				packs = "<"+bits*2
		else:
			raise ValueError("unsupported stratos field")
		
		if packs:
			if oxm_hasmask:
				vm = struct.pack(packs, oxm_value, oxm_mask)
			else:
				vm = struct.pack(packs, oxm_value)
		else:
			if oxm_hasmask:
				vm = oxm_value
			else:
				vm = oxm_value + oxm_mask
		
		if oxm_mask:
			oxm_mask = 1
		else:
			oxm_mask = 0
		
		oxm_length = 6 + len(vm)
		return struct.pack("!HBBIH", oxm_class, (oxm_field<<1)+oxm_hasmask, oxm_length, exp, exp_type)+vm
	else:
		raise ValueError("unsupported experimenter")
