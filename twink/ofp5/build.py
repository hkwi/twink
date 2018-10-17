from __future__ import absolute_import
import struct
import random
from . import *

_len = len
_type = type

try:
	long(0)
except:
	long = int

default_xid = lambda: long(random.random()*0xFFFFFFFF)

def _obj(obj):
	if isinstance(obj, bytes):
		return obj
	elif isinstance(obj, tuple):
		return eval(obj.__class__.__name__)(*obj)
	else:
		raise ValueError(obj)

def _pack(fmt, *args):
	if fmt[0] != "!":
		fmt = "!"+fmt
	return struct.pack(fmt, *args)

def _unpack(fmt, message, offset):
	if fmt[0] != "!":
		fmt = "!"+fmt
	return struct.unpack_from(fmt, message, offset)

def _align(length):
	return (length+7)//8*8

# 7.1
def ofp_header(version, type, length, xid):
	if version is None:
		version = 5
	assert version==5
	
	if length is None:
		length = 8
	
	if xid is None:
		xid = default_xid()
	
	return _pack("BBHI", version, type, length, xid)


def ofp_(header, data, type=None):
	if isinstance(header, bytes):
		(version, oftype, length, xid) = _unpack("BBHI", header, 0)
		if isinstance(type, int):
			assert oftype == type
		elif isinstance(type, (list,tuple)):
			assert oftype in type
		elif type is None:
			pass
		else:
			raise ValueError(type)
	elif isinstance(header, tuple):
		(version, oftype, length, xid) = header
		if isinstance(type, int):
			if oftype is None:
				oftype = type
			else:
				assert oftype == type
		elif isinstance(type, (list,tuple)):
			assert oftype in type
		elif type is None:
			assert isinstance(oftype, int)
		else:
			raise ValueError(type)
	elif header is None:
		version = 5
		if isinstance(type, int):
			oftype = type
		else:
			raise ValueError(type)
		xid = default_xid()
	else:
		raise ValueError(header)
	
	data = _obj(data)
	length = 8 + _len(data)
	return ofp_header(version, oftype, length, xid)+data


# 7.2.1.1
def ofp_port(port_no, length, hw_addr, name, config, state, properties):
	assert isinstance(hw_addr, str) and _len(hw_addr)==6
	assert isinstance(name, str) and _len(name)<=16
	
	if isinstance(properties, str):
		pass
	elif isinstance(properties, (list, tuple)):
		properties = b"".join([_obj(p) for p in properties])
	elif properties is None:
		properties = b""
	else:
		raise ValueError(properties)
	
	length = 40 + _len(properties)
	
	msg = _pack("IH2x6s2x16sII", 
		port_no,
		length,
		hw_addr,
		name,
		config,
		state
		)
	return msg

# 7.2.1.2
def ofp_port_desc_prop_header(type, length):
	# XXX: You won't need this function
	return _pack("HH", type, length)

def ofp_port_desc_prop_ethernet(type, length,
		curr, advertised, supported, peer, curr_speed, max_speed):
	if type is None:
		type = OFPPDPT_ETHERNET
	assert type == OFPPDPT_ETHERNET
	
	length = 32
	return _pack("HH4x6I", type, length,
		curr, advertised, supported, peer, curr_speed, max_speed)

def ofp_port_desc_prop_optical(type, length, supported,
		tx_min_freq_lmda, tx_max_freq_lmda, tx_grid_freq_lmda,
		rx_min_freq_lmda, rx_max_freq_lmda, rx_grid_freq_lmda,
		tx_pwr_min, tx_pwr_max):
	if type is None:
		type = OFPPDPT_OPTICAL
	assert type == OFPPDPT_OPTICAL
	
	length = 40
	return _pack("HH4x7I2H", type, length, supported,
		tx_min_freq_lmda, tx_max_freq_lmda, tx_grid_freq_lmda,
		rx_min_freq_lmda, rx_max_freq_lmda, rx_grid_freq_lmda,
		tx_pwr_min, tx_pwr_max)

def ofp_port_desc_prop_experimenter(type, length,
		experimenter, exp_type, experimenter_data):
	if type is None:
		type = OFPPDPT_EXPERIMENTER
	assert type == OFPPDPT_EXPERIMENTER
	
	if experimenter_data is None:
		experimenter_data = b""
	
	length = 12 + _len(experimenter_data)
	return _pack("HHII", type, length, experimenter, exp_type
		) + experimenter_data + b"\x00" * (align(length) - length)

# 7.2.2.1
def ofp_match(type, length, oxm_fields):
	'''type: OFPMT_STANDARD/OXM
	'''
	if type is None:
		type = OFPMT_OXM
	
	if isinstance(oxm_fields, str):
		pass
	elif isinstance(oxm_fields, (list, tuple)):
		oxm_fields = b"".join([_obj(f) for f in oxm_fields])
	elif oxm_fields is None:
		oxm_fields = b""
	else:
		ValueError(oxm_fields)
	
	length = 4 + _len(oxm_fields)
	
	msg = _pack("HH", type, length) + oxm_fields + b"\0"*(_align(length)-length)
	assert _len(msg) % 8 == 0
	return msg

# 7.2.4
def ofp_instruction_header(type, len):
	return _pack("HH", type, len)

def ofp_instruction_goto_table(type, len, table_id):
	if type is None:
		type = OFPIT_GOTO_TABLE
	assert type==OFPIT_GOTO_TABLE
	len = 8
	msg = _pack("HHB3x",
		type,
		len,
		table_id)
	assert _len(msg)==8
	return msg

def ofp_instruction_write_metadata(type, len, metadata, metadata_mask):
	if type is None:
		type = OFPIT_WRITE_METADATA
	assert type==OFPIT_WRITE_METADATA
	len = 24
	msg = _pack("HH4xQQ",
		type,
		len,
		metadata,
		metadata_mask)
	assert _len(msg)==24
	return msg

