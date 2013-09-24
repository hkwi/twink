from __future__ import absolute_import
from twink.gevent import *
from gevent import socket,subprocess
import logging

subprocess.check_call(["ovs-ofctl","--version"], stdout=open("/dev/null","w"), stderr=open("/dev/null","w"))


class ProxySwitchChannel(StreamChannel):
	# To debug this channel, add LogginChannel mixin
	message_handler = None
	def send(self, message, message_handler): # send message to controller
		super(ProxySwitchChannel, self).send(message, message_handler) # for observers
		if self.message_handler is None:
			self.message_handler = message_handler
		assert self.message_handler == message_handler, "We can handle only one handler at a time."
		
		self.direct_send(message)
	
	def on_message(self, message): # recv message from controller
		super(ProxySwitchChannel, self).on_message(message) # for observers
		self.message_handler(message, self)


class ProxyMessageHandler(object):
	def __init__(self, upstream):
		self.parent = upstream
		self.channel = None
	
	def __call__(self, message, channel):
		if self.channel is None:
			self.channel = channel
		assert self.channel == channel, "We can handle only one controller connection at a time."
		
		(version, oftype, length, xid) = parse_ofp_header(message)
		if oftype==2: # ECHO
			channel.send(struct.pack("!BBHI", channel.version, 3, 8+length, xid)+message, None)
			return True
		elif oftype==0: # HELLO
			accept_versions = channel.accept_versions
			if not accept_versions:
				accept_versions = set([1,])
			channel.version = max(parse_hello(message) & accept_versions)
		else:
			self.parent.send(message, self.on_parent_message)
	
	def on_parent_message(self, message, channel):
		assert channel is self.parent
		
		if self.channel.closed:
			raise CallbackDeadError("channel closed")
		self.channel.send(message, self)


class OvsChannel(Channel):
	def add_flow(self, flow):
		return self.ofctl("add-flow", flow)
	
	def mod_flows(self, flow, strict=False):
		return self.ofctl("mod-flows", flow, strict=strict)
	
	def ofctl(self, action, *args, **options):
		server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		server_socket.bind(("127.0.0.1", 0))
		server = StreamServer(server_socket, handle=StreamHandler(
			channel_cls=type("OvsProxy", (ProxySwitchChannel,), {
				"accept_versions": set([self.version]),
				}),
			message_handler=ProxyMessageHandler(upstream=self)))
		server_socket.listen(1)
		server.start()
		try:
			if self.version != 1:
				if "O" in options or "protocols" in options:
					pass
				else:
					options["O"] = ("OpenFlow10","OpenFlow11","OpenFlow12","OpenFlow13")[self.version - 1]
			cmd = ["ovs-ofctl",]
			cmd.extend(self._make_ofctl_options(options))
			cmd.append(action)
			cmd.append("tcp:%s:%d" % server_socket.getsockname())
			cmd.extend(args)
			
			p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			(pstdout, pstderr) = p.communicate()
			if p.returncode != 0:
				logging.error(pstderr, exc_info=True)
			return pstdout
		finally:
			server.stop()
	
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

if __name__=="__main__":
	def message_handler(message, channel):
		ret = easy_message_handler(message, channel)
		(version, oftype, length, xid) = parse_ofp_header(message)
		if oftype==0:
			print channel.ofctl("dump-flows")
		return ret
	
	logging.basicConfig(level=logging.DEBUG)
	address = ("0.0.0.0", 6653)
	tcpserv = StreamServer(address, handle=StreamHandler(
		channel_cls = type("SChannel",
			(StreamChannel, ControllerChannel, OvsChannel, LoggingChannel), 
			{"accept_versions":[1,4]}),
		message_handler = message_handler))
	udpserv = OpenflowDatagramServer(address, 
		channel_cls = type("DChannel",
			(StreamChannel, ControllerChannel, OvsChannel, LoggingChannel), 
			{"accept_versions":[1,4]}),
		message_handler = message_handler)
	serve_forever(tcpserv, udpserv)
