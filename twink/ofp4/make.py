from __future__ import absolute_import
import struct
import random
from twink.ofp4 import *

_len = len
_type = type

default_xid = lambda: random.random()*0xFFFFFFFF

def _obj(obj):
	if isinstance(obj, str):
		return obj
	elif isinstance(obj, tuple):
		return eval(obj.__class__.__name__)(*obj)
	else:
		raise ValueError(obj)

def _pack(fmt, *args):
	if fmt[0] != "!":
		fmt = "!"+fmt
	return struct.pack(fmt, *args)

def _align(length):
	return (length+7)/8*8


def fix_ofp_header(type, message):
	assert isinstance(type, int)
	msg = _obj(message)
	return msg[0]+_pack("BH", type, _len(msg))+msg[4:]

# 7.1
def ofp_header(version, type, length, xid):
	if version is None:
		version = 4
	assert version==4
	
	if xid is None:
		xid = default_xid()
	
	return _pack("BBHI", version, type, length, xid)


def ofp_(header, data):
	header = _obj(header)
	type = ord(header[1])
	return fix_ofp_header(type, header+data)


# 7.2.1
def ofp_port(port_no, hw_addr, name, config, state, 
		curr, advertised, supported, peer, curr_speed, max_speed):
	assert isinstance(hw_addr, str) and _len(hw_addr)==6
	assert isinstance(name, str) and _len(name)<=16
	
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
	if isinstance(properties, str):
		pass
	elif isinstance(properties, (list, tuple)):
		properties = "".join([_obj(p) for p in properties])
	elif properties is None:
		properties = ""
	else:
		raise ValueError(properties)
	
	len = 16 + _len(properties)
	
	msg = _pack("IIH6x",
		queue_id,
		port,
		len)
	assert _len(msg)==16
	return msg + properties


def fix_ofp_queue_prop_header(property, message):
	msg = _obj(message)
	return ofp_queue_prop_header(property, _len(msg))+msg[8:]


def ofp_queue_prop_header(property, len):
	if len is None:
		len = 8
	msg = _pack("HH4x",
		property,
		len)
	assert _len(msg)==8
	return msg


def ofp_queue_prop_min_rate(prop_header, rate):
	prop_header = ofp_queue_prop_header(1, 16)
	msg = _pack("8sH6x",
			_obj(prop_header),
			rate)
	assert _len(msg)==16
	return msg


def ofp_queue_prop_max_rate(prop_header, rate):
	prop_header = ofp_queue_prop_header(2, 16)
	msg = _pack("8sH6x",
			_obj(prop_header),
			rate)
	assert _len(msg)==16
	return msg


def ofp_queue_prop_experimenter(prop_header, experimenter, data):
	prop_header = ofp_queue_prop_header(0xFFFF, None)
	msg = fix_ofp_queue_prop_header(0xFFFF, 
		_pack("8sI4x",
			_obj(prop_header),
			experimenter, # experimenter_id
			)+data)
	return msg


def ofp_match(type, length, oxm_fields):
	if isinstance(oxm_fields, str):
		pass
	elif isinstance(oxm_fields, (list, tuple)):
		oxm_fields = "".join([_obj(f) for f in oxm_fields])
	elif oxm_fields is None:
		oxm_fields = ""
	else:
		ValueError(oxm_fields)
	
	length = 4 + _len(oxm_fields)
	
	msg = _pack("HH", type, length) + oxm_fields + "\0"*(_align(length)-length)
	return msg


def ofp_instruction_goto_table(type, len, table_id):
	if type is None:
		type = 1
	assert type==1
	len = 8
	msg = _pack("HHB3x",
		type,
		len,
		table_id)
	assert _len(msg)==8
	return msg


def ofp_instruction_write_metadata(type, len, metadata, metadata_mask):
	if type is None:
		type = 2
	assert type==2
	
	len = 24
	
	msg = _pack("HH4xQQ",
		type,
		len,
		metadata,
		metadata_mask)
	assert _len(msg)==24
	return msg


def ofp_instruction_actions(type, len, actions):
	if isinstance(actions, str):
		pass
	elif isinstance(actions, (tuple, list)):
		actions = "".join([_obj(a) for a in actions])
	elif actions is None:
		actions = ""
	else:
		raise ValueError(actions)
	
	assert type in (3,4,5)
	
	len = 8 + _len(actions)
	msg = _pack("HH4x",
		type,
		len) + actions
	return msg


def ofp_instruction_meter(type, len, meter_id):
	if type is None:
		type = 6
	assert type==6
	
	len = 8
	
	msg = _pack("HHI",
		type,
		len,
		meter_id)
	return msg


def ofp_instruction_experimenter(type, len, experimenter, data):
	if type is None:
		type = 0xFFFF
	assert type == 0xFFFF
	
	assert isinstance(data, str)
	
	len = 8 + _len(data)
	
	msg = _pack("HHI",
		type,
		len,
		experimenter) + data
	return msg


def fix_ofp_action_header(type, message):
	msg = _obj(message)
	return ofp_action_header(type, _len(msg))+msg[8:]