def ofp_instruction_actions(type, len, actions):
	'''type: OFPIT_WRITE_ACTIONS/APPLY_ACTIONS/CLEAR_ACTIONS
	'''
	if isinstance(actions, str):
		pass
	elif isinstance(actions, (tuple, list)):
		actions = b"".join([_obj(a) for a in actions])
	elif actions is None:
		actions = b""
	else:
		raise ValueError(actions)
	
	assert type in (OFPIT_WRITE_ACTIONS, OFPIT_APPLY_ACTIONS, OFPIT_CLEAR_ACTIONS)
	
	len = _align(8 + _len(actions))
	msg = _pack("HH4x",
		type,
		len) + actions
	return msg

def ofp_instruction_meter(type, len, meter_id):
	if type is None:
		type = OFPIT_METER
	assert type==OFPIT_METER
	len = 8
	msg = _pack("HHI",
		type,
		len,
		meter_id)
	return msg

def ofp_instruction_experimenter_(type, len, experimenter, data):
	if type is None:
		type = OFPIT_EXPERIMENTER
	assert type == OFPIT_EXPERIMENTER
	
	data = _obj(data)
	
	len = 8 + _len(data)
	
	msg = _pack("HHI",
		type,
		len,
		experimenter) + data
	return msg

# 7.2.4
def ofp_action_header(type, len):
	return _pack("HH", type, len)

def ofp_action_output(type, len, port, max_len):
	'''max_len: OFP_CML_MAX/NO_BUFFER
	'''
	if type is None:
		type = OFPAT_OUTPUT
	assert type == OFPAT_OUTPUT
	
	len = 16
	
	msg = _pack("HHIH6x",
		type,
		len,
		port,
		max_len)
	assert _len(msg) == 16
	return msg

def ofp_action_group(type, len, group_id):
	if type is None:
		type = OFPAT_GROUP
	assert type == OFPAT_GROUP
	
	len = 8
	
	msg = _pack("HHI",
		type,
		len,
		group_id)
	assert _len(msg) == 8
	return msg

def ofp_action_set_queue(type, len, queue_id):
	if type is None:
		type = OFPAT_SET_QUEUE
	assert type == OFPAT_SET_QUEUE
	
	len = 8
	
	msg = _pack("HHI",
		type,
		len,
		queue_id)
	assert _len(msg) == 8
	return msg

def ofp_action_mpls_ttl(type, len, mpls_ttl):
	if type is None:
		type = OFPAT_SET_MPLS_TTL
	assert type == OFPAT_SET_MPLS_TTL
	
	len = 8
	
	msg = _pack("HHB3x",
		type,
		len,
		mpls_ttl)
	assert _len(msg) == 8
	return msg

def ofp_action_generic(type, len):
	assert type in (OFPAT_COPY_TTL_OUT, OFPAT_COPY_TTL_IN,
		OFPAT_DEC_MPLS_TTL, OFPAT_DEC_NW_TTL, OFPAT_POP_VLAN, OFPAT_POP_PBB)
	len = 8
	return _pack("HH4x", type, len)

def ofp_action_nw_ttl(type, len, nw_ttl):
	if type is None:
		type = OFPAT_SET_NW_TTL
	assert type == OFPAT_SET_NW_TTL
	
	len = 8
	
	msg = _pack("HHB3x",
		type,
		len,
		nw_ttl)
	assert _len(msg) == 8
	return msg

def ofp_action_push(type, len, ethertype):
	'''type: OFPAT_PUSH_VLAN/PUSH_MPLS/PUSH_PBB
	'''
	assert type in (OFPAT_PUSH_VLAN, OFPAT_PUSH_MPLS, OFPAT_PUSH_PBB)
	
	len = 8
	
	msg = _pack("3H2x",
		type,
		len,
		ethertype)
	assert _len(msg) == 8
	return msg

def ofp_action_pop_mpls(type, len, ethertype):
	if type is None:
		type = OFPAT_POP_MPLS
	assert type == OFPAT_POP_MPLS
	
	len = 8
	
	msg = _pack("3H2x",
		type,
		len,
		ethertype)
	assert _len(msg) == 8
	return msg

def ofp_action_set_field(type, len, field):
	if type is None:
		type = OFPAT_SET_FIELD
	assert type == OFPAT_SET_FIELD
	
	assert isinstance(field, bytes)
	
	filled_len = 4 + _len(field)
	len = _align(filled_len)
	
	return _pack("HH", type, len) + field + b'\0'*(len-filled_len)

def ofp_action_experimenter_header(type, len, experimenter):
	return _pack("HHI", type, len, experimenter)

def ofp_action_experimenter_(type, len, experimenter, data):
	if type is None:
		type = OFPAT_EXPERIMENTER
	assert type == OFPAT_EXPERIMENTER
	
	assert isinstance(data, str)
	
	filled_len = 8 + _len(data)
	len = _align(filled_len)
	
	return _pack("HHI", type, len, experimenter) + data + b'\0'*(len-filled_len)

# 7.3.1
def ofp_switch_features(header, datapath_id, n_buffers, n_tables, auxiliary_id, capabilities):
	msg = ofp_(header, _pack("QIBB2xII",
		datapath_id,
		n_buffers,
		n_tables,
		auxiliary_id,
		capabilities,
		0), OFPT_FEATURES_REPLY)
	assert _len(msg) == 32
	return msg

# 7.3.2
def ofp_switch_config(header, flags, miss_send_len):
	if miss_send_len is None:
		miss_send_len = OFPCML_NO_BUFFER
	msg = ofp_(header, _pack("HH",
		flags,
		miss_send_len), (OFPT_SET_CONFIG, OFPT_GET_CONFIG_REPLY))
	assert _len(msg) == 12
	return msg

