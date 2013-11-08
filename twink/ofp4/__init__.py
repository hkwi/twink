import struct
import collections

class _enum_base(object):
	numbers = None
	bitshifts = None
	def items(self):
		ret = []
		if self.numbers is None:
			pass
		elif isinstance(self.numbers, str):
			vs = self.numbers.split()
			ret += zip(vs, range(len(vs)))
		elif isinstance(self.numbers, dict):
			for k,v in self.numbers.items():
				for ki in k.split():
					ret.append((ki, v))
					v += 1
		else:
			raise ValueError(self.numbers)
		
		ret += self.items_bitshifts()
		
		return ret
	
	def items_bitshifts(self):
		ret = []
		if self.bitshifts is None:
			pass
		elif isinstance(self.bitshifts, str):
			vs = self.bitshifts.split()
			for k,v in zip(vs, range(len(vs))):
				if v<0:
					ret.append((k, 0))
				else:
					ret.append((k, 1<<v))
		elif isinstance(self.bitshifts, dict):
			for k,v in self.bitshifts.items():
				for ki in k.split():
					if v < 0:
						ret.append((ki, 0))
					else:
						ret.append((ki, 1<<v))
					v += 1
		else:
			raise ValueError(self.bitshifts)
		
		return ret
	
	def __init__(self, scope):
		for k,v in self.items():
			scope[self.prefix+"_"+k] = v
	
	def name(self, value):
		for k,v in self.items():
			if v == value:
				return self.prefix+"_"+k
	
	def bitnames(self, value):
		nohit = None
		ret = []
		for k,v in self.items_bitshifts():
			if k.endswith("_MASK"):
				continue
			if value & v:
				ret.append(self.prefix+"_"+k)
			elif v == 0:
				nohit = self.prefix+"_"+k
		if not ret and nohit:
			return [nohit,]
		return ret
	
	def values(self):
		return [v for k,v in self.items()]
	
	def keys(self):
		return [k for k,v in self.items()]

# special definition
OFP_NO_BUFFER = 0xffffffff

# 6.4 and 7.3.4.1
ofp_flow_mod_command = type("ofp_flow_mod_command", (_enum_base,), {
	"prefix": "OFPFC",
	"numbers": "ADD MODIFY MODIFY_STRICT DELETE DELETE_STRICT"
	})(globals())

ofp_group_mod_command = type("ofp_group_mod_command", (_enum_base,), {
	"prefix": "OFPGC",
	"numbers": "ADD MODIFY DELETE"
	})(globals())

ofp_meter_mod_command = type("ofp_meter_mod_command", (_enum_base,), {
	"prefix": "OFPMC",
	"numbers": "ADD MODIFY DELETE"
	})(globals())

ofp_type = type("ofp_type", (_enum_base,), {
	"prefix": "OFPT",
	"numbers": '''HELLO ERROR ECHO_REQUEST ECHO_REPLY EXPERIMENTER
		FEATURES_REQUEST FEATURES_REPLY GET_CONFIG_REQUEST GET_CONFIG_REPLY SET_CONFIG
		PACKET_IN FLOW_REMOVED PORT_STATUS
		PACKET_OUT FLOW_MOD GROUP_MOD PORT_MOD TABLE_MOD
		MULTIPART_REQUEST MULTIPART_REPLY
		BARRIER_REQUEST BARRIER_REPLY
		QUEUE_GET_CONFIG_REQUEST QUEUE_GET_CONFIG_REPLY
		ROLE_REQUEST ROLE_REPLY
		GET_ASYNC_REQUEST GET_ASYNC_REPLY SET_ASYNC
		METER_MOD'''
	})(globals())

ofp_port_config = type("ofp_port_config", (_enum_base,), {
	# XXX There're two definitions, each in 7.2.1 and A.6.8
	"prefix": "OFPPC",
	"bitshifts": "PORT_DOWN NO_STP NO_RECV NO_RECV_STP NO_FLOOD NO_FWD NO_PACKET_IN"
	})(globals())

ofp_port_state = type("ofp_port_state", (_enum_base,), {
	"prefix": "OFPPS",
	"bitshifts": "LINK_DOWN BLOCKED LIVE"
	})(globals())

ofp_port_no = type("ofp_port_no", (_enum_base,), {
	"prefix": "OFPP",
	"numbers": {
		"MAX":        0xffffff00,
		"IN_PORT":    0xfffffff8,
		"TABLE":      0xfffffff9,
		"NORMAL":     0xfffffffa,
		"FLOOD":      0xfffffffb,
		"ALL":        0xfffffffc,
		"CONTROLLER": 0xfffffffd,
		"LOCAL":      0xfffffffe,
		"ANY":        0xffffffff }
	})(globals())