def ofp_action_header(type, len):
	return _pack("HH4x", type, len)


def ofp_action_output(type, len, port, max_len):
	if type is None:
		type = 0
	assert type == 0
	
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
		type = 22
	assert type == 22
	
	len = 8
	
	msg = _pack("HHI",
		type,
		len,
		group_id)
	assert _len(msg) == 8
	return msg


def ofp_action_set_queue(type, len, queue_id):
	if type is None:
		type = 21
	assert type == 21
	
	len = 8
	
	msg = _pack("HHI",
		type,
		len,
		queue_id)
	assert _len(msg) == 8
	return msg


def ofp_action_mpls_ttl(type, len, mpls_ttl):
	if type is None:
		type = 15
	assert type == 15
	
	len = 8
	
	msg = _pack("HHB3x",
		type,
		len,
		mpls_ttl)
	assert _len(msg) == 8
	return msg


def ofp_action_nw_ttl(type, len, nw_ttl):
	if type is None:
		type = 23
	assert type == 23
	
	len = 8
	
	msg = _pack("HHB3x",
		type,
		len,
		nw_ttl)
	assert _len(msg) == 8
	return msg


def ofp_action_push(type, len, ethertype):
	assert type in (17, 19, 26)
	
	len = 8
	
	msg = _pack("3H2x",
		type,
		len,
		ethertype)
	assert _len(msg) == 8
	return msg


def ofp_action_pop_mpls(type, len, ethertype):
	if type is None:
		type = 20
	assert type == 20
	
	len = 8
	
	msg = _pack("3H2x",
		type,
		len,
		ethertype)
	assert _len(msg) == 8
	return msg


def ofp_action_set_field(type, len, field):
	if type is None:
		type = 25
	assert type == 25
	
	assert isinstance(field, str)
	
	filled_len = 4 + len(field)
	len = _align(filled_len)
	
	return _pack("HH", type, len) + field + '\0'*(len-filled_len)


def ofp_action_experimenter(type, len, experimenter, data):
	if type is None:
		type = 0xFFFF
	assert type == 0xFFFF
	
	assert isinstance(data, str)
	
	filled_len = 8 + _len(data)
	len = _align(filled_len)
	
	return _pack("HHI", type, len, experimenter) + data + '\0'*(len-filled_len)


def ofp_switch_features(header, datapath_id, n_buffers, n_tables, auxiliary_id, capabilities):
	if header is None:
		header = ofp_header(4, OFPT_FEATURES_REPLY, 0, None)
	msg = fix_ofp_header(5, _pack("8sQIBB2xII",
		_obj(header),
		datapath_id,
		n_buffers,
		n_tables,
		auxiliary_id,
		capabilities,
		0))
	assert _len(msg) == 32
	return msg


# 7.3.2
def ofp_switch_config(header, flags, miss_send_len):
	msg = fix_ofp_header(9, _pack("8sHH",
		_obj(header),
		flags,
		miss_send_len))
	assert _len(msg) == 12
	return msg


# 7.3.3
def ofp_table_mod(header, table_id, config):
	msg = fix_ofp_header(17, _pack("8sB3xI",
		_obj(header),
		table_id,
		config))
	assert _len(msg) == 16
	return msg


# 7.3.4.1
def ofp_flow_mod(header, cookie, cookie_mask, table_id, command,
		idle_timeout, hard_timeout, priority, buffer_id, out_port, out_group, flags,
		match, instructions):
	if isinstance(instructions. str):
		pass
	elif isinstance(instructions, (list, tuple)):
		instructions = "".join([_obj(i) for i in instructions])
	elif instructions is None:
		instructions = ""
	else:
		ValueError(instructions)
	
	msg = fix_ofp_header(14, _pack("8sQQBBHHHIIIH2x",
		_obj(header),
		cookie,
		cookie_mask,
		table_id,
		command,
		idle_timeout,
		hard_timeout,
		priority,
		buffer_id,
		out_port,
		out_group,
		flags)+_obj(match)+instructions)
	return msg

# 7.3.4.2
def ofp_group_mod(header, command, type, group_id, buckets):
	if header is None:
		header = ofp_header(4, OFPT_GROUP_MOD, 0, None)
	
	if isinstance(buckets, str):
		pass
	elif isinstance(buckets, (list, tuple)):
		buckets = "".join([_obj(b) for b in buckets])
	elif buckets is None:
		buckets = ""
	else:
		raise ValueError(buckets)
	
	msg = fix_ofp_header(15, _pack("8sHBxI",
		_obj(header),
		command,
		type,
		group_id)+buckets)
	return msg


def ofp_bucket(len, weight, watch_port, watch_group, actions):
	if isinstance(actions, str):
		pass
	elif isinstance(actions, (list, tuple)):
		actions = "".join([_obj(a) for a in actions])
	elif actions is None:
		actions = ""
	else:
		raise ValueError(actions)
	
	filled_len = 16 + _len(actions)
	len = _align(filled_len)
	
	msg = _pack("HHII4x",
		len,
		weight,
		watch_port,
		watch_group) + actions + '\0'*(len-filled_len)
	return msg