# 7.3.3
def ofp_table_mod(header, table_id, config, properties):
	msg = ofp_(header, _pack("B3xI",
		table_id,
		config)+properties, OFPT_TABLE_MOD)
	return msg

def ofp_table_mod_prop_header(type, length):
	return _pack("HH", type, length)

def ofp_table_mod_prop_eviction(type, length, flags):
	type = OFPTMPT_EVICTION
	return _pack("HHI", type, length, flags)

def ofp_table_mod_prop_vacancy(type, length, vacancy_down, vacancy_up, vacancy):
	type =OFPTMPT_VACANCY
	length = 8
	return _pack("HH3Bx", type, length, vacancy_down, vacancy_up, vacancy)

def ofp_table_mod_prop_experimenter(type, length, experimenter, exp_type, experimenter_data):
	type = OFPTMPT_EXPERIMENTER
	length = 12 + _len(experimenter_data)
	if experimenter_data is None:
		experimenter_data = b""
	return _pack("HHII", type, length, experimenter, exp_type
		) + experimenter_data + b'\0'*(_align(length)-length)

# 7.3.4.1
def ofp_flow_mod(header, cookie, cookie_mask, table_id, command,
		idle_timeout, hard_timeout, priority, buffer_id, out_port, out_group, flags, importance,
		match, instructions):
	'''command=OFPFC_ADD/MODIFY/MODIFY_STRICT/DELETE/DELETE_STRICT
	'''
	if isinstance(instructions, str):
		pass
	elif isinstance(instructions, (tuple,list)):
		instructions = b"".join([_obj(i) for i in instructions])
	elif instructions is None:
		instructions = b""
	else:
		raise ValueError(instructions)
	
	if buffer_id is None:
		buffer_id = 0xffffffff # OFP_NO_BUFFER

	if out_port is None:
		out_port = OFPP_ANY

	if out_group is None:
		out_group = OFPG_ANY

	msg = ofp_(header, _pack("QQBB3H3IHH",
		cookie, cookie_mask,
		table_id, command,
		idle_timeout, hard_timeout,
		priority, buffer_id,
		out_port, out_group,
		flags, importance)+_obj(match)+instructions, 
		OFPT_FLOW_MOD)
	return msg

# 7.3.4.2
def ofp_group_mod(header, command, type, group_id, buckets):
	'''
	command = OFPGC_ADD/MODIFY/DELETE
	type = OFPGT_ALL/SELECT/INDIRECT/FF
	'''
	if isinstance(buckets, str):
		pass
	elif isinstance(buckets, (list, tuple)):
		buckets = b"".join([_obj(b) for b in buckets])
	elif buckets is None:
		buckets = b""
	else:
		raise ValueError(buckets)
	
	msg = ofp_(header,
		_pack("HBxI", command, type, group_id)+buckets,
		OFPT_GROUP_MOD)
	return msg

def ofp_bucket(len, weight, watch_port, watch_group, actions):
	if isinstance(actions, str):
		pass
	elif isinstance(actions, (list, tuple)):
		actions = b"".join([_obj(a) for a in actions])
	elif actions is None:
		actions = b""
	else:
		raise ValueError(actions)
	
	filled_len = 16 + _len(actions)
	len = _align(filled_len)
	
	msg = _pack("HHII4x",
		len,
		weight,
		watch_port,
		watch_group) + actions + b'\0'*(len-filled_len)
	return msg

# 7.3.4.3
def ofp_port_mod(header, port_no, hw_addr, config, mask, properties):
	if isinstance(properties, str):
		pass
	elif isinstance(properties, (list, tuple)):
		properties = b"".join([_obj(p) for p in properties])
	elif properties is None:
		properties = b""
	else:
		raise ValueError(properties)
	
	msg = ofp_(header,
		_pack("I4x6s2xII", port_no, hw_addr, config, mask)+properties,
		OFPT_PORT_MOD)
	return msg

def ofp_port_mod_prop_header(type, length):
	return _pack("HH", type, length)

def ofp_port_mod_prop_ethernet(type, length, advertise):
	type = OFPPMPT_ETHERNET
	length = 8
	return _pack("HHI", type, length, advertise)

def ofp_port_mod_prop_optical(type, length, configure, freq_lmda, fl_offset, grid_span, tx_pwr):
	type = OFPPMPT_OPTICAL
	length = 24
	return _pack("HHIIiII", type, length, configure, freq_lmda, fl_offset, grid_span, tx_pwr)

def ofp_port_mod_prop_experimenter(type, length, experimenter, exp_type, experiimenter_data):
	type = OFPPMPT_EXPERIMENTER
	length = 12 + _len(experiimenter_data)
	if experiimenter_data is None:
		experiimenter_data = b""
	return _pack("HHII", type, length, experimenter, exp_type
		)+experiimenter_data+b'\0'*(_align(length)-length)

# 7.3.4.5
def ofp_meter_mod(header, command, flags, meter_id, bands):
	if isinstance(bands, str):
		pass
	elif isinstance(bands, (list, tuple)):
		bands = b"".join([_obj(b) for b in bands])
	elif bands is None:
		bands = b""
	else:
		raise ValueError(bands)
	
	msg = _pack("8sHHI",
		_obj(header),
		command,
		flags,
		meter_id) + bands
	return msg

def ofp_meter_band_header(type, len, rate, burst_size):
	msg = _pack("HHII", type, len, rate, burst_size)
	assert _len(msg) == 12
	return msg

def ofp_meter_band_drop(type, len, rate, burst_size):
	if type is None:
		type = OFPMBT_DROP
	assert type == OFPMBT_DROP
	
	len = 16
	
	msg = _pack("HHII4x",
		type,
		len,
		rate,
		burst_size)
	assert _len(msg) == 16
	return msg