ofp_port_features = type("ofp_port_features", (_enum_base,), {
	"prefix": "OFPPF",
	"bitshifts": '''10MB_HD 10MB_FD 100MB_HD 100MB_FD 1GB_HD 1GB_FD
		10GB_FD 40GB_FD 100GB_FD 1TB_FD OTHER
		COPPER FIBER AUTONEG PAUSE PAUSE_ANY'''
	})(globals())

ofp_queue_properties = type("ofp_queue_properties", (_enum_base,), {
	"prefix": "OFPQT",
	"numbers": {
		"MIN_RATE": 1,
		"MAX_RATE": 2,
		"EXPERIMENTER": 0xffff }
	})(globals())

ofp_match_type = type("ofp_match_type", (_enum_base,), {
	"prefix": "OFPMT",
	"numbers": "STANDARD OXM"
	})(globals())

ofp_oxm_class = type("ofp_oxm_class", (_enum_base,), {
	"prefix": "OFPXMC",
	"numbers": {
		"NXM_0":          0x0000,
		"NXM_1":          0x0001,
		"OPENFLOW_BASIC": 0x8000,
		"EXPERIMENTER":   0xFFFF }
	})(globals())

ofp_match_fields = type("ofp_match_fields", (_enum_base,), {
	"prefix": "OFPXMT_OFB",
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
	"numbers": {
		"PRESENT": 0x1000,
		"NONE":    0x0000 }
	})(globals())

ofp_ipv6exthdr_flags = type("ofp_ipv6exthdr_flags", (_enum_base,), {
	"prefix": "OFPIEH",
	"bitshifts":"NONEXT ESP AUTH DEST FRAG ROUTER HOP UNREP UNSEQ"
	})(globals())

ofp_instruction_type = type("ofp_instruction_type", (_enum_base,), {
	"prefix": "OFPIT",
	"numbers": {
		'''GOTO_TABLE
		WRITE_METADATA
		WRITE_ACTIONS
		APPLY_ACTIONS
		CLEAR_ACTIONS
		METER''': 1,
		"EXPERIMENTER":   0xFFFF}
	})(globals())

# 7.2.5
ofp_action_type = type("ofp_action_type", (_enum_base,), {
	"prefix": "OFPAT",
	"numbers": {
		"OUTPUT": 0,
		"COPY_TTL_OUT COPY_TTL_IN": 11,
		'''SET_MPLS_TTL DEC_MPLS_TTL PUSH_VLAN POP_VLAN
			PUSH_MPLS POP_MPLS SET_QUEUE GROUP
			SET_NW_TTL DEC_NW_TTL SET_FIELD PUSH_PBB POP_PBB''': 15,
		"EXPERIMENTER": 0xffff}
	})(globals())

# A.6.17 
# ofp_action_type = type("ofp_action_type", (_enum_base,), {
# 	"prefix": "OFPAT",
# 	"numbers": {'''OUTPUT SET_VLAN_VID SET_VLAN_PCP STRIP_VLAN
# 		SET_DL_SRC SET_DL_DST SET_NW_SRC SET_NW_DST
# 		SET_TP_SRC SET_TP_DST''':0,
# 		"VENDOR": 0xffff}
# 	})(globals())

ofp_controller_max_len = type("ofp_controller_max_len", (_enum_base,), {
	"prefix": "OFPCML",
	"numbers": {
		"MAX":       0xffe5,
		"NO_BUFFER": 0xffff}
	})(globals())

ofp_capabilities = type("ofp_capabilities", (_enum_base,), {
	"prefix": "OFPC",
	"bitshifts": {
		'''FLOW_STATS
		TABLE_STATS
		PORT_STATS
		GROUP_STATS''': 0,
		'''IP_REASM
		QUEUE_STATS''': 5,
		"PORT_BLOCKED": 8 }
	})(globals())

ofp_config_flags = type("ofp_config_flags", (_enum_base,), {
	"prefix": "OFPC_FRAG",
	"numbers": "NORMAL DROP REASM MASK"
	})(globals())

ofp_table = type("ofp_table", (_enum_base,), {
	"prefix": "OFPTT",
	"numbers": {
		"MAX": 0xfe,
		"ALL": 0xff }
	})(globals())

ofp_table_config = type("ofp_table_config", (_enum_base,), {
	"prefix": "OFPTC",
	"numbers": {
		"DEPRECATED_MASK": 3 }
	})(globals())

