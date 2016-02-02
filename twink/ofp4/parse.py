
from __future__ import absolute_import
import struct
from collections import namedtuple
from . import *

_len = len
_type = type

def _align(length):
	return (length+7)//8*8

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

def from_bitmap(uint32_t_list):
	ret = []
	for o,i in zip(range(_len(uint32_t_list)),uint32_t_list):
		for s in range(32):
			if i & (1<<s):
				ret.append(32*o + s)
	return ret

def parse(message, offset=0):
	if message is None:
		return None
	
	cursor = _cursor(offset)
	header = ofp_header(message, cursor.offset)
	assert header.version == 4
	if header.type == OFPT_HELLO:
		return ofp_hello(message, cursor)
	elif header.type == OFPT_ERROR:
		return ofp_error_msg(message, cursor)
	elif header.type == OFPT_FEATURES_REPLY:
		return ofp_switch_features(message, cursor)
	elif header.type in (OFPT_SET_CONFIG, OFPT_GET_CONFIG_REPLY):
		return ofp_switch_config(message, cursor)
	elif header.type == OFPT_PACKET_IN:
		return ofp_packet_in(message, cursor)
	elif header.type == OFPT_FLOW_REMOVED:
		return ofp_flow_removed(message, cursor)
	elif header.type == OFPT_PORT_STATUS:
		return ofp_port_status(message, cursor)
	elif header.type == OFPT_PACKET_OUT:
		return ofp_packet_out(message, cursor)
	elif header.type == OFPT_FLOW_MOD:
		return ofp_flow_mod(message, cursor)
	elif header.type == OFPT_GROUP_MOD:
		return ofp_group_mod(message, cursor)
	elif header.type == OFPT_PORT_MOD:
		return ofp_port_mod(message, cursor)
	elif header.type == OFPT_TABLE_MOD:
		return ofp_table_mod(message, cursor)
	elif header.type == OFPT_MULTIPART_REQUEST:
		return ofp_multipart_request(message, cursor)
	elif header.type == OFPT_MULTIPART_REPLY:
		return ofp_multipart_reply(message, cursor)
	elif header.type == OFPT_EXPERIMENTER:
		return ofp_experimenter_(message, cursor)
	elif header.type == OFPT_QUEUE_GET_CONFIG_REQUEST:
		return ofp_queue_get_config_request(message, cursor)
	elif header.type == OFPT_QUEUE_GET_CONFIG_REPLY:
		return ofp_queue_get_config_reply(message, cursor)
	elif header.type in (OFPT_SET_ASYNC, OFPT_GET_ASYNC_REPLY):
		return ofp_async_config(message, cursor)
	elif header.type == OFPT_METER_MOD:
		return ofp_meter_mod(message, cursor)
	else:
		# OFPT_ECHO_REQUEST, OFPT_ECHO_REPLY
		# OFPT_FEATURES_REQUEST
		# OFPT_BARRIER_REQUEST, OFPT_BARRIER_REPLY
		# OFPT_GET_ASYNC_REQUEST
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