def ofp_meter_band_dscp_remark(type, len, rate, burst_size, prec_level):
	if type is None:
		type = OFPMBT_DSCP_REMARK
	assert type == OFPMBT_DSCP_REMARK
	
	len = 16
	
	msg = _pack("HHIIB3x",
		type,
		len,
		rate,
		burst_size,
		prec_level)
	assert _len(msg) == 16
	return msg

def ofp_meter_band_experimenter(type, len, rate, burst_size, experimenter, data):
	if type is None:
		type = OFPMBT_EXPERIMENTER
	assert type == OFPMBT_EXPERIMENTER
	
	assert isinstance(data, str)
	
	len = 16 + _len(data)
	# XXX: no _align here in spec
	
	msg = _pack("HHIII",
		type,
		len,
		rate,
		burst_size,
		experimenter) + data
	return msg

# 7.3.5
def ofp_multipart_request(header, type, flags, body=None):
	if type in (OFPMP_DESC, OFPMP_TABLE, OFPMP_GROUP_DESC, 
			OFPMP_GROUP_FEATURES, OFPMP_METER_FEATURES, OFPMP_PORT_DESC):
		body = b""
	elif type in (OFPMP_FLOW, OFPMP_AGGREGATE, OFPMP_PORT_STATS, 
			OFPMP_QUEUE_STATS, OFPMP_GROUP, OFPMP_METER, OFPMP_METER_CONFIG):
		if body is None:
			body = b""
		else:
			body = _obj(body)
	elif type == OFPMP_TABLE_FEATURES:
		if isinstance(body, str):
			pass
		elif isinstance(body, (list, tuple)):
			body = b"".join([_obj(b) for b in body])
		elif body is None:
			body = []
	
	msg = ofp_(header,
		_pack("HH4x", type, flags) + body,
		OFPT_MULTIPART_REQUEST)
	return msg

def ofp_multipart_reply(header, type, flags, body):
	if type in (OFPMP_DESC, OFPMP_AGGREGATE, OFPMP_GROUP_FEATURES,
			OFPMP_METER_FEATURES):
		if isinstance(body, (tuple,str)):
			body = _obj(body)
		elif body is None:
			body = b""
		else:
			raise ValueError(body)
	elif type in (OFPMP_FLOW, OFPMP_TABLE, OFPMP_PORT_STATS, OFPMP_QUEUE_STATS, 
			OFPMP_GROUP, OFPMP_GROUP_DESC, OFPMP_METER, OFPMP_METER_CONFIG,
			OFPMP_TABLE_FEATURES, OFPMP_PORT_DESC):
		if isinstance(body, (list,tuple)):
			body = b"".join([_obj(b) for b in body])
		elif body is None:
			body = b""
		else:
			raise ValueError(body)
	elif type == OFPMP_EXPERIMENTER:
		if isinstance(body, str):
			pass
		else:
			raise ValueError(body)
	else:
		raise ValueError(type)
	
	msg = ofp_(header,
		_pack("HH4x", type, flags) + body,
		OFPT_MULTIPART_REPLY)
	return msg

# 7.3.5.1
def ofp_desc(mfr_desc, hw_desc, sw_desc, serial_num, dp_desc):
	if mfr_desc is None:
		mfr_desc = b""
	if hw_desc is None:
		hw_desc = b""
	if sw_desc is None:
		sw_desc = b""
	if serial_num is None:
		serial_num = b""
	if dp_desc is None:
		dp_desc = b""
	msg = _pack("256s256s256s32s256s",
		mfr_desc,
		hw_desc,
		sw_desc,
		serial_num,
		dp_desc)
	assert _len(msg) == 1056
	return msg

# 7.3.5.2
def ofp_flow_stats_request(table_id, out_port, out_group, cookie, cookie_mask, match):
	if table_id is None:
		table_id = OFPTT_ALL
	if out_port is None:
		out_port = OFPP_ANY
	if out_group is None:
		out_group = OFPG_ANY
	if cookie is None:
		cookie = 0
	if cookie_mask is None:
		cookie_mask = 0
	if match is None:
		match = ofp_match(None, None, [])
	desc = _pack("B3xII4xQQ", table_id, out_port, out_group, cookie, cookie_mask)
	assert _len(desc)==32
	return desc+_obj(match)

def ofp_flow_stats(length, table_id, duration_sec, duration_nsec, priority,
		idle_timeout, hard_timeout, flags, cookie, packet_count, byte_count,
		match, instructions):
	if instructions is None:
		instructions = b""
	elif isinstance(instructions, (list, tuple)):
		instructions = b"".join([_obj(i) for i in instructions])
	elif isinstance(instructions, str):
		pass
	else:
		raise ValueError(instructions)
	
	match = _obj(match)
	
	length = 48 + _len(match) + _len(instructions)
	msg = _pack("HBxII4H4x3Q", length, table_id, duration_sec, duration_nsec,
		priority, idle_timeout, hard_timeout, flags,
		cookie, packet_count, byte_count)+match+instructions
	assert _len(msg) == length
	return msg

# 7.3.5.3
def ofp_aggregate_stats_request(table_id, out_port, out_group, cookie, cookie_mask, match):
	if table_id is None:
		table_id = OFPTT_ALL
	if out_port is None:
		out_port = OFPP_ANY
	if out_group is None:
		out_group = OFPG_ANY
	if cookie is None:
		cookie = 0
	if cookie_mask is None:
		cookie_mask = 0
	desc = _pack("B3xII4xQQ", table_id, out_port, out_group, cookie, cookie_mask)
	assert len(desc) == 40
	return desc + _obj(match)