ofp_flow_mod_flags = type("ofp_flow_mod_flags", (_enum_base,), {
	"prefix": "OFPFF",
	"bitshifts":"SEND_FLOW_REM CHECK_OVERLAP RESET_COUNTS NO_PKT_COUNTS BYT_COUNTS"
	})(globals())

ofp_group_mod_command = type("ofp_group_mod_command", (_enum_base,), {
	"prefix": "OFPGC",
	"numbers": "ADD MODIFY DELETE"
	})(globals())

ofp_group_type = type("ofp_group_type", (_enum_base,), {
	"prefix": "OFPGT",
	"numbers": "ALL SELECT INDIRECT FF"
	})(globals())

ofp_group = type("ofp_group", (_enum_base,), {
	"prefix": "OFPG",
	"numbers": {
		"MAX": 0xffffff00,
		"ALL": 0xfffffffc,
		"ANY": 0xffffffff }
	})(globals())

ofp_meter = type("ofp_meter", (_enum_base,), {
	"prefix": "OFPM",
	"numbers": {
		"MAX":        0xffff0000,
		"SLOWPATH":   0xfffffffd,
		"CONTROLLER": 0xfffffffe,
		"ALL":        0xffffffff }
	})(globals())

ofp_meter_mod_command = type("ofp_meter_mod_command", (_enum_base,), {
	"prefix": "OFPMC",
	"numbers": "ADD MODIFY DELETE"
	})(globals())

ofp_meter_flags = type("ofp_meter_flags", (_enum_base,), {
	"prefix": "OFPMF",
	"bitshifts":"KBPS PKTPS BURST STATS"
	})(globals())

ofp_meter_band_type = type("ofp_meter_band_type", (_enum_base,), {
	"prefix": "OFPMBT",
	"numbers": {
		"DROP": 1,
		"DSCP_REMARK": 2,
		"EXPERIMENTER": 0xFFFF }
	})(globals())

ofp_multipart_request_flags = type("ofp_multipart_request_flags", (_enum_base,), {
	"prefix": "OFPMPF",
	"numbers": { "REQ_MORE": 1 }
	})(globals())

ofp_multipart_reply_flags = type("ofp_multipart_reply_flags", (_enum_base,), {
	"prefix": "OFPMPF",
	"numbers": { "REPLY_MORE": 1 }
	})(globals())

ofp_multipart_type = type("ofp_multipart_type", (_enum_base,), {
	"prefix": "OFPMP",
	"numbers": {
		'''DESC FLOW AGGREGATE TABLE PORT_STATS QUEUE
		GROUP GROUP_DESC GROUP_FEATURES
		METER METER_CONFIG METER_FEATURES
		TABLE_FEATURES PORT_DESC''': 0,
		"EXPERIMENTER": 0xffff}
	})(globals())

ofp_table_feature_prop_type = type("ofp_table_feature_prop_type", (_enum_base,), {
	"prefix": "OFPTFPT",
	"numbers": {
		'''INSTRUCTIONS INSTRUCTIONS_MISS
		NEXT_TABLES NEXT_TABLES_MISS
		WRITE_ACTIONS WRITE_ACTIONS_MISS
		APPLY_ACTIONS APPLY_ACTIONS_MISS
		MATCH
		WILDCARDS
		WRITE_SETFIELD WRITE_SETFIELD_MISS
		APPLY_SETFIELD APPLY_SETFIELD_MISS''':0,
		"EXPERIMENTER EXPERIMENTER_MISS": 0xFFFE }
	})(globals())

ofp_group_capabilities = type("ofp_group_capabilities", (_enum_base,), {
	"prefix": "OFPGFC",
	"bitshifts":"SELECT_WEIGHT SELECT_LIVENESS CHAINING CHAINING_CHECKS"
	})(globals())

ofp_controller_role = type("ofp_controller_role", (_enum_base,), {
	"prefix": "OFPCR_ROLE",
	"numbers": "NOCHANGE EQUAL MASTER SLAVE"
	})(globals())

ofp_packet_in_reason = type("ofp_packet_in_reason", (_enum_base,), {
	"prefix": "OFPR",
	"numbers": "NO_MATCH ACTION INVALID_TTL"
	})(globals())

ofp_flow_removed_reason = type("ofp_flow_removed_reason", (_enum_base,), {
	"prefix": "OFPRR",
	"numbers": "IDLE_TIMEOUT HARD_TIMEOUT DELETE GROUP_DELETE"
	})(globals())

ofp_port_reason = type("ofp_port_reason", (_enum_base,), {
	"prefix": "OFPPR",
	"numbers": "ADD DELETE MODIFY"
	})(globals())

