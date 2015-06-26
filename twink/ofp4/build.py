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
		version = 4
	assert version==4
	
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
		version = 4
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


# 7.2.1
def ofp_port(port_no, hw_addr, name, config, state, 
		curr, advertised, supported, peer, curr_speed, max_speed):
	if isinstance(name, str):
		name = name.encode("UTF-8")
	
	assert isinstance(hw_addr, bytes) and _len(hw_addr)==6
	assert isinstance(name, bytes) and _len(name)<=16
	
	msg = _pack("I4x6s2x16s8I", 
		port_no,
		hw_addr,
		name,
		config,
		state,
		curr,
		advertised,
		supported,
		peer,
		curr_speed,
		max_speed
		)
	assert _len(msg) == 64
	return msg

# 7.2.2
def ofp_packet_queue(queue_id, port, len, properties):
	if isinstance(properties, bytes):
		pass
	elif isinstance(properties, (list, tuple)):
		properties = b"".join([_obj(p) for p in properties])
	elif properties is None:
		properties = b""
	else:
		raise ValueError(properties)
	
	len = 16 + _len(properties)
	
	desc = _pack("IIH6x",
		queue_id,
		port,
		len)
	assert _len(desc)==16
	return desc + properties

def ofp_queue_prop_header(property, len):
	if len is None:
		len = 8
	msg = _pack("HH4x",
		property,
		len)
	assert _len(msg)==8
	return msg

def ofp_queue_prop_(prop_header, data, type=None):
	if isinstance(prop_header, bytes):
		(property,len) = _unpack("HH", prop_header, 0)
		if isinstance(type, int):
			assert property==type
		elif isinstance(type, (list, tuple)):
			assert property in type
		elif type is None:
			pass
		else:
			raise ValueError(type)
	elif isinstance(prop_header, (list, tuple)):
		(property,len) = prop_header
		if isinstance(type, int):
			if property is None:
				property = type
			else:
				assert property==type
		elif isinstance(type, (list, tuple)):
			assert property in type
		elif type is None:
			assert isinstance(property, int)
		else:
			raise ValueError(type)
	elif prop_header is None:
		property = type
	else:
		raise ValueError(prop_header)
	
	data = _obj(data)
	len = _len(data) + 8
	return ofp_queue_prop_header(property,len)+data

def ofp_queue_prop_min_rate(prop_header, rate):
	msg = ofp_queue_prop_(prop_header,
		_pack("H6x", rate),
		OFPQT_MIN_RATE)
	assert _len(msg)==16
	return msg

def ofp_queue_prop_max_rate(prop_header, rate):
	msg = ofp_queue_prop_(prop_header,
		_pack("H6x", rate),
		OFPQT_MAX_RATE)
	assert _len(msg)==16
	return msg

def ofp_queue_prop_experimenter(prop_header, experimenter, data):
	msg = ofp_queue_prop_(prop_header, 
		_pack("I4x", experimenter)+data,
		OFPQT_EXPERIMENTER)
	return msg

# 7.2.3.1
def ofp_match(type, length, oxm_fields):
	'''type: OFPMT_STANDARD/OXM
	'''
	if type is None:
		type = OFPMT_OXM
	
	if isinstance(oxm_fields, bytes):
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
def ofp_instruction(type, len):
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
	if isinstance(actions, bytes):
		pass
	elif isinstance(actions, (tuple, list)):
		actions = b"".join([_obj(a) for a in actions])
	elif actions is None:
		actions = b""
	else:
		raise ValueError(actions)
	
	assert type in (OFPIT_WRITE_ACTIONS, OFPIT_APPLY_ACTIONS, OFPIT_CLEAR_ACTIONS)
	
	len = 8 + _len(actions)
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

def ofp_instruction_experimenter(type, len, experimenter, data):
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

# 7.2.5
def ofp_action_header(type, len):
	return _pack("HH4x", type, len)

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