def ofp_aggregate_stats_reply(packet_count, byte_count, flow_count):
	return _pack("QQI4x", packet_count, byte_count, flow_count)

# 7.3.5.4
def ofp_table_stats(table_id, active_count, lookup_count, matched_count):
	msg = _pack("B3xIQQ", table_id, active_count, lookup_count, matched_count)
	assert _len(msg) == 24
	return msg

# 7.3.5.5
def ofp_table_desc(length, table_id, config, properties):
	if isinstance(properties, (list,tuple)):
		properties = b"".join([_obj(p) for p in properties])
	elif isinstance(properties, str):
		pass
	elif properties is None:
		properties = b""
	else:
		raise ValueError(properties)
	
	length = 8 + _len(properties)
	return _pack("HBxI", length, table_id, config) + properties

# 7.3.5.5.1
def ofp_table_features(length, table_id, name, metadata_match, metadata_write, capabilities, max_entries, properties):
	if isinstance(properties, (list,tuple)):
		properties = b"".join([_obj(p) for p in properties])
	elif isinstance(properties, str):
		pass
	elif properties is None:
		properties = b""
	else:
		raise ValueError(properties)
	
	length = 64 + _len(properties)
	
	msg = _pack("HB5x32sQQII", length, table_id, name, metadata_match, metadata_write,
		capabilities, max_entries) + properties
	assert _len(msg) == length
	return msg

# 7.3.5.5.2
def ofp_table_feature_prop_header(type, length):
	return _pack("HH", type, length)

def ofp_table_feature_prop_instructions(type, length, instruction_ids):
	if isinstance(instruction_ids, (list,tuple)):
		instruction_ids = b"".join([_obj(i) for i in instruction_ids])
	elif isinstance(instruction_ids, str):
		pass
	elif instruction_ids is None:
		instruction_ids = b""
	else:
		raise ValueError(instruction_ids)
	
	assert type in (OFPTFPT_INSTRUCTIONS, OFPTFPT_INSTRUCTIONS_MISS)
	
	length = 4 + _len(instruction_ids)
	
	return _pack("HH", type, length) + instruction_ids + b'\0'*(_align(length)-length)

def ofp_instruction_id(type, len, exp_data):
	if type in (OFPTFPT_EXPERIMENTER, OFPTFPT_EXPERIMENTER_MISS):
		if exp_data is None:
			exp_data = b""
	else:
		exp_data = b""
	
	len = 4 + _len(exp_data)
	return _pack("HH", type, len) + exp_data

def ofp_table_feature_prop_tables(type, length, table_ids):
	if isinstance(table_ids, (list,tuple)):
		table_ids = b"".join([_obj(n) for n in table_ids])
	elif isinstance(table_ids, str):
		pass
	elif table_ids is None:
		table_ids = b""
	else:
		raise ValueError(table_ids)
	
	assert type in (OFPTFPT_NEXT_TABLES, OFPTFPT_NEXT_TABLES_MISS)
	
	length = 4 + _len(table_ids)
	
	return _pack("HH", type, length) + table_ids + b'\0'*(_align(length)-length)

def ofp_table_feature_prop_actions(type, length, action_ids):
	if isinstance(action_ids, (list,tuple)):
		action_ids = b"".join([_obj(a) for a in action_ids])
	elif isinstance(action_ids, str):
		pass
	elif action_ids is None:
		action_ids = b""
	else:
		raise ValueError(action_ids)
	
	assert type in (OFPTFPT_WRITE_ACTIONS, OFPTFPT_WRITE_ACTIONS_MISS,
		OFPTFPT_APPLY_ACTIONS, OFPTFPT_APPLY_ACTIONS_MISS)
	
	length = 4 + _len(action_ids)
	
	return _pack("HH", type, length) + action_ids + b'\0'*(_align(length)-length)

def ofp_action_id(type, len, exp_data):
	if type == OFPAT_EXPERIMENTER:
		if exp_data is None:
			exp_data = b""
	else:
		exp_data = b""
	
	len = 4 + _len(exp_data)
	return _pack("HH", type, len) + exp_data

def ofp_table_feature_prop_oxm(type, length, oxm_ids):
	if isinstance(oxm_ids, (list,tuple)):
		oxm_ids = _pack("%dI" % len(oxm_ids), *oxm_ids)
	elif isinstance(oxm_ids, str):
		pass
	elif oxm_ids is None:
		oxm_ids = b""
	else:
		raise ValueError(oxm_ids)
	
	assert type in (OFPTFPT_MATCH, OFPTFPT_WILDCARDS, OFPTFPT_WRITE_SETFIELD, OFPTFPT_WRITE_SETFIELD_MISS, 
		OFPTFPT_APPLY_SETFIELD, OFPTFPT_APPLY_SETFIELD_MISS)
	
	length = 4 + _len(oxm_ids)
	
	return _pack("HH", type, length) + oxm_ids + b'\0'*(_align(length)-length)

def ofp_table_feature_prop_experimenter(type, length, experimenter, exp_type, data):
	assert isinsntace(data, str)
	
	length = 12 + _len(data)
	
	assert type in (OFPTFPT_EXPERIMENTER, OFPTFPT_EXPERIMENTER_MISS)
	
	return _pack("HHII", type, length, experimenter, exp_type) + data

# 7.3.5.6
def ofp_port_stats_request(port_no):
	if port_no is None:
		port_no = OFPP_ANY
	return _pack("I4x", port_no)

def ofp_port_stats(length, port_no, duration_sec, duration_nsec,
		rx_packets, tx_packets, rx_bytes, tx_bytes, rx_dropped, tx_dropped,
		rx_errors, tx_errors, properties):
	if isinstance(properties, (list,tuple)):
		properties = b"".join([_obj(p) for p in properties])
	elif isinstance(properties, str):
		pass
	elif properties is None:
		properties = b""
	else:
		raise ValueError(properties)
	
	length = 80 + _len(properties)
	return _pack("H2x3I8Q", length, port_no, duration_sec, duration_nsec,
		rx_packets, tx_packets, rx_bytes, tx_bytes, rx_dropped, tx_dropped,
		rx_errors, tx_errors) + properties

