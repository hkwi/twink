from __future__ import absolute_import
import struct
from collections import namedtuple

def _unpack(fmt, msg, offset=0):
	if fmt[0] != "!":
		fmt = "!"+fmt
	return struct.unpack_from(fmt, msg, offset)

def ofp(message, offset=0):
	header = ofp_header(message)
	if header.type == OFPT_HELLO:
		elements = []
		while offset < header.length:
			(type,) = _unpack("H", message, offset)
			if type == 1:
				elements.append(ofp_hello_elem_versionbitmap(message, offset))
			else:
				raise ValueError("message offset=%d" % offset)
		return namedtuple("ofp_hello",
			"header elements")(
			header,elements)
	elif header.type == OFPT_FEATURES_REPLY:
		return ofp_switch_features(message, offset)

def ofp_header(message, offset=0):
	(version, type, length, xid) = _unpack("BBHI", message, offset)
	assert version == 4
	return namedtuple("ofp_header",
		"version type length xid")(
		version,type,length,xid)

def ofp_hello_elem_header(message, offset=0):
	return namedtuple("ofp_hello_elem_header",
		"type length")(*_unpack("HH", message, offset))

def ofp_switch_features(message, offset=0):
	(header, datapath_id, n_buffers, n_tables, 
		auxiliary_id, capabilities, reserved) = _unpack("8sQIBB2xII", message, offset)
	header = ofp_header(header)
	return namedtuple("ofp_switch_features",
		"header datapath_id n_buffers n_tables auxiliary_id capabilities reserved")(*
		(header,datapath_id,n_buffers,n_tables,auxiliary_id,capabilities,reserved))