# 7.2.1 and 7.3.5.7
def ofp_port(message, offset):
	cursor = _cursor(offset)
	p = list(_unpack("I4x6s2x16sII6I", message, cursor))
	p[2] = p[2].partition(b"\0")[0].decode("UTF-8")
	return namedtuple("ofp_port", '''
		port_no hw_addr name
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
			properties.append(ofp_queue_prop_min_rate(message, cursor))
		elif prop_header.property == OFPQT_MAX:
			properties.append(ofp_queue_prop_max_rate(message, cursor))
		elif prop_header.property == OFPQT_EXPERIMENTER:
			properties.append(ofp_queue_prop_experimenter(message, cursor))
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
	oxm_fields = message[cursor.offset:offset+length]
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

def ofp_instruction_(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(type, len) = ofp_instruction(message, cursor.offset)
	if type == OFPIT_GOTO_TABLE:
		return ofp_instruction_goto_table(message, cursor)
	elif type == OFPIT_WRITE_METADATA:
		return ofp_instruction_write_metadata(message, cursor)
	elif type in (OFPIT_WRITE_ACTIONS, OFPIT_APPLY_ACTIONS, OFPIT_CLEAR_ACTIONS):
		return ofp_instruction_actions(message, cursor)
	elif type == OFPIT_METER:
		return ofp_instruction_meter(message, cursor)
	elif type == OFPIT_EXPERIMENTER:
		return ofp_instruction_experimenter(message, cursor)
	else:
		raise ValueError(ofp_instruction(message, cursor.offset))

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
		actions.append(ofp_action_(message,cursor))
	
	assert cursor.offset == offset+len
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

def ofp_action_(message, offset):
	cursor = _cursor(offset)
	header = ofp_action_header(message, cursor.offset)
	if header.type == OFPAT_OUTPUT:
		return ofp_action_output(message, cursor)
	elif header.type == OFPAT_GROUP:
		return ofp_action_group(message, cursor)
	elif header.type == OFPAT_SET_QUEUE:
		return ofp_action_set_queue(message, cursor)
	elif header.type == OFPAT_SET_MPLS_TTL:
		return ofp_action_mpls_ttl(message, cursor)
	elif header.type == OFPAT_SET_NW_TTL:
		return ofp_action_nw_ttl(message, cursor)
	elif header.type in (OFPAT_PUSH_VLAN,OFPAT_PUSH_MPLS,OFPAT_PUSH_PBB):
		return ofp_action_push(message, cursor)
	elif header.type == OFPAT_POP_MPLS:
		return ofp_action_pop_mpls(message, cursor)
	elif header.type == OFPAT_SET_FIELD:
		return ofp_action_set_field(message, cursor)
	elif header.type == OFPAT_EXPERIMENTER:
		return ofp_action_experimenter_(message, cursor)
	else:
		return ofp_action_header(message, cursor)

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

def ofp_action_push(message, offset):
	return namedtuple("ofp_action_push",
		"type,len,ethertype")(*_unpack("HHH2x", message, offset))

def ofp_action_pop_mpls(message, offset):
	return namedtuple("ofp_action_pop_mpls",
		"type,len,ethertype")(*_unpack("HHH2x", message, offset))

def ofp_action_set_field(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(type,len) = _unpack("HH", message, cursor)
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
	instructions = _list_fetch(message, cursor, offset+header.length, ofp_instruction_)
	
	return namedtuple("ofp_flow_mod",
		'''header,cookie,cookie_mask,table_id,command,
		idle_timeout,hard_timeout,priority,
		buffer_id,out_port,out_group,flags,match,instructions''')(
		header,cookie,cookie_mask,table_id,command,
		idle_timeout,hard_timeout,priority,
		buffer_id,out_port,out_group,flags,match,instructions)

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
	while cursor.offset < offset+len:
		actions.append(ofp_action_(message, cursor))
	
	return namedtuple("ofp_bucket",
		"len weight watch_port watch_group actions")(
		len,weight,watch_port,watch_group,actions)

# 7.3.4.3
def ofp_port_mod(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	
	(port_no, hw_addr, config, advertise) = _unpack("I4x6s2xIII4x", message, offset)
	assert offset + header.length == cursor.offset
	return namedtuple("ofp_port_mod",
		"header,port_no,hw_addr,config,advertise")(
		header,port_no,hw_addr,config,advertise)

# 7.3.4.4
def ofp_meter_mod(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	
	(command,flags,meter_id) = _unpack("HHI", message, cursor)
	
	bands = []
	while cursor.offset < offset + header.length:
		bands.append(ofp_meter_band_(message, cursor))
	
	return namedtuple("ofp_meter_mod",
		"header,command,flags,meter_id,bands")(
		header,command,flags,meter_id,bands)

def ofp_meter_band_header(message, offset):
	return namedtuple("ofp_meter_band_header",
		"type,len,rate,burst_size")(*_unpack("HHII", message, offset))

def ofp_meter_band_(message, offset):
	cursor = _cursor(offset)
	
	header = ofp_meter_band_header(message, cursor.offset)
	if header.type == OFPMBT_DROP:
		return ofp_meter_band_drop(message, cursor)
	elif header.type == OFPMBT_DSCP_REMARK:
		return ofp_meter_band_dscp_remark(message, cursor)
	elif header.type == OFPMBT_EXPERIMENTER:
		return ofp_meter_band_experimenter(message, cursor)
	else:
		raise ValueError(header)

def ofp_meter_band_drop(message, offset):
	return namedtuple("ofp_meter_band_drop",
		"type,len,rate,burst_size")(*_unpack("HHII4x", message, offset))

def ofp_meter_band_dscp_remark(message, offset):
	return namedtuple("ofp_meter_band_dscp_remark",
		"type,len,rate,burst_size,prec_level")(
		*_unpack("HHIIB3x", message, offset))

def ofp_meter_band_experimenter(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(type,len,rate,burst_size,experimenter) = _unpack("HH3I", message, offset)
	data = message[cursor.offset:offset+len]
	return namedtuple("ofp_meter_band_experimenter",
		"type,len,rate,burst_size,experimenter,data")(
		type,len,rate,burst_size,experimenter,data)

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
		body = ofp_experimenter_multipart_(message, cursor, offset+header.length)
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

# 7.3.5.1
def ofp_desc(message, offset):
	return namedtuple("ofp_desc",
		"mfr_desc,hw_desc,sw_desc,serial_num,dp_desc")(*_unpack("256s256s256s32s256s", message, offset))

# 7.3.5.2
def ofp_flow_stats_request(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(table_id,out_port,out_group,cookie,cookie_mask) = _unpack("B3xII4xQQ", message, cursor)
	
	match = ofp_match(message, cursor)
	
	return namedtuple("ofp_flow_stats_request",
		"table_id,out_port,out_group,cookie,cookie_mask,match")(
		table_id,out_port,out_group,cookie,cookie_mask,match)

def ofp_flow_stats(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(length,table_id,duration_sec,duration_nsec,priority,
	idle_timeout,hard_timeout,flags,cookie,
	packet_count,byte_count) = _unpack("HBxII4H4x3Q", message, cursor)
	
	match = ofp_match(message, cursor)
	
	instructions = _list_fetch(message, cursor, offset+length, ofp_instruction_)
	
	return namedtuple("ofp_flow_stats", '''
		length table_id duration_sec duration_nsec
		priority idle_timeout hard_timeout flags cookie
		packet_count byte_count match instructions''')(
		length,table_id,duration_sec,duration_nsec,priority,
		idle_timeout,hard_timeout,flags,cookie,
		packet_count,byte_count,match,instructions)

# 7.3.5.3
def ofp_aggregate_stats_request(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(table_id,out_port,out_group,cookie,cookie_mask) = _unpack("B3xII4xQQ", message, cursor)
	match = ofp_match(message, cursor)
	
	return namedtuple("ofp_aggregate_stats_request",
		"table_id,out_port,out_group,cookie,cookie_mask,match")(
		table_id,out_port,out_group,cookie,cookie_mask,match)

def ofp_aggregate_stats_reply(message, offset):
	return namedtuple("ofp_aggregate_stats_reply",
		"packet_count,byte_count,flow_count")(
		*_unpack("QQI4x", message, offset))

# 7.3.5.4
def ofp_table_stats(message, offset):
	return namedtuple("ofp_table_stats", "table_id,active_count,lookup_count,matched_count")(
		*_unpack("B3xIQQ", message, offset))

# 7.3.5.5.1
def ofp_table_features(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(length,table_id,name,metadata_match,metadata_write,config,max_entries) = _unpack("HB5x32sQQII", message, cursor)
	properties = _list_fetch(message, cursor, offset+length, ofp_table_feature_prop_)
	
	name = name.partition('\0')[0]
	
	return namedtuple("ofp_table_feature_prop_header",
		"length,table_id,name,metadata_match,metadata_write,config,max_entries,properties")(
		length,table_id,name,metadata_match,metadata_write,config,max_entries,properties)

# 7.3.5.5.2
def ofp_table_feature_prop_header(message, offset):
	return namedtuple("ofp_table_feature_prop_header",
		"type,length")(*_unpack("HH", message, offset))

def ofp_table_feature_prop_instructions(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(type,length) = _unpack("HH", message, cursor)
	instruction_ids = []
	while cursor.offset < offset+length:
		header = ofp_instruction(cursor.offset)
		if header.type == OFPIT_EXPERIMENTER:
			instruction_ids.append(ofp_instruction_experimenter(message, cursor))
		else:
			assert header.len == 4
			instruction_ids.append(header)
	cursor.offset += _align(length)-length
	
	return namedtuple("ofp_table_feature_prop_instructions",
		"type,length,instruction_ids")(
		type,length,instruction_ids)

def ofp_table_feature_prop_next_tables(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(type,length) = _unpack("HH", message, cursor)
	next_table_ids = _unpack("%dB" % (length-4), message, offset)
	cursor.offset += _align(length)-length
	
	return namedtuple("ofp_table_feature_prop_next_tables",
		"type,length,next_table_ids")(type,length,next_table_ids)

def ofp_table_feature_prop_actions(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(type,length) = _unpack("HH", message, cursor)
	action_ids = []
	while cursor.offset < offset+length:
		header = ofp_action_header(message, cursor.offset)
		if header.type == OFPAT_EXPERIMENTER:
			action_ids.append(ofp_action_experimenter(message, cursor))
		else:
			assert header.len == 4
			action_ids.append(header)
	cursor.offset += _align(length)-length
	
	return namedtuple("ofp_table_feature_prop_actions",
		"type,length,action_ids")(type,length,action_ids)

def ofp_table_feature_prop_oxm(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(type,length) = _unpack("HH", message, cursor)
	oxm_ids = _unpack("%dI" % ((length-4)//4), message, cursor)
	cursor.offset += _align(length)-length
	
	return namedtuple("ofp_table_feature_prop_oxm",
		"type,length,oxm_ids")(type,length,oxm_ids)

def ofp_table_feature_prop_experimenter(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(type,length,experimenter,exp_type) = _unpack("HHII", message, cursor)
	data = message[cursor.offset:offset+length]
	cursor.offset += _align(length)-length
	
	return namedtuple("ofp_table_feature_prop_experimenter",
		"type,length,experimenter,exp_type,data")(
		type,length,experimenter,exp_type,data)

# 7.3.5.6
def ofp_port_stats_request(message, offset):
	return namedtuple("ofp_port_stats_request",
		"port_no")(*_unpack("I4x", message, offset))

def ofp_port_stats(message, offset):
	return namedtuple("ofp_port_stats", '''
		port_no
		rx_packets tx_packets
		rx_bytes tx_bytes
		rx_dropped tx_dropped
		rx_errors tx_errors
		rx_frame_err
		rx_over_err
		rx_crc_err
		collisions
		duration_sec duration_nsec''')(*_unpack("I3x12Q2I", message, offset))

# 7.3.5.8
def ofp_queue_stats_request(message, offset):
	return namedtuple("ofp_queue_stats_request",
		"port_no queue_id")(*_unpack("II", message, offset))

def ofp_queue_stats(message, offset):
	return namedtuple("ofp_queue_stats", '''
		port_no queue_id
		tx_bytes tx_packets tx_errors
		duration_sec duration_nsec''')(*_unpack("2I3Q2I", message, offset))

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
	
	(length, type, group_id) = _unpack("HBxI", message, cursor)
	buckets = _list_fetch(message, cursor, offset+length, ofp_bucket)
	return namedtuple("ofp_group_desc",
		"length type group_id buckets")(
		length,type,group_id,buckets)

# 7.3.5.11
def ofp_group_features(message, offset):
	cursor = _cursor(offset)
	(type,capabilities) = _unpack("II", message, cursor)
	max_groups = _unpack("4I", message, cursor)
	actions = _unpack("4I", message, cursor)
	return namedtuple("ofp_group_features",
		"type,capabilities,max_groups,actions")(
		type,capabilities,max_groups,actions)

# 7.3.5.12
def ofp_meter_multipart_request(message, offset):
	# and 7.3.5.13
	return namedtuple("ofp_meter_multipart_request",
		"meter_id")(*_unpack("I4x", message, offset))

def ofp_meter_stats(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(meter_id,len,flow_count,packet_in_count,byte_in_count,
		duration_sec,duration_nsec) = _unpack("IH6xIQQII", message, cursor)
	
	band_stats = _list_fetch(message, cursor, offset+len, ofp_meter_band_stats)
	
	return namedtuple("ofp_meter_stats", '''
		meter_id len flow_count packet_in_count byte_in_count 
		duration_sec duration_nsec band_stats''')(
		meter_id,len,flow_count,packet_in_count,byte_in_count,
		duration_sec,duration_nsec,band_stats)

def ofp_meter_band_stats(message, offset):
	return namedtuple("ofp_meter_band_stats",
		"packet_band_count,byte_band_count")(*_unpack("QQ", message, offset))

# 7.3.5.13
def ofp_meter_config(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(length,flags,meter_id) = _unpack("HHI", message, cursor)
	bands = _list_fetch(message, cursor, offset+length, ofp_meter_band_)
	
	return namedtuple("ofp_meter_config",
		"length,flags,meter_id,bands")(
		length,flags,meter_id,bands)

# 7.3.5.14
def ofp_meter_features(message, offset):
	return namedtuple("ofp_meter_features", '''
		max_meter band_types capabilities
		max_bands max_color''')(*_unpack("3IBB2x", message, offset))

# 7.3.5.15
def ofp_experimenter_multipart_header(message, offset):
	return namedtuple("ofp_experimenter_multipart_header",
		"experimenter,exp_type")(*_unpack("II", message, offset))

def ofp_experimenter_multipart_(message, offset, limit):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(experimenter,exp_type) = ofp_experimenter_multipart_header(message, cursor)
	data = message[cursor.offset:limit]
	cursor.offset = limit
	
	return namedtuple("ofp_experimenter_multipart_",
		"experimenter,exp_type,data")(experimenter,exp_type,data)

# 7.3.6
def ofp_queue_get_config_request(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	(port,) = _unpack("I4x", message, cursor)
	return namedtuple("ofp_queue_get_config_request",
		"header,port")(header,port)

def ofp_queue_get_config_reply(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	(port,) = _unpack("I4x", message, cursor)
	queues = _list_fetch(message, cursor, offset+header.length, ofp_packet_queue)
	
	return namedtuple("ofp_queue_get_config_reply",
		"header,port,queues")(header,port,queues)

# 7.3.7
def ofp_packet_out(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	
	(buffer_id, in_port, actions_len) = _unpack("IIH6x", message, cursor)
	
	actions_end = cursor.offset + actions_len
	actions = []
	while cursor.offset < actions_end:
		actions.append(ofp_action_(message, cursor))
	
	data = message[cursor.offset:offset+header.length]
	
	return namedtuple("ofp_packet_out",
		"header,buffer_id,in_port,actions_len,actions,data")(
		header,buffer_id,in_port,actions_len,actions,data)

# 7.3.9
def ofp_role_request(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	(role,generation_id) = _unpack("I4xQ", message, cursor)
	
	return namedtuple("ofp_role_request",
		"header,role,generation_id")(header,role,generation_id)

# 7.3.10
def ofp_async_config(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	p = _unpack("6I", message, cursor)
	
	return namedtuple("ofp_async_config",
		"header,packet_in_mask,port_status_mask,flow_removed_mask")(
		header,p[0:2],p[2:4],p[4:6])

# 7.4.1
def ofp_packet_in(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	
	(buffer_id, total_len, reason, table_id, cookie) = _unpack("IHBBQ", message, cursor)
	
	match = ofp_match(message, cursor)
	_unpack("2x", message, cursor);
	data = message[cursor.offset:offset+header.length]
	
	return namedtuple("ofp_packet_in",
		"header,buffer_id,total_len,reason,table_id,cookie,match,data")(
		header,buffer_id,total_len,reason,table_id,cookie,match,data)

# 7.4.2
def ofp_flow_removed(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	
	(cookie,priority,reason,table_id,
	duration_sec,duration_nsec,
	idle_timeout,hard_timeout,packet_count,byte_count) = _unpack("QHBBIIHHQQ", message, cursor)
	
	match = ofp_match(message, cursor)
	
	return namedtuple("ofp_flow_removed",
		'''header cookie priority reason table_id 
		duration_sec duration_nsec 
		idle_timeout hard_timeout packet_count byte_count
		match''')(
		header,cookie,priority,reason,table_id,
		duration_sec,duration_nsec,
		idle_timeout,hard_timeout,packet_count,byte_count,
		match)

# 7.4.3
def ofp_port_status(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	
	(reason,) = _unpack("B7x", message, cursor)
	
	desc = ofp_port(message, cursor)
	return namedtuple("ofp_port_status",
		"header,reason,desc")(
		header,reason,desc)

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
	while cursor.offset < offset + header.length:
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
	
	bitmaps = _unpack("%dI" % ((length-4)//4), message, cursor)
	cursor.offset += _align(length) - length
	
	return namedtuple("ofp_hello_elem_versionbitmap",
		"type length bitmaps")(type,length,bitmaps)

# 7.5.4
def ofp_experimenter_header(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	header = ofp_header(message, cursor)
	(experimenter,exp_type) = _unpack("II", message, cursor)
	return namedtuple("ofp_experimenter_header",
		"header,experimenter,exp_type")(header,experimenter,exp_type)

def ofp_experimenter_(message, offset):
	cursor = _cursor(offset)
	offset = cursor.offset
	
	(header,experimenter,exp_type) = ofp_experimenter_header(message, cursor)
	
	data = message[cursor.offset:offset+length]
	cursor.offset = offset+length
	
	return namedtuple("ofp_experimenter_",
		"header,experimenter,exp_type,data")(header,experimenter,exp_type,data)