def ofp_port_stats_prop_header(type, length):
	return _pack("HH", type, length)

def ofp_port_stats_prop_ethernet(type, length,
		rx_frame_err, rx_over_err, rx_crc_err, collisions):
	type = OFPPSPT_ETHERNET
	length = 40
	return _pack("HH4x4Q", type, length, rx_frame_err, rx_over_err, rx_crc_err, collisions)

def ofp_port_stats_prop_optical(type, length,
		flags,
		tx_freq_lmda, tx_offset, tx_grid_span,
		rx_freq_lmda, rx_offset, rx_grid_span,
		tx_pwr, rx_pwr, bias_current, temperature):
	type = OFPPSPT_OPTICAL
	length = 44
	return _pack("HH4x7I4H", type, length,
		flags,
		tx_freq_lmda, tx_offset, tx_grid_span,
		rx_freq_lmda, rx_offset, rx_grid_span,
		tx_pwr, rx_pwr, bias_current, temperature)

def ofp_port_stats_prop_experimenter(type, length,
		experimenter, exp_type, experimenter_data):
	type = OFPPSPT_EXPERIMENTER
	if experimenter_data is None:
		experimenter_data = b""
	length = 12 + _len(experimenter_data)
	return _pack("HHII", type, length,
		experimenter, exp_type) + experimenter_data

# 7.3.5.9
def ofp_queue_stats_request(port_no, queue_id):
	if port_no is None:
		port_no = OFPP_ANY
	if queue_id is None:
		queue_id = OFPQ_ALL
	return _pack("II", port_no, queue_id)

def ofp_queue_stats(length, port_no, queue_id, tx_bytes, tx_packets, tx_errors, duration_sec, duration_nsec, properties):
	if isinstance(properties, str):
		pass
	elif isinstance(properties, (list, tuple)):
		properties = b"".join([_obj(p) for p in properties])
	elif properties is None:
		properties = b""
	else:
		raise ValueError(properties)
	
	length = 48 + _len(properties)
	return _pack("H6x2I3Q2I", length, port_no, queue_id, tx_bytes, tx_packets, tx_errors, duration_sec, duration_nsec
		)+properties

def ofp_queue_stats_prop_header(type, length):
	return _pack("HH", type, length)

def ofp_queue_stats_prop_experimenter(type, length, experimenter, exp_type, experimenter_data):
	type = OFPQSPT_EXPERIMENTER
	length = 12 + _len(experimenter_data)
	return _pack("HHII", type, length, experimenter, exp_type) + experimenter_data + b'\0'*(_align(length)-length)

# 7.3.5.10
def ofp_queue_desc_request(port_no, queue_id):
	if port_no is None:
		port_no = OFPP_ANY
	if queue_id is None:
		queue_id = OFPQ_ALL
	return _pack("II", port_no, queue_id)

def ofp_queue_desc(port_no, queue_id, len, properties):
	if isinstance(properties, str):
		pass
	elif isinstance(properties, (list, tuple)):
		properties = b"".join([_obj(p) for p in properties])
	elif properties is None:
		properties = b""
	else:
		raise ValueError(properties)
	
	len = 16 + _len(properties)
	
	desc = _pack("IIH6x",
		port_no,
		queue_id,
		len)
	assert _len(desc)==16
	return desc + properties

def ofp_queue_desc_prop_header(type, len):
	# XXX: You won't need this function
	return _pack("HH4x", type, len)

def ofp_queue_desc_prop_min_rate(type, length, rate):
	type = OFPQDPT_MIN_RATE
	length = 8
	return _pack("HHH2x", type, length, rate)

def ofp_queue_desc_prop_max_rate(type, length, rate):
	type = OFPQDPT_MAX_RATE
	length = 8
	return _pack("HHH2x", type, length, rate)

def ofp_queue_desc_prop_experimenter(type, length, experimenter, exp_type, experimenter_data):
	type = OFPQDPT_EXPERIMENTER
	length = 12 + _len(data)
	return _pack("HHII", type, length, experimenter, exp_type
		) + experimenter_data + b'\0'*(_align(length)-length)

# 7.3.5.9
def ofp_group_stats_request(group_id):
	if group_id is None:
		group_id = OFPG_ALL
	return _pack("I4x", group_id)

def ofp_group_stats(length, group_id, ref_count, packet_count, byte_count,
		duration_sec, duration_nsec, bucket_stats):
	if isinstance(bucket_stats, (list,tuple)):
		bucket_stats = b"".join([_obj(b) for b in bucket_stats])
	elif isinstance(bucket_stats, str):
		pass
	elif bucket_stats is None:
		bucket_stats = b""
	else:
		raise ValueError(bucket_stats)
	
	length = 40 + _len(bucket_stats)
	
	return _pack("H2xII4xQQII", length, group_id, ref_count, packet_count, byte_count,
		duration_sec, duration_nsec) + bucket_stats

def ofp_bucket_counter(packet_count, byte_count):
	return _pack("QQ", packet_count, byte_count)

# 7.3.5.10
def ofp_group_desc(length, type, group_id, buckets):
	if isinstance(buckets, (list,tuple)):
		buckets = b"".join([_obj(b) for b in buckets])
	elif isinstance(buckets, str):
		pass
	elif buckets is None:
		buckets = b""
	else:
		raise ValueError(buckets)
	
	length = 8 + _len(buckets)
	
	return _pack("HBxI", length, type, group_id) + buckets