ofp_error_type = type("ofp_error_type", (_enum_base,), {
	"prefix": "OFPET",
	"numbers": {
		'''HELLO_FAILED BAD_REQUEST BAD_ACTION BAD_INSTRUCTION BAD_MATCH
		FLOW_MOD_FAILED GROUP_MOD_FAILED PORT_MOD_FAILED
		TABLE_MOD_FAILED SWITCH_CONFIG_FAILWD ROLE_REQUEST_FAILED 
		METER_MOD_FAILED TABLE_FEATURES_FAILED''': 0,
		"EXPERIMENTER": 0xffff }
	})(globals())

ofp_hello_failed_code = type("ofp_hello_failed_code", (_enum_base,), {
	"prefix": "OFPHFC",
	"numbers": "INCOMPATIBLE EPERM"
	})(globals())

ofp_bad_request_code = type("ofp_bad_request_code", (_enum_base,), {
	"prefix": "OFPBRC",
	"numbers": '''BAD_VERSION BAD_TYPE BAD_MULTIPART BAD_EXPERIMENTER
		BAD_EXP_TYPE EPERM BAD_LEN BUFFER_EMPTY BUFFER_UNKNOWN BAD_TABLE_ID
		IS_SLAVE BAD_PORT BAD_PACKET MULTIPART_BUFFER_OVERFLOW'''
	})(globals())

ofp_bad_action_code = type("ofp_bad_action_code", (_enum_base,), {
	"prefix": "OFPBAC",
	"numbers": '''BAD_TYPE BAD_LEN BAD_EXPERIMENTER BAD_EXP_TYPE BAD_OUT_PORT
		BAD_ARGUMENT EPERM TOO_MANY BAD_QUEUE BAD_OUT_GROUP
		MATCH_INCONSISTENT UNSUPPORTED_ORDER BAD_TAG
		BAD_SET_TYPE BAD_SET_LEN BAD_SET_ARGUMENT'''
	})(globals())

ofp_bad_instruction_code = type("ofp_bad_instruction_code", (_enum_base,), {
	"prefix": "OFPBIC",
	"numbers": '''UNKNOWN_INST UNSUP_INST BAD_TABLE_ID
		UNSUP_METADATA UNSUP_METADATA_MASK
		BAD_EXPERIMENTER BAD_EXP_TYPE BAD_LEN EPERM'''
	})(globals())

ofp_bad_match_code = type("ofp_bad_match_code", (_enum_base,), {
	"prefix": "OFPBMC",
	"numbers": '''BAD_TYPE BAD_LEN BAD_TAG
		BAD_DL_ADDR_MASK BAD_NW_ADDR_MASK BAD_WILDCARDS
		BAD_FIELD BAD_VALUE BAD_MASK BAD_PREREQ
		DUP_FIELD EPERM'''
	})(globals())

ofp_flow_mod_failed_code = type("ofp_flow_mod_failed_code", (_enum_base,), {
	"prefix": "OFPFMFC",
	"numbers": '''UNKNOWN TABLE_FULL BAD_TABLE_ID OVERLAP EPERM
		BAD_TIMEOUT BAD_COMMAND BAD_FLAGS'''
	})(globals())

ofp_group_mod_failed_code = type("ofp_group_mod_failed_code", (_enum_base,), {
	"prefix": "OFPGMFC",
	"numbers": '''GROUP_EXISTS INVALID_GROUP WEIGHT_UNSUPPORTED
		OUT_OF_GROUPS OUT_OF_BUCKETS CHAINING_UNSUPPORTED
		WATCH_UNSUPPORTED LOOP UNKNOWN_GROUP CHAINED_GROUP
		BAD_TYPE BAD_COMMAND BAD_BUCKET BAD_WATCH EPERM'''
	})(globals())

ofp_table_mod_failed_code = type("ofp_table_mod_failed_code", (_enum_base,), {
	"prefix": "OFPTMFC",
	"numbers": "BAD_TABLE BAD_CONFIG EPERM"
	})(globals())

ofp_queue_op_failed_code = type("ofp_queue_op_failed_code", (_enum_base,), {
	"prefix": "OFPQOFC",
	"numbers": "BAD_PORT BAD_QUEUE EPERM"
	})(globals())

ofp_switch_config_failed_code = type("ofp_switch_config_failed_code", (_enum_base,), {
	"prefix": "OFPSCFC",
	"numbers": "BAD_FLAGS BAD_LEN EPERM"
	})(globals())

