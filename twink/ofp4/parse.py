from __future__ import absolute_import
from twink.ofp4 import *
import struct
from collections import namedtuple

def _align(length):
	return (length+7)/8*8

class _pos(object):
	offset = 0

def _cursor(offset):
	if isinstance(offset, _pos):
		return offset
	elif isinstance(offset, int):
		ret = _pos()
		ret.offset = offset
		return ret
	else:
		raise ValueError(offset)

def _unpack(fmt, msg, offset):
	cur = _cursor(offset)
	
	if fmt[0] != "!":
		fmt = "!"+fmt
	
	ret = struct.unpack_from(fmt, msg, cur.offset)
	cur.offset += struct.calcsize(fmt)
	return ret

def parse(message, offset=0):
	cursor = _cursor(offset)
	header = ofp_header(message, cursor.offset)
	assert header.version == 4
	if header.type == OFPT_HELLO:
		return ofp_header(message, cursor)
	elif header.type == OFPT_ERROR:
		return ofp_error_msg(message, cursor)
	elif header.type == 
	else:
		return ofp_(message, cursor)

# 7.1
def ofp_header(message, offset):
	cursor = _cursor(offset)
	(version, type, length, xid) = _unpack("BBHI", message, cursor)
	assert version == 4
	return namedtuple("ofp_header",
		"version type length xid")(
		version,type,length,xid)

