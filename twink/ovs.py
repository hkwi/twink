from __future__ import absolute_import
from . import *
import subprocess

class OvsChannel(ControllerChannel, ParallelChannel):
	def add_flow(self, flow):
		return self.ofctl("add-flow", flow)
	
	def mod_flows(self, flow, strict=False):
		return self.ofctl("mod-flows", flow, strict=strict)
	
	def ofctl(self, action, *args, **options):
		starter, halt, addr = self.temp_server()
		starter()
		try:
			if self.version != 1:
				if "O" in options or "protocols" in options:
					pass
				else:
					options["O"] = ("OpenFlow10","OpenFlow11","OpenFlow12","OpenFlow13")[self.version - 1]
			cmd = ["ovs-ofctl",]
			cmd.extend(self._make_ofctl_options(options))
			cmd.append(action)
			cmd.append("tcp:%s:%d" % addr)
			cmd.extend(args)
			
			p = self.subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			(pstdout, pstderr) = p.communicate()
			if p.returncode != 0:
				logging.getLogger(__name__).error(repr(cmd)+pstderr, exc_info=True)
			return pstdout
		finally:
			halt()
	
	def _make_ofctl_options(self, options):
		# key name, double hyphn, take arg type, join with equal
		fields = ("name", "detail", "argtype", "joinWithEqual")
		option_list = (
			("strict", True, None, False),
			("O", False, str, False), ("protocols", True, str, True),
			("F", False, str, False), ("flow_format", True, str, True),
			("P", False, str, False), ("packet_in_format", True, str, True),
			("timestamp", True, None, False),
			("m", False, None, False), ("more", True, None, False),
			("sort", True, str, True),
			("rsort", True, str, True),
			("pidfile", True, str, True),
			("overwrite_pidfile", True, None, False),
			("detach", True, None, False),
			("monitor", True, None, False),
			("no_chdir", True, None, False),
			("p", False, str, False), ("private_key", True, str, True),
			("c", False, str, False), ("certificate", True, str, True),
			("C", False, str, False), ("ca_cert", True, str, True),
			("v", False, str, False), ("verbose", True, str, True),
			("log_file", True, str, True),
			("h", False, None, False), ("help", True, None, False),
			("V", False, None, False), ("version", True, None, False),
			("idle_timeout", True, int, True),
			("hard_timeout", True, int, True),
			("send_flow_rem", True, None, False),
			("check_overlap", True, None, False)
			)
		known_opts = dict()
		for option_item in option_list:
			known_opts[option_item[0]] = dict(zip(fields, option_item))
		
		ret = []
		for (option,value) in options.items():
			assert option in known_opts, "unknown ovs-ofctl option %s" % option
			opt_info = known_opts[option]
			
			tmp = "-"+option.replace("_", "-")
			if opt_info["detail"]:
				tmp = "-"+tmp
			
			if opt_info["argtype"] is None or value is None:
				ret.append(tmp)
			else:
				sval = str(opt_info["argtype"](value))
				if opt_info["joinWithEqual"] and len(sval):
					ret.append(tmp+"="+sval)
				else:
					ret.append(tmp)
					ret.append(sval)
		return ret


class AutoPacketOut(ControllerChannel):
	'''
	openvswitch-switch sometimes sends dummy OFPT_PACKET_IN instead of sending OFPT_ECHO_REQUEST.
	We must send OFPT_PACKET_OUT, or openvswitch-switch thinks the connection is dead.
	'''
	auto_packet_out = True
	
	def handle_async(self, message, channel):
		parent = super(AutoPacketOut, self)
		if hasattr(parent, "handle_async"):
			parent.handle_async(message, channel)
		
		if not self.auto_packet_out:
			return
		
		(version, oftype, length, xid) = parse_ofp_header(message)
		if oftype == 10:
			(buffer_id,) = struct.unpack_from("!I", message, offset=8)
			if version==1:
				self.send(struct.pack("!BBHIIHH", version, 13, struct.calcsize("!BBHIIHH"), xid,
					buffer_id, 0xffff, 0))
			else:
				self.send(struct.pack("!BBHIIIH6x", version, 13, struct.calcsize("!BBHIIIH6x"), xid,
					buffer_id, 0xfffffffd, 0))


if __name__=="__main__":
	from . import threading
	logging.basicConfig(level=logging.DEBUG)
	
	def handle(message, channel):
		pass
	
	tcpserv = ChannelStreamServer(("0.0.0.0", 6653), StreamRequestHandler)
	tcpserv.channel_cls = type("TestChannel", (
		AutoPacketOut,
		OvsChannel,
		JackinChannel,
		threading.BranchingMixin,
		AutoEchoChannel,
		LoggingChannel,
		threading.HandleInThreadChannel),{
			"accept_versions":[1,4,],
			"handle": staticmethod(handle)
		})
	threading.serve_forever(tcpserv)