ofp_role_request_failed_code = type("ofp_role_request_failed_code", (_enum_base,), {
	"prefix": "OFPRRFC",
	"numbers": "STALE UNSUP BAD_ROLE"
	})(globals())

ofp_meter_mod_failed_code = type("ofp_meter_mod_failed_code", (_enum_base,), {
	"prefix": "OFPMMFC",
	"numbers": '''UNKNOWN METER_EXISTS INVALID_METER UNKNOWN_METER
		BAD_COMMAND BAD_FLAGS BAD_RATE BAD_BURST BAD_BAND BAD_BAND_VALUE
		OUT_OF_METERS OUT_OF_BANDS'''
	})(globals())

ofp_table_features_failed_code = type("ofp_table_features_failed_code", (_enum_base,), {
	"prefix": "OFPTFFC",
	"numbers": "BAD_TABLE BAD_METADATA BAD_TYPE BAD_LEN BAD_ARGUMENT EPERM"
	})(globals())

ofp_hello_enum_type = type("ofp_hello_enum_type", (_enum_base,), {
	"prefix": "OFPHET",
	"numbers": { "VERSIONBITMAP":1 }
	})(globals())

ofp_flow_wildcards = type("ofp_flow_wildcards", (_enum_base,), {
	"prefix": "OFPFW",
	"numbers": {
		"IN_PORT": 1<<0,
		"DL_VLAN": 1<<1,
		"DL_SRC": 1<<2,
		"DL_DST": 1<<3,
		"DL_TYPE": 1<<4,
		"NW_PROTO": 1<<5,
		"TP_SRC": 1<<6,
		"TP_DST": 1<<7,
		"NW_SRC_SHIFT": 8,
		"NW_SRC_BITS": 6,
		"NW_SRC_MASK": 0x3f<<8,
		"NW_DST_SHIFT": 14,
		"NW_DST_BITS": 6,
		"NW_DST_MASK": 0x3f<<14,
		"NW_DST_ALL": 32<<14,
		"ALL": 0xfffff }
	})(globals())

ofp_flow_expired_readon = type("ofp_flow_expired_readon", (_enum_base,), {
	"prefix": "OFPER",
	"numbers": "IDLE_TIMEOUT HARD_TIMEOUT"
	})(globals())


def ofptuple(etherframe, in_port=None):
	'''
	returns an openflow v1.0 12 tuple without the first in_port
	'''
	(ethernet_dst, ethernet_src, ethernet_type, tci, inner_type) = struct.unpack_from("!6s6sHHH", etherframe)
	if ethernet_type == 0x8100:
		vlan_id = tci&0x0FFF
		vlan_priority = tci>>13
		ethernet_type = inner_type
		offset = 4
	else:
		vlan_id = None
		vlan_priority = None
		offset = 0
	
	if ethernet_type < 0x05DC:
		(llc_dsap, llc_ssap, llc_ctl, snap_oui, snap_type) = struct.unpack_from("!BBB3sH", etherframe, offset=14)
		if llc_dsap==0xAA and llc_ssap==0xAA and snap_oui=="0x00"*3:
			ethernet_type = snap_type
			offset = 8
	
	ip_tos = ip_protocol = ip_src = ip_dst = None
	transport_src_port_or_icmp_type = None
	transport_dst_port_or_icmp_code = None
	if ethernet_type == 0x0800: # IP
		(ip_tos, ip_protocol, ip_src, ip_dst, src_port, dst_port) = struct.unpack_from("!xB7xB2x4s4sHH", etherframe, offset=14+offset)
		if ip_protocol == 1: # ICMP
			transport_src_port_or_icmp_type = src_port>>8
			transport_dst_port_or_icmp_code = src_port&0xFF
		elif ip_protocol in (6, 17): # TCP, UDP
			transport_src_port_or_icmp_type = src_port
			transport_dst_port_or_icmp_code = dst_port
	elif ethernet_type == 0x0806: # ARP
		# ip_protocol : ARP Operation
		(ip_protocol, ip_src, ip_dst) = struct.unpack_from("!6xH6x4s6x4s", etherframe, offset=14+offset)
	
	return collections.namedtuple("ofptuple", "in_port dl_src dl_dst dl_type dl_vlan dl_vlan_pcp nw_src nw_dst nw_proto ip_tos tp_src tp_dst")(
		in_port,
		ethernet_src,
		ethernet_dst,
		ethernet_type,
		vlan_id,
		vlan_priority,
		ip_src,
		ip_dst,
		ip_protocol,
		ip_tos,
		transport_src_port_or_icmp_type,
		transport_dst_port_or_icmp_code
		)