def ofp_action_experimenter_(type, len, experimenter, data):
	if type is None:
		type = OFPAT_EXPERIMENTER
	assert type == OFPAT_EXPERIMENTER
	
	assert isinstance(data, bytes)
	
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
def ofp_table_mod(header, table_id, config):
	msg = ofp_(header, _pack("B3xI",
		table_id,
		config), OFPT_TABLE_MOD)
	assert _len(msg) == 16
	return msg

# 7.3.4.1
def ofp_flow_mod(header, cookie, cookie_mask, table_id, command,
		idle_timeout, hard_timeout, priority, buffer_id, out_port, out_group, flags,
		match, instructions):
	'''command=OFPFC_ADD/MODIFY/MODIFY_STRICT/DELETE/DELETE_STRICT
	'''
	if isinstance(instructions, bytes):
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
	
	msg = ofp_(header, _pack("QQBB3H3IH2x",
		cookie, cookie_mask,
		table_id, command,
		idle_timeout, hard_timeout,
		priority, buffer_id,
		out_port, out_group,
		flags)+_obj(match)+instructions, 
		OFPT_FLOW_MOD)
	return msg

# 7.3.4.2
def ofp_group_mod(header, command, type, group_id, buckets):
	'''
	command = OFPGC_ADD/MODIFY/DELETE
	type = OFPGT_ALL/SELECT/INDIRECT/FF
	'''
	if isinstance(buckets, bytes):
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
	if isinstance(actions, bytes):
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
def ofp_port_mod(header, port_no, hw_addr, config, mask, advertise):
	msg = ofp_(header,
		_pack("I4x6s2xIII4x", port_no, hw_addr, config, mask, advertise),
		OFPT_PORT_MOD)
	assert _len(msg)==40
	return msg


# 7.3.4.4
def ofp_meter_mod(header, command, flags, meter_id, bands):
	if isinstance(bands, bytes):
		pass
	elif isinstance(bands, (list, tuple)):
		bands = b"".join([_obj(b) for b in bands])
	elif bands is None:
		bands = b""
	else:
		raise ValueError(bands)
	
	msg = ofp_(header,
		_pack("HHI", command, flags, meter_id) + bands,
		OFPT_METER_MOD)
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
	
	assert isinstance(data, bytes)
	
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
			OFPMP_QUEUE, OFPMP_GROUP, OFPMP_METER, OFPMP_METER_CONFIG):
		if body is None:
			body = b""
		else:
			body = _obj(body)
	elif type == OFPMP_TABLE_FEATURES:
		if isinstance(body, bytes):
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
		if isinstance(body, (tuple,bytes)):
			body = _obj(body)
		elif body is None:
			body = b""
		else:
			raise ValueError(body)
	elif type in (OFPMP_FLOW, OFPMP_TABLE, OFPMP_PORT_STATS, OFPMP_QUEUE, 
			OFPMP_GROUP, OFPMP_GROUP_DESC, OFPMP_METER, OFPMP_METER_CONFIG,
			OFPMP_TABLE_FEATURES, OFPMP_PORT_DESC):
		if isinstance(body, (list,tuple)):
			body = b"".join([_obj(b) for b in body])
		elif body is None:
			body = b""
		else:
			raise ValueError(body)
	elif type == OFPMP_EXPERIMENTER:
		if isinstance(body, bytes):
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
	elif isinstance(instructions, bytes):
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

# 7.3.5.5.1
def ofp_table_features(length, table_id, name, metadata_match, metadata_write, config, max_entries, properties):
	if isinstance(properties, (list,tuple)):
		properties = b"".join([_obj(p) for p in properties])
	elif isinstance(properties, bytes):
		pass
	elif properties is None:
		properties = b""
	else:
		raise ValueError(properties)
	
	length = 64 + _len(properties)
	
	msg = _pack("HB5x32sQQII", length, table_id, name, metadata_match, metadata_write,
		config, max_entries) + properties
	assert _len(msg) == length
	return msg

# 7.3.5.5.2
def ofp_table_feature_prop_header(type, length):
	return _pack("HH", type, length)