def ofp_(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	
	data = message[cursor.offset:offset+header.length]
	cursor.offset = offset+header.length
	return namedtuple("ofp_",
		"header,data")(header, data)

# 7.2.1
def ofp_port(message, offset):
	cursor = _cursor(offset)
	p = list(_unpack("I4x6s2x16sII6I", message, cursor))
	p[2] = p[2].partition("\0")[0]
	return namedtuple('''ofp_port hw_addr name
		config state
		curr advertised supported peer
		curr_speed max_speed''')(*p)

# 7.2.2
def ofp_packet_queue(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(queue_id,port,len) = _unpack("IIH6x", message, cursor)
	properties = []
	while cursor.offset < offset + len:
		prop_header = ofp_queue_prop_header(message, cursor.offset)
		if prop_header.property == OFPQT_MIN:
			properties.append(ofp_queue_prop_min_rate(message, cursor)
		elif prop_header.property == OFPQT_MAX:
			properties.append(ofp_queue_prop_max_rate(message, cursor)
		elif prop_header.property == OFPQT_EXPERIMENTER:
			properties.append(ofp_queue_prop_experimenter(message, cursor)
		else:
			raise ValueError(prop_header)
	assert cursor.offset == offset + len
	return namedtuple("ofp_packet_queue",
		"queue_id port len properties")(queue_id,port,len,properties)

def ofp_queue_prop_header(message, offset):
	return namedtuple("ofp_queue_prop_header",
		"property len")(*_unpack("HH4x", message, offset))

def ofp_queue_prop_min_rate(message, offset):
	cursor = _cursor(offset)
	
	prop_header = ofp_queue_prop_header(message, cursor)
	
	(rate,) = _unpack("H6x", message, cursor)
	
	return namedtuple("ofp_queue_prop_min_rate",
		"prop_header rate")(prop_header, rate)

def ofp_queue_prop_max_rate(message, offset):
	cursor = _cursor(offset)
	
	prop_header = ofp_queue_prop_header(message, cursor)
	
	(rate,) = _unpack("H6x", message, cursor)
	
	return namedtuple("ofp_queue_prop_max_rate",
		"prop_header rate")(prop_header, rate)

def ofp_queue_prop_experimenter(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	prop_header = ofp_queue_prop_header(message, cursor)
	
	(experimenter,) = _unpack("I4x", message, cursor)
	
	data = message[cursor.offset:offset+prop_header.len]
	cursor.offset = offset + prop_header.len
	
	return namedtuple("ofp_queue_prop_experimenter",
		"prop_header experimenter data")(prop_header,experimenter,data)

# 7.2.3.1
def ofp_match(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(type,length) = _unpack("HH", message, cursor)
	oxm_fields = message[cursor.offset:offset+length-4]
	cursor.offset = offset+_align(length)
	return namedtuple("ofp_match",
		"type length oxm_fields")(type,length,oxm_fields)

# 7.2.3.8
def ofp_oxm_experimenter_header(message, offset):
	return namedtuple("ofp_oxm_experimenter_header",
		"oxm_header experimenter")(*_unpack("II", message, offset))

# 7.2.4
def ofp_instruction(message, offset):
	return namedtuple("ofp_instruction",
		"type len")(*_unpack("HH", message, offset))

def ofp_instruction_goto_table(message, offset):
	return namedtuple("ofp_instruction_goto_table",
		"type len table_id")(*_unpack("HHB3x", message, offset))

def ofp_instruction_write_metadata(message, offset):
	return namedtuple("ofp_instruction_write_metadata",
		"type len metadata metadata_mask")(*_unpack("HH4xQQ", message, offset))

def ofp_instruction_actions(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(type,len) = _unpack("HH4x", message, cursor)
	
	actions = []
	while cursor.offset < offset + len:
		header = ofp_action_header(message, cursor.offset)
		if header.type == OFPAT_OUTPUT:
			actions.append(ofp_action_output(message, cursor))
		elif header.type == OFPAT_GROUP:
			actions.append(ofp_action_group(message, cursor))
		elif header.type == OFPAT_SET_QUEUE:
			actions.append(ofp_action_set_queue(message, cursor))
		elif header.type == OFPAT_SET_MPLS_TTL:
			actions.append(ofp_action_mpls_ttl(message, cursor))
		elif header.type == OFPAT_SET_NW_TTL:
			actions.append(ofp_action_nw_ttl(message, cursor))
		elif header.type in (OFPAT_PUSH_VLAN,OFPAT_PUSH_MPLS,OFPAT_PUSH_PBB):
			actions.append(ofp_action_push(message, cursor))
		elif header.type == OFPAT_POP_MPLS:
			actions.append(ofp_action_pop_mpls(message, cursor))
		elif header.type == OFPAT_SET_FIELD:
			actions.append(ofp_action_set_field(message, cursor))
		elif header.type == OFPAT_EXPERIMENTER:
			actions.append(ofp_action_experimenter_(message, cursor))
		else:
			actions.append(ofp_action_header(message, cursor))
	
	return namedtuple("ofp_instruction_actions",
		"type,len,actions")(type,len,actions)

def ofp_instruction_meter(message, offset):
	return namedtuple("ofp_instruction_meter",
		"type len meter_id")(*_unpack("HHI", message, offset))

def ofp_instruction_experimenter(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(type,len,experimenter) = _unpack("HHI", message, cursor)
	
	data = message[cursor.offset:offset+len]
	cursor.offset = offset+len
	
	return namedtuple("ofp_instruction_experimenter",
		"type len experimenter data")(type,len,experimenter,data)

# 7.2.5
def ofp_action_header(message, offset):
	return namedtuple("ofp_action_header",
		"type,len")(*_unpack("HH4x", message, offset))

def ofp_action_output(message, offset):
	return namedtuple("ofp_action_output",
		"type,len,port,max_len")(*_unpack("HHIH6x", message, offset))

def ofp_action_group(message, offset):
	return namedtuple("ofp_action_group",
		"type,len,group_id")(*_unpack("HHI", message, offset))

def ofp_action_set_queue(message, offset):
	return namedtuple("ofp_action_set_queue",
		"type,len,queue_id")(*_unpack("HHI", message, offset))

def ofp_action_mpls_ttl(message, offset):
	return namedutple("ofp_action_mpls_ttl",
		"type,len,mpls_ttl")(*_unpack("HHB3x", message, offset))

def ofp_action_nw_ttl(message, offset):
	return namedtuple("ofp_action_nw_ttl",
		"type,len,nw_ttl")(*_unpack("HHB3x", message, offset))

def ofp_ation_push(message, offset):
	return namedtuple("ofp_action_push",
		"type,len,ethertype")(*_unpack("HHH2x", message, offset))

def ofp_action_pop_mpls(message, offset):
	return namedtuple("ofp_action_pop_mpls",
		"type,len,ethertype")(*_unpack("HHH2x", message, offset))

def ofp_action_set_field(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(type,len) = ofp_action_header(message, offset)
	field = message[cursor.offset:offset+len]
	cursor.offset = offset+len
	return namedtuple("ofp_action_set_field",
		"type,len,field")(type,len,field)

def ofp_action_experimenter_header(message, offset):
	return namedtuple("ofp_action_experimenter_header",
		"type,len,experimenter")(*_unpack("HHI", message, offset))

def ofp_action_experimenter_(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_action_experimenter_header(message, cursor)
	data = message[cursor.offset:offset+header.len]
	cursor.offset = offset + header.len
	return namedtuple("ofp_action_experimenter_",
		"type,len,experimenter,data")(*header+(data,))

# 7.3.1
def ofp_switch_features(message, offset=0):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	(datapath_id, n_buffers, n_tables, 
		auxiliary_id, capabilities, reserved) = _unpack("QIBB2xII", message, cursor)
	return namedtuple("ofp_switch_features",
		"header,datapath_id,n_buffers,n_tables,auxiliary_id,capabilities")(
		header,datapath_id,n_buffers,n_tables,auxiliary_id,capabilities)

# 7.3.2
def ofp_switch_config(message, offset):
	cursor = _cursor(offset)
	
	header = ofp_header(message, cursor)
	(flags,miss_send_len) = _unpack("HH", message, cursor)
	return namedtuple("ofp_switch_config",
		"header,flags,miss_send_len")(header,flags,miss_send_len)

# 7.3.3
def ofp_table_mod(message, offset):
	cursor = _cursor(offset)
	
	header = ofp_header(message, cursor)
	(table_id,config) = _unpack("B3xI", message, cursor)
	return namedtuple("ofp_table_mod",
		"header,table_id,config")(header,table_id,config)

# 7.3.4.1
def ofp_flow_mod(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	(cookie,cookie_mask,table_id,command,
		idle_timeout,hard_timeout,priority,
		buffer_id,out_port,out_group,flags) = _unpack("QQBB3H3IH2x", message, cursor)
	match = ofp_match(message, cursor)
	instructions = []
	while cursor.offset < offset + header.length:
		(type, len) = ofp_instruction(message, cursor.offset)
		if type == OFPIT_GOTO_TABLE:
			instructions.append(ofp_instruction_goto_table(message, cursor))
		elif type == OFPIT_WRITE_METADATA:
			instructions.append(ofp_instruction_write_metadata(message, cursor))
		elif type in (OFPIT_WRITE_ACTIONS, OFPIT_APPLY_ACTIONS, OFPIT_CLEAR_ACTIONS):
			instructions.append(ofp_instruction_actions(message, cursor))
		elif type == OFPIT_METER:
			instructions.append(ofp_instruction_meter(message, cursor))
		elif type == OFPIT_EXPERIMENTER:
			instructions.append(ofp_instruction_experimenter(message, cursor))
		else:
			raise ValueError(ofp_instruction(message, cursor.offset))
	
	return namedtuple("ofp_flow_mod",
		'''header,cookie,cookie_mask,table_id,command,
		idle_timeout,hard_timeout,priority,
		buffer_id,out_port,out_group,flags,instructions''')(
		header,cookie,cookie_mask,table_id,command,
		idle_timeout,hard_timeout,priority,
		buffer_id,out_port,out_group,flags,instructions)

# 7.3.4.2
def ofp_group_mod(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	(command,type,group_id) = _unpack("HBxI", message, cursor)
	buckets = []
	while cursor.offset < offset + header.length:
		buckets.append(ofp_bucket(message, cursor))
	
	return namedtuple("ofp_group_mod",
		"header,command,type,group_id,buckets")(header,command,type,group_id,buckets)

def ofp_bucket(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(len,weight,watch_port,watch_group)=_unpack("HHII4x", message, cursor)
	actions = []
	while cursor < offset+len:
		header = ofp_action_header(message, cursor.offset)
		if header.type == OFPAT_OUTPUT:
			actions.append(ofp_action_output(message, cursor))
		elif header.type == OFPAT_GROUP:
			actions.append(ofp_action_group(message, cursor))
		elif header.type == OFPAT_SET_QUEUE:
			actions.append(ofp_action_set_queue(message, cursor))
		elif header.type == OFPAT_SET_MPLS_TTL:
			actions.append(ofp_action_mpls_ttl(message, cursor))
		elif header.type == OFPAT_SET_NW_TTL:
			actions.append(ofp_action_nw_ttl(message, cursor))
		elif header.type in (OFPAT_PUSH_VLAN,OFPAT_PUSH_MPLS,OFPAT_PUSH_PBB):
			actions.append(ofp_action_push(message, cursor))
		elif header.type == OFPAT_POP_MPLS:
			actions.append(ofp_action_pop_mpls(message, cursor))
		elif header.type == OFPAT_SET_FIELD:
			actions.append(ofp_action_set_field(message, cursor))
		elif header.type == OFPAT_EXPERIMENTER:
			actions.append(ofp_action_experimenter_(message, cursor))
		else:
			actions.append(ofp_action_header(message, cursor))
	
	return namedtuple("ofp_bucket",
		"len weight watch_port watch_group actions")(
		len,weight,watch_port,watch_group,actions)

# 7.3.4.3
def ofp_port_mod(message, offset):
	# XXX:
	pass

# 7.3.4.4
def ofp_meter_mod(message, offset):
	# XXX:
	pass

# 7.3.5
def ofp_multipart_request(message, offset=0):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	
	(type, flags) = _unpack("HH4x", message, cursor)
	if type in (OFPMP_DESC, OFPMP_TABLE, OFPMP_GROUP_DESC, 
			OFPMP_GROUP_FEATURES, OFPMP_METER_FEATURES, OFPMP_PORT_DESC):
		body = ""
	elif type == OFPMP_FLOW:
		body = ofp_flow_stats_request(message, cursor)
	elif type == OFPMP_AGGREGATE:
		body = ofp_aggregate_stats_request(message, cursor)
	elif type == OFPMP_PORT_STATS:
		body = ofp_port_stats_request(message, cursor)
	elif type == OFPMP_QUEUE:
		body = ofp_queue_stats_request(message, cursor)
	elif type == OFPMP_GROUP:
		body = ofp_group_stats_request(message, cursor)
	elif type in (OFPMP_METER, OFPMP_METER_CONFIG):
		body = ofp_meter_multipart_requests(message, cursor)
	elif type == OFPMP_TABLE_FEATURES:
		body = []
		while cursor.offset < offset + header.length:
			body.append(ofp_table_features(message, cursor))
	elif type == OFPMP_EXPERIMENTER:
		body = message[cursor.offset:offset+header.length]
		cursor.offset = offset + header.length
	else:
		raise ValueError("multiaprt type=%d flags=%s" % (type, flags))
	
	return namedtuple("ofp_multipart_request",
		"header type flags body")(header,type,flags,body)

def ofp_multipart_reply(message, offset=0):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	
	(type, flags) = _unpack("HH4x", message, cursor)
	body = []
	if type == OFPMP_DESC:
		body = ofp_desc(message, cursor)
	elif type == OFPMP_FLOW:
		body = _list_fetch(message, cursor, offset + header.length, ofp_flow_stats)
	elif type == OFPMP_AGGREGATE:
		body = _list_fetch(message, cursor, offset + header.length, ofp_aggregate_stats_reply)
	elif type == OFPMP_TABLE:
		body = _list_fetch(message, cursor, offset + header.length, ofp_table_stats)
	elif type == OFPMP_PORT_STATS:
		body = _list_fetch(message, cursor, offset + header.length, ofp_port_stats)
	elif type == OFPMP_QUEUE:
		body = _list_fetch(message, cursor, offset + header.length, ofp_queue_stats)
	elif type == OFPMP_GROUP:
		body = _list_fetch(message, cursor, offset + header.length, ofp_group_stats)
	elif type == OFPMP_GROUP_DESC:
		body = _list_fetch(message, cursor, offset + header.length, ofp_group_desc)
	elif type == OFPMP_GROUP_FEATURES:
		body = ofp_group_features(message, cursor)
	elif type == OFPMP_METER:
		body = _list_fetch(message, cursor, offset + header.length, ofp_meter_stats)
	elif type == OFPMP_METER_CONFIG:
		body = _list_fetch(message, cursor, offset + header.length, ofp_meter_config)
	elif type == OFPMP_METER_FEATURES:
		body = ofp_meter_features(message, cursor)
	elif type == OFPMP_TABLE_FEATURES:
		body = _list_fetch(message, cursor, offset + header.length, ofp_table_features)
	elif type == OFPMP_PORT_DESC:
		body = _list_fetch(message, cursor, offset + header.length, ofp_port)
	elif type == OFPMP_EXPERIMENTER:
		body = message[cursor.offset:offset+header.length]
		cursor.offset = offset+headr.length
	else:
		raise ValueError("multiaprt type=%d flags=%s" % (type, flags))
	
	return namedtuple("ofp_multipart_reply",
		"header type flags body")(header,type,flags,body)

def _list_fetch(message, cursor, limit, fetcher):
	ret = []
	while cursor.offset < limit:
		ret.append(fetcher(message, cursor))
	assert cursor.offset == limit
	return ret

# 7.3.5.9
def ofp_group_stats_request(message, offset):
	return namedtuple("ofp_group_stats_request",
		"group_id")(*_unpack("I4x", message, offset))

def ofp_group_stats(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(length, group_id, ref_count, packet_count, byte_count,
		duration_sec, duration_nsec) = _unpack("H2xII4xQQII", message, cursor)
	bucket_stats = _list_fetch(message, cursor, offset+length, ofp_bucket_counter)
	return namedtuple("ofp_group_stats", '''
		length group_id ref_count packet_count byte_count
		duration_sec duration_nsec bucket_stats''')(
		length,group_id,ref_count,packet_count,byte_count,
		duration_sec,duration_nsec,bucket_stats)

def ofp_bucket_counter(message, offset):
	return namedtuple("ofp_bucket_counter",
		"packet_count byte_count")(*_unpack("QQ", message, offset))

# 7.3.5.10
def ofp_group_desc(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(length, type, group_id) = _unpack("HBxI", message, offset)
	buckets = _list_fetch(message, cursor, offset+length, ofp_bucket)
	return namedtuple("ofp_group_desc",
		"length type group_id buckets")(
		length,type,group_id,buckets)

# 7.4.4
def ofp_error_msg(message, offset=0):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	
	(type, code) = _unpack("HH", message, cursor)
	
	data = message[cursor.offset:offset+header.length]
	cursor.offset = offset + header.length
	
	return namedtuple("ofp_error_msg",
		"header,type,code,data")(header,type,code,data)

# 7.5.1
def ofp_hello(message, offset=0):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	
	elements = []
	while cursor.offset < head.offset + header.length:
		elem_header = ofp_hello_elem_header(message, cursor.offset)
		
		if elem_header.type == 1:
			elements.append(ofp_hello_elem_versionbitmap(message, cursor))
		else:
			raise ValueError("message offset=%d %s" % (cursor.offset, elem_header))
	
	assert cursor.offset == offset + header.length
	return namedtuple("ofp_hello", "header elements")(header, elements)

def ofp_hello_elem_header(message, offset):
	return namedtuple("ofp_hello_elem_header",
		"type length")(*_unpack("HH", message, offset))

def ofp_hello_elem_versionbitmap(message, offset):
	cursor = _cursor(offset)
	(type, length) = _unpack("HH", message, cursor)
	assert type == OFPHET_VERSIONBITMAP
	
	bitmaps = _unpack("%dI" % ((length-4)/4), message, cursor)
	cursor.offset += _align(length) - length
	
	return namedtuple("ofp_hello_elem_versionbitmap",
		"type length bitmaps")(type,length,bitmaps)