# 7.3.5.11
def ofp_group_features(types, capabilities, max_groups, actions):
	if isinstance(max_groups, (list,tuple)):
		max_groups = _pack("4I", *max_groups)
	elif isinstance(max_groups, str):
		assert len(max_groups) == 16
	elif max_groups is None:
		max_groups = b'\0'*16
	else:
		raise ValueError(max_groups)
	
	if isinstance(actions, (list,tuple)):
		actions = _pack("4I", *actions)
	elif isinstance(actions, str):
		assert len(actions) == 16
	elif actions is None:
		actions = b'\0'*16
	else:
		raise ValueError(actions)
	
	return _pack("II", types, capabilities) + max_groups + actions

# 7.3.5.14
def ofp_meter_multipart_request(meter_id):
	return _pack("I4x", meter_id)

def ofp_meter_stats(meter_id, len, flow_count, packet_in_count, byte_in_count,
		duration_sec, duration_nsec, band_stats):
	if isinstance(band_stats, (list, tuple)):
		band_stats = b"".join([_obj(b) for b in band_stats])
	elif isinstance(band_stats, str):
		pass
	elif band_stats is None:
		band_stats = b""
	else:
		raise ValueError(band_stats)
	
	return _pack("IH6xIQQII", meter_id, len, flow_count, packet_in_count, byte_in_count,
		duration_sec, duration_nsec) + band_stats

def ofp_meter_band_stats(packet_band_count, byte_band_count):
	return _pack("QQ", packet_band_count, byte_band_count)

# 7.3.5.13
def ofp_meter_config(length, flags, meter_id, bands):
	if isinstance(bands, (list,tuple)):
		bands = b"".join([_obj(b) for b in bands])
	elif isinstance(bands, str):
		pass
	elif bands is None:
		bands = b""
	else:
		raise ValueError(bands)
	
	length = 8 + _len(bands)
	
	return _pack("HHI", length, flags, meter_id) + bands

# 7.3.5.16
def ofp_meter_features(max_meter, band_types, capabilities, max_bands, max_color):
	return _pack("IIIBB2x", max_meter, band_types, capabilities, max_bands, max_color)

# 7.3.5.17
def ofp_flow_monitor_request(monitor_id, out_port, out_group,
		flags, table_id, command, match):
	return _pack("3IHBB", monitor_id, out_port, out_group,
		flags, table_id, command)+_obj(match)

# 7.3.5.17.2
def ofp_flow_update_full(length, event, table_id, reason,
		idle_timeout, hard_timeout, priority, cookie, match, instructions):
	
	if isinstance(instructions, str):
		pass
	elif isinstance(instructions, (list, tuple)):
		instructions = b"".join([_obj(p) for p in instructions])
	elif instructions is None:
		instructions = b""
	else:
		raise ValueError(instructions)
	
	match = _obj(match)
	length = 32+_len(match)+_len(instructions)
	return _pack("HHBB3H4xQ", length, event, table_id, reason,
		idle_timeout, hard_timeout, priority, cookie)+match+instructions

def ofp_flow_update_abbrev(length, event, xid):
	length = 8
	event = OFPFME_ABBREV
	return _pack("HHI", length, event, xid)

def ofp_flow_update_paused(length, event):
	length = 8
	return _pack("HH4x", length, event)

# 7.3.5.15
def ofp_experimenter_multipart_header(experimenter, exp_type):
	return _pack("II", experimenter, exp_type)

# 7.3.7
def ofp_packet_out(header, buffer_id, in_port, actions_len, actions, data):
	if isinstance(actions, (list,tuple)):
		actions = b"".join([_obj(a) for a in actions])
	elif isinstance(actions, str):
		pass
	elif actions is None:
		actions = b""
	else:
		raise ValueError(actions)
	
	if isinstance(data, str):
		pass
	elif data is None:
		data = b""
	else:
		raise ValueError(data)
	
	if buffer_id is None:
		buffer_id = OFP_NO_BUFFER
	
	actions_len = _len(actions)
	
	return ofp_(header,
		_pack("IIH6x", buffer_id, in_port, actions_len) + actions + data,
		OFPT_PACKET_OUT)

# 7.3.8
def ofp_role_request(header, role, generation_id):
	return ofp_(header,
		_pack("I4xQ", role, generation_id),
		(OFPT_ROLE_REQUEST, OFPT_ROLE_REPLY))

# 7.3.9.1
def ofp_bundle_ctrl_msg(header, bundle_id, type, flags, properties):
	if isinstance(properties, str):
		pass
	elif isinstance(properties, (list, tuple)):
		properties = b"".join([_obj(p) for p in properties])
	elif properties is None:
		properties = b""
	else:
		raise ValueError(properties)
	
	return ofp_(header,
		_pack("IHH", bundle_id, type, flags)+properties,
		OFPT_BUNDLE_CONTROL)

# 7.3.9.2
def ofp_bundle_add_msg(header, bundle_id, flags, message, properties):
	if isinstance(properties, str):
		pass
	elif isinstance(properties, (list, tuple)):
		properties = b"".join([_obj(p) for p in properties])
	elif properties is None:
		properties = b""
	else:
		raise ValueError(properties)
	
	return ofp_(header,
		_pack("I2xH", bundle_id, flags)+_obj(message)+properties,
		OFPT_BUNDLE_ADD_MESSAGE)

# 7.3.9.4
def ofp_bundle_prop_header(type, length):
	return _pack("HH", type, length)

def ofp_bundle_prop_experimenter(type, length,
		experimenter, exp_type, experimenter_data):
	type = OFPBPT_EXPERIMENTER
	length = 12 + _len(experimenter_data)
	
	return _pack("HHII", type, length, experimenter, exp_type
		)+experimenter_data+b'\0'*(_align(length)-length)