# 7.3.4.3
def ofp_port_mod(header, port_no, hw_addr, config, mask, advertise):
	msg = fix_ofp_header(16, _pack("8sI4x6s2xIII4x",
		_obj(header),
		port_no,
		hw_addr,
		config,
		mask,
		advertise))
	assert _len(msg)==40
	return msg


# 7.3.4.4
def ofp_meter_mod(header, command, flags, meter_id, bands):
	if isinstance(bands, str):
		pass
	elif isinstance(bands, (list, tuple)):
		bands = "".join([_obj(b) for b in bands])
	elif bands is None:
		bands = ""
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
		type = 1
	assert type == 1
	
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
		type = 2
	assert type == 2
	
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
		type = 0xFFFF
	assert type == 0xFFFF
	
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
	if header is None:
		header = ofp_header(4, OFPT_MULTIPART_REQUEST, 0, None)
	
	if type in (OFPMP_DESC, OFPMP_TABLE, OFPMP_GROUP_DESC, 
			OFPMP_GROUP_FEATURES, OFPMP_METER_FEATURES, OFPMP_PORT_DESC):
		body = ""
	elif type in (OFPMP_FLOW, OFPMP_AGGREGATE, OFPMP_PORT_STATS, 
			OFPMP_QUEUE, OFPMP_GROUP, OFPMP_METER, OFPMP_METER_CONFIG):
		if body is None:
			body = ""
		else:
			body = _obj(body)
	elif type == OFPMP_TABLE_FEATURES:
		if isinstance(body, str):
			pass
		elif isinstance(body, (list, tuple)):
			body = "".join([_obj(b) for b in body])
		elif body is None:
			body = []
	
	msg = fix_ofp_header(OFPT_MULTIPART_REQUEST, _pack("8sHH4x",
		_obj(header),
		type,
		flags) + body)
	return msg


def ofp_multipart_reply(header, type, flags, body):
	if header is None:
		header = ofp_header(4, OFPT_MULTIPART_REPLY, 0, None)
	
	if body is None:
		body = ""
	assert isinstance(body, str)
	
	msg = fix_ofp_header(OFPT_MULTIPART_REPLY, _pack("8sHH4x",
		_obj(header),
		type,
		flags) + body)
	return msg


# 7.3.5.1
def ofp_desc(mfr_desc, hw_desc, sw_desc, serial_num, dp_desc):
	msg = _pack("256s256s256s32s256s",
		mfr_desc,
		hw_desc,
		sw_desc,
		serial_num,
		dp_desc)
	assert _len(msg) == 1056
	return msg


# 7.3.5.2

######################

def ofp_hello(header, elements):
	if header is None:
		header = ofp_header(4, OFPT_HELLO, 0, None)
	
	if isinstance(elements, str):
		pass
	elif isinstance(elements, (tuple, list)):
		elements = "".join([_obj(e) for e in elements])
	elif elements is None:
		elements = ""
	else:
		raise ValueError(elements)
	
	return fix_ofp_header(1, _obj(header)+elements)


def ofp_hello_elem_header(type, length):
	return _pack("HH", type, length)


def ofp_hello_elem_unknown_(type, length, data):
	assert isinstance(data, str)
	
	length = 4 + _len(data)
	
	return _pack("HH", type, length)+data


def ofp_hello_elem_versionbitmap(type, length, bitmaps):
	if type is None:
		type = 1
	assert type == 1 # VERSIONBITMAP
	
	if isinstance(bitmaps, str):
		pass
	elif isinstance(bitmaps, (tuple, list)):
		bitmaps = "".join([_pack("I",e) for e in bitmaps])
	elif bitmaps is None:
		bitmaps = ""
	else:
		raise ValueError("%s" % bitmaps)
	
	length = 4 + _len(bitmaps)
	
	return struct.pack("!HH", type, length) + bitmaps + '\0'*(_align(length)-length)


def ofp_table_mod(header, table_id, config):
	msg = fix_ofp_header("".join([
		_obj(header), 
		_int("B", table_id),
		'\0'*3,
		_int("I", config)
		]))
	assert _len(msg) == 16
	return msg

def ofp_flow_mod(header, cookie, cookie_mask, table_id, command,
		idle_timeout, hard_timeout, priority, buffer_id,
		out_port, out_group, flags, match, instructions):
	if isinstance(instructions, str):
		pass
	elif isinstance(instructions, (tuple,list)):
		instructions = "".join([_obj(i) for i in instructions])
	elif instructions is None:
		instructions = ""
	else:
		raise ValueError(instructions)
	
	msg = fix_ofp_header(14, "".join([
		_obj(header),
		_int("Q", cookie),
		_int("Q", cookie_mask),
		_int("B", table_id),
		_int("B", command),
		_int("H", idle_timeout),
		_int("H", hard_timeout),
		_int("H", priority),
		_int("I", buffer_id),
		_int("I", out_port),
		_int("I", out_group),
		_int("H", flags),
		'\0'*2,
		_obj(match)
		]) + instructions)
	return msg

def ofp_group_stats_request(group_id):
	return _pack("I4x", group_id)

