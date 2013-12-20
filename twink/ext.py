from __future__ import absolute_import
from . import *
import struct
import weakref
from collections import namedtuple

class PortMonitorChannel(ControllerChannel):
	def __init__(self, *args, **kwargs):
		super(PortMonitorChannel, self).__init__(*args, **kwargs)
		self._ports = []
		self._ports_init = self.event()
		self._port_monitor_multi = dict()
		
		self._attach = weakref.WeakValueDictionary()
		self._detach = weakref.WeakValueDictionary()
	
	def recv(self):
		message = super(PortMonitorChannel, self).recv()
		if message:
			ofp_port = "!H6s16sIIIIII" # ofp_port v1.0
			ofp_port_names = '''port_no hw_addr name
				config state
				curr advertised supported peer'''
			if self.version in (2,3,4):
				ofp_port = "!I4x6s2x16sIIIIIIII"
				ofp_port_names = '''port_no hw_addr name
					config state
					curr advertised supported peer
					curr_speed max_speed'''
			elif self.version == 5:
				ofp_port = "!IH2x6s2x6sII"
				ofp_port_names = '''port_no length hw_addr name
					config state'''
			
			(version, oftype, length, xid) = parse_ofp_header(message)
			if xid in self._port_monitor_multi and oftype==19: # MULTIPART_REPLY
				assert self.version in (4,5)
				(mptype, flags) = struct.unpack_from("!HH4x", message, offset=8)
				if mptype==13: # OFPMP_PORT_DESC
					ports = self._port_monitor_multi[xid]
					offset = 16
					while offset < length:
						port = list(struct.unpack_from(ofp_port, message, offset=offset))
						port[2] = port[2].partition('\0')[0]
						ports.append(namedtuple("ofp_port", ofp_port_names)(*port))
						offset += struct.calcsize(ofp_port)
				
					if not flags&1:
						with self.lock:
							self._ports_replace(ports)
							self._ports_init.set()
							del(self._port_monitor_multi[xid])
			elif oftype==6 and self.version != 4: # FEATURES_REPLY
				fmt = "!BBHIQIB3x"
				assert struct.calcsize(fmt) % 8 == 0
				offset = struct.calcsize(fmt+"II")
				ports = []
				while offset < length:
					port = list(struct.unpack_from(ofp_port, message, offset=offset))
					port[2] = port[2].partition('\0')[0]
					ports.append(namedtuple("ofp_port", ofp_port_names)(*port))
					offset += struct.calcsize(ofp_port)
				with self.lock:
					self._ports_replace(ports)
					self._ports_init.set()
			elif oftype==12: # PORT_STATUS
				p = struct.unpack_from("!B7x"+ofp_port[1:], message, offset=8)
				reason = p[0]
				port = list(p[1:])
				port[2] = port[2].partition('\0')[0]
				self._update_port(reason, namedtuple("ofp_port", ofp_port_names)(*port))
		return message
	
	def _update_port(self, reason, port):
		with self.lock:
			ports = self._ports
			hit = [x for x in ports if x[0]==port[0]] # check with port_no(0)
			if reason==0: # ADD
				if self._ports_init.is_set():
					assert not hit
				ports.append(port)
				
				with self.lock:
					s = self._attach.get(port.port_no, self._attach.get(port.name))
					if s:
						s.set(port)
						self._attach.pop(s)
			elif reason==1: # DELETE
				if self._ports_init.is_set():
					assert hit
				if hit:
					assert len(hit) == 1
					ports.remove(hit.pop())
				
				with self.lock:
					s = self._detach.get(port.port_no, self._detach.get(port.name))
					if s:
						s.set(port)
						self._detach.pop(s)
			elif reason==2: # MODIFY
				if self._ports_init.is_set():
					assert hit
				if hit:
					assert len(hit) == 1
					old = hit.pop()
					idx = ports.index(old)
					ports.remove(old)
					ports.insert(idx, port)
				else:
					ports.append(port)
			else:
				assert False, "unknown reason %d" % reason
			self._ports = ports
	
	@property
	def ports(self):
		if not self._ports_init.is_set():
			if self.version in (4, 5):
				xid = hms_xid()
				with self.lock:
					self._port_monitor_multi[xid] = []
				self.send(struct.pack("!BBHIHH4x", self.version, 
					18, # MULTIPART_REQUEST (v1.3, v1.4)
					16, # struct.calcsize(fmt)==16
					xid, 
					13, # PORT_DESC
					0, # no REQ_MORE
					))
			else:
				self.send(ofp_header_only(5, version=self.version)) # FEATURES_REQUEST
			self._ports_init.wait()
		return tuple(self._ports)
	
	def _ports_replace(self, new_ports):
		old_ports = self.ports
		
		old_nums = set([p.port_no for port in self.ports])
		old_names = set([p.name for port in self.ports])
		new_nums = set([p.port_no for port in value])
		new_names = set([p.name for port in value])
		
		for port in old_ports:
			if port.port_no in old_nums-new_nums:
				with self.lock:
					s = self._detach[port.port_no]
					if s:
						s.set(port)
						self._detach.pop(s)
			if port.name in old_names-new_names:
				with self.lock:
					s = self._detach[port.name]
					if s:
						s.set(port)
						self._detach.pop(s)
		
		for port in new_ports:
			if port.port_no in new_nums-old_nums:
				with self.lock:
					s = self._attach[port.port_no]
					if s:
						s.set(port)
						self._attach.pop(s)
			if port.name in new_names-old_names:
				with self.lock:
					s = self._attach[port.name]
					if s:
						s.set(port)
						self._attach.pop(s)
		
		self._ports = new_ports
	
	def close(self):
		self._ports_init.set() # unlock the event
		super(PortMonitorChannel, self).close()
	
	def wait_attach(self, num_or_name, timeout=10):
		for port in self.ports:
			if port.port_no == num_or_name or port.name == num_or_name:
				return port
		
		with self.lock:
			if num_or_name not in self._attach:
				result = self._attach[num_or_name] = self.event()
			else:
				result = self._attach[num_or_name]
		
		if result.wait(timeout=timeout):
			for port in self.ports:
				if port.port_no == num_or_name or port.name == num_or_name:
					return port
	
	def wait_detach(self, num_or_name, timeout=10):
		hit = False
		for port in self.ports:
			if port.port_no == num_or_name or port.name == num_or_name:
				hit = True
		if not hit:
			return num_or_name # already detached
		
		with self.lock:
			if num_or_name not in self._detach:
				result = self._detach[num_or_name] = self.event()
			else:
				result = self._detach[num_or_name]
		
		if result.wait(timeout=timeout):
			return num_or_name