# 7.3.10
def ofp_async_config(header, properties):
	if isinstance(properties, str):
		pass
	elif isinstance(properties, (list, tuple)):
		properties = b"".join([_obj(p) for p in properties])
	elif properties is None:
		properties = b""
	else:
		raise ValueError(properties)
	
	return ofp_(header,
		properties,
		(OFPT_GET_ASYNC_REPLY, OFPT_SET_ASYNC))

def ofp_async_config_prop_header(type, length):
	return _pack("HH", type, length)

def ofp_async_config_prop_reasons(type, length, mask):
	assert type in (OFPACPT_PACKET_IN_SLAVE, OFPACPT_PACKET_IN_MASTER,
		OFPACPT_PORT_STATUS_SLAVE, OFPACPT_PORT_STATUS_MASTER,
		OFPACPT_FLOW_REMOVED_SLAVE, OFPACPT_FLOW_REMOVED_MASTER,
		OFPACPT_ROLE_STATUS_SLAVE, OFPACPT_ROLE_STATUS_MASTER,
		OFPACPT_TABLE_STATUS_SLAVE, OFPACPT_TABLE_STATUS_MASTER,
		OFPACPT_REQUESTFORWARD_SLAVE, OFPACPT_REQUESTFORWARD_MASTER)
	length = 8
	return _pack("HHI", type, length, mask)

def ofp_async_config_prop_experimenter(type, length,
		experimenter, exp_type, experimenter_data):
	assert type in (OFPACPT_EXPERIIMENTER_SLAVE, OFPACPT_EXPERIMENTER_MASTER)
	length = 12 + _len(experimenter_data)
	return _pack("HHII", type, length, experimenter, exp_type
		)+experimenter_data+b'\0'*(_align(length)-length)

# 7.4.1
def ofp_packet_in(header, buffer_id, total_len, reason, table_id, cookie, match, data):
	return ofp_(header,
		_pack("IHBBQ", buffer_id, total_len, reason, table_id, cookie) + _obj(match) + b"\0"*2 + data,
		OFPT_PACKET_IN)

# 7.4.2
def ofp_flow_removed(header, cookie, priority, reason, table_id,
		duration_sec, duration_nsec, idle_timeout, hard_timeout,
		packet_count, byte_count, match):
	return ofp_(header,
		_pack("QHBBIIHHQQ", cookie, priority, reason, table_id,
			duration_sec, duration_nsec, idle_timeout, hard_timeout,
			packet_count, byte_count) + _obj(match),
		OFPT_FLOW_REMOVED)

# 7.4.3
def ofp_port_status(header, reason, desc):
	return ofp_(header,
		_pack("B7x", reason) + _obj(desc),
		OFP_PORT_STATUS)

# 7.4.4
def ofp_role_status(header, role, reason, generation_id, properties):
	if isinstance(properties, str):
		pass
	elif isinstance(properties, (list, tuple)):
		properties = b"".join([_obj(p) for p in properties])
	elif properties is None:
		properties = b""
	else:
		raise ValueError(properties)
	
	return ofp_(header,
		_pack("IB3xQ", role, reason, generation_id)+properties,
		(OFPT_ROLE_REQUEST, OFPT_ROLE_REPLY))

def ofp_role_prop_header(type, length):
	return _pack("HH", type, length)

def ofp_role_prop_experimenter(type, length, experimenter, exp_type, experimenter_data):
	type = OFPRPT_EXPERIMENTER
	if experimenter_data is None:
		experimenter_data = b""
	length = 12 + _len(experimenter_data)
	return _pack("HHII", type, length, experimenter, exp_type
		) + experimenter_data + b'\0'*(_align(length)-length)

# 7.4.5
def ofp_table_status(header, reason, table):
	return ofp_(header,
		_pack("H7x", reason)+_obj(table),
		OFPT_TABLE_STATUS)

# 7.4.6
def ofp_requestforward_header(header, request):
	return ofp_(header,
		_obj(request),
		OFPT_REQUESTFORWARD)

# 7.5.1
def ofp_hello(header, elements):
	if isinstance(elements, str):
		pass
	elif isinstance(elements, (tuple, list)):
		elements = b"".join([_obj(e) for e in elements])
	elif elements is None:
		elements = b""
	else:
		raise ValueError(elements)
	
	return ofp_(header, elements, OFPT_HELLO)

def ofp_hello_elem_header(type, length):
	return _pack("HH", type, length)

def ofp_hello_elem_versionbitmap(type, length, bitmaps):
	if type is None:
		type = 1
	assert type == 1 # VERSIONBITMAP
	
	if isinstance(bitmaps, str):
		pass
	elif isinstance(bitmaps, (tuple, list)):
		bitmaps = b"".join([_pack("I",e) for e in bitmaps])
	elif bitmaps is None:
		bitmaps = b""
	else:
		raise ValueError("%s" % bitmaps)
	
	length = 4 + _len(bitmaps)
	
	return struct.pack("!HH", type, length) + bitmaps + b'\0'*(_align(length)-length)

# 7.5.4
def ofp_error_msg(header, type, code, data):
	if data is None:
		data = b""
	return ofp_(header,
		_pack("HH", type, code)+data,
		OFPT_ERROR)

def ofp_error_experimenter_msg(header, type, exp_code, experimenter, data):
	type = OFPET_EXPERIMENTER
	return ofp_(header,
		_pack("HHI", type, exp_code, experimenter)+data,
		OFPT_ERROR)

# 7.5.5
def ofp_experimenter_msg(header, experimenter, exp_type, experimenter_data):
	if experimenter_data is None:
		experimenter_data = b""
	return ofp_(header,
		_pack("II", experimenter, exp_type) + experimenter_data,
		OFPT_EXPERIMENTER)