def ofp_table_feature_prop_instructions(type, length, instruction_ids):
	if isinstance(instruction_ids, (list,tuple)):
		instruction_ids = b"".join([_obj(i) for i in instruction_ids])
	elif isinstance(instruction_ids, bytes):
		pass
	elif instruction_ids is None:
		instruction_ids = b""
	else:
		raise ValueError(instruction_ids)
	
	assert type in (OFPTFPT_INSTRUCTIONS, OFPTFPT_INSTRUCTIONS_MISS)
	
	length = 4 + _len(instruction_ids)
	
	return _pack("HH", type, length) + instruction_ids + b'\0'*(_align(length)-length)

def ofp_table_feature_prop_next_tables(type, length, next_table_ids):
	if isinstance(next_table_ids, (list,tuple)):
		next_table_ids = b"".join([_obj(n) for n in next_table_ids])
	elif isinstance(next_table_ids, bytes):
		pass
	elif next_table_ids is None:
		next_table_ids = b""
	else:
		raise ValueError(next_table_ids)
	
	assert type in (OFPTFPT_NEXT_TABLES, OFPTFPT_NEXT_TABLES_MISS)
	
	length = 4 + _len(next_table_ids)
	
	return _pack("HH", type, length) + next_table_ids + b'\0'*(_align(length)-length)

def ofp_table_feature_prop_actions(type, length, action_ids):
	if isinstance(action_ids, (list,tuple)):
		action_ids = b"".join([_obj(a) for a in action_ids])
	elif isinstance(action_ids, bytes):
		pass
	elif action_ids is None:
		action_ids = b""
	else:
		raise ValueError(action_ids)
	
	assert type in (OFPTFPT_WRITE_ACTIONS, OFPTFPT_WRITE_ACTIONS_MISS,
		OFPTFPT_APPLY_ACTIONS, OFPTFPT_APPLY_ACTIONS_MISS)
	
	length = 4 + _len(action_ids)
	
	return _pack("HH", type, length) + action_ids + b'\0'*(_align(length)-length)

def ofp_table_feature_prop_oxm(type, length, oxm_ids):
	if isinstance(oxm_ids, (list,tuple)):
		oxm_ids = _pack("%dI" % len(oxm_ids), *oxm_ids)
	elif isinstance(oxm_ids, bytes):
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
	assert isinsntace(data, bytes)
	
	length = 12 + _len(data)
	
	assert type in (OFPTFPT_EXPERIMENTER, OFPTFPT_EXPERIMENTER_MISS)
	
	return _pack("HHII", type, length, experimenter, exp_type) + data

# 7.3.5.6
def ofp_port_stats_request(port_no):
	if port_no is None:
		port_no = OFPP_ANY
	return _pack("I4x", port_no)

def ofp_port_stats(port_no, rx_packets, tx_packets, rx_bytes, tx_bytes, rx_dropped, tx_dropped,
		rx_errors, tx_errors, rx_frame_err, rx_over_err, rx_crc_err,
		collisions, duration_sec, duration_nsec):
	return _pack("I4x12Q2I", port_no, rx_packets, tx_packets, rx_bytes, tx_bytes, rx_dropped, tx_dropped,
		rx_errors, tx_errors, rx_frame_err, rx_over_err, rx_crc_err,
		collisions, duration_sec, duration_nsec)

# 7.3.5.8
def ofp_queue_stats_request(port_no, queue_id):
	if port_no is None:
		port_no = OFPP_ANY
	if queue_id is None:
		queue_id = OFPQ_ALL
	return _pack("II", port_no, queue_id)

def ofp_queue_stats(port_no, queue_id, tx_bytes, tx_packets, tx_errors, duration_sec, duration_nsec):
	return _pack("2I3Q2I", port_no, queue_id, tx_bytes, tx_packets, tx_errors, duration_sec, duration_nsec)

# 7.3.5.9
def ofp_group_stats_request(group_id):
	if group_id is None:
		group_id = OFPG_ALL
	return _pack("I4x", group_id)

def ofp_group_stats(length, group_id, ref_count, packet_count, byte_count,
		duration_sec, duration_nsec, bucket_stats):
	if isinstance(bucket_stats, (list,tuple)):
		bucket_stats = b"".join([_obj(b) for b in bucket_stats])
	elif isinstance(bucket_stats, bytes):
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
	elif isinstance(buckets, bytes):
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
	elif isinstance(max_groups, bytes):
		assert len(max_groups) == 16
	elif max_groups is None:
		max_groups = b'\0'*16
	else:
		raise ValueError(max_groups)
	
	if isinstance(actions, (list,tuple)):
		actions = _pack("4I", *actions)
	elif isinstance(actions, bytes):
		assert len(actions) == 16
	elif actions is None:
		actions = b'\0'*16
	else:
		raise ValueError(actions)
	
	return _pack("II", types, capabilities) + max_groups + actions

# 7.3.5.12
def ofp_meter_multipart_request(meter_id):
	return _pack("I4x", meter_id)

def ofp_meter_stats(meter_id, len, flow_count, packet_in_count, byte_in_count,
		duration_sec, duration_nsec, band_stats):
	if isinstance(band_stats, (list, tuple)):
		band_stats = b"".join([_obj(b) for b in band_stats])
	elif isinstance(band_stats, bytes):
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
	elif isinstance(bands, bytes):
		pass
	elif bands is None:
		bands = b""
	else:
		raise ValueError(bands)
	
	length = 8 + _len(bands)
	
	return _pack("HHI", length, flags, meter_id) + bands

# 7.3.5.14
def ofp_meter_features(max_meter, band_types, capabilities, max_bands, max_color):
	return _pack("IIIBB2x", max_meter, band_types, capabilities, max_bands, max_color)

# 7.3.5.15
def ofp_experimenter_multipart_header(experimenter, exp_type):
	return _pack("II", experimenter, exp_type)

# XXX

# 7.3.6
def ofp_queue_get_config_request(header, port):
	return ofp_(header,
		_pack("I4x", port),
		OFPT_QUEUE_GET_CONFIG_REQUEST)

def ofp_queue_get_config_reply(header, port, queues):
	if isinstance(queues, (list,tuple)):
		queues = b"".join([_obj(q) for q in queues])
	elif isinstance(queues, bytes):
		pass
	elif queues is None:
		queues = b""
	else:
		raise ValueError(queues)
	
	return ofp_(header,
		_pack("I4x", port) + queues,
		OFPT_QUEUE_GET_CONFIG_REPLY)

# 7.3.7
def ofp_packet_out(header, buffer_id, in_port, actions_len, actions, data):
	if isinstance(actions, (list,tuple)):
		actions = b"".join([_obj(a) for a in actions])
	elif isinstance(actions, bytes):
		pass
	elif actions is None:
		actions = b""
	else:
		raise ValueError(actions)
	
	if isinstance(data, bytes):
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

# 7.3.9
def ofp_role_request(header, role, generation_id):
	return ofp_(header,
		_pack("I4xQ", role, generation_id),
		(OFPT_ROLE_REQUEST, OFPT_ROLE_REPLY))

# 7.3.10
def ofp_async_config(header, packet_in_mask, port_status_mask, flow_removed_mask):
	return ofp_(header,
		_pack("6I", *packet_in_mask + port_status_mask + flow_removed_mask),
		(OFPT_GET_ASYNC_REPLY, OFPT_SET_ASYNC))

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
def ofp_error_msg(header, type, code, data):
	if data is None:
		data = b""
	return ofp_(header,
		_pack("HH", type, code)+data,
		OFPT_ERROR)

# 7.5.1
def ofp_hello(header, elements):
	if isinstance(elements, bytes):
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
	
	if isinstance(bitmaps, bytes):
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
def ofp_experimenter_header(header, experimenter, exp_type, data):
	return ofp_(header,
		_pack("II", experimenter, exp_type) + data,
		OFPT_EXPERIMENTER)

