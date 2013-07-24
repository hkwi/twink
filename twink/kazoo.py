from __future__ import absolute_import
import logging
import uuid
import json
from twink import Channel
from kazoo.client import KazooClient
from kazoo.security import READ_ACL_UNSAFE, CREATOR_ALL_ACL

def zkopts(opts):
	return dict([(k[3:],v) for k,v in opts.items() if k.startswith("zk_")])

class ZkCollection(dict):
	klass = "base"
	def __init__(self, *args, **kwargs):
		self.zk = zk = KazooClient(**zkopts(kwargs))
		zk.start()
		
		self.zkid = str(uuid.uuid1())
		# XXX: READ_ACL_UNSAFE + CREATOR_ALL_ACL did not work
		zk.create(self.path, value=self.value(), ephemeral=True, makepath=True)
	
	def sync(self):
		self.zk.set(self.path, self.value())
	
	@property
	def path(self):
		return self.basepath() + "/" +self.zkid
	
	@classmethod
	def basepath(self):
		return "/twink/" + self.klass
	
	def value(self):
		return ""
	
	def close(self):
		self.zk.stop()
	
	def __del__(self):
		self.zk.stop()


class ZkChannelCollection(ZkCollection):
	klass = "channel"
	def __init__(self, channel, **kwargs):
		self.channel = channel
		super(ZkChannelCollection, self).__init__(channel, **kwargs)
	
	def value(self):
		return json.dumps(self.channel.plain())
	
	@classmethod
	def all(self, **kwargs):
		zk = KazooClient(**zkopts(kwargs))
		zk.start()
		bulk = [zk.get(self.basepath() + "/" +zkid) for zkid in zk.get_children(self.basepath())]
		zk.stop()
		ret = []
		for b in bulk:
			r = json.loads(b[0])
			for k in "czxid mzxid ctime mtime version cversion aversion pzxid".split():
				r["zk_"+k] = getattr(b[1], k)
			ret.append(r)
		return ret


class ZkChannel(Channel):
	def __init__(self, *args, **kwargs):
		super(ZkChannel, self).__init__(*args, **kwargs)
		self._zk = ZkChannelCollection(self, **kwargs)
	
	def zk_sync(self):
		self._zk.sync()
	
	def close(self):
		self._zk.close()
		super(ZkChannel, self).close()
	
	def plain(self):
		'''
		return a PLAIN object
		'''
		base = {
			"ctime": self.ctime,
			"version": self.version,
			"datapath": self.datapath,
			"auxiliary": self.auxiliary
			}
		try:
			from twink.gevent import StreamChannel, DatagramChannel
			if isinstance(self, StreamChannel):
				base["proto"] = "tcp"
				peer = self.socket.getpeername()
				base["peer_host"] = peer[0]
				base["peer_port"] = peer[1]
			elif isinstance(self, DatagramChannel):
				base["proto"] = "udp"
				peer = self.address
				base["peer_host"] = peer[0]
				base["peer_port"] = peer[1]
		except ImportError:
			pass
		
		return base


if __name__ == "__main__":
	from twink.gevent import *
	import kazoo.handlers.gevent
	
	logging.basicConfig(level=logging.DEBUG)
	
	zk_handler = kazoo.handlers.gevent.SequentialGeventHandler()
	def message_handler(message, channel):
		if easy_message_handler(message, channel):
			return True
		
		(version, oftype, length, xid) = parse_ofp_header(message)
		if oftype==0:
			channel.feature()
			channel.zk_sync()
			print ZkChannelCollection.all(zk_handler=zk_handler)
	
	address = ("0.0.0.0", 6633)
	appconf = {"accept_versions":[1,]}
	tcpserv = StreamServer(address, handle=StreamHandler(
		channel_cls=type("SChannel", (StreamChannel, PortMonitorChannel, SyncChannel, ZkChannel, LoggingChannel), {}),
		channel_opts={"zk_handler": zk_handler},
		accept_versions=[1],
		message_handler=message_handler))
	udpserv = OpenflowDatagramServer(address,
		channel_cls=type("DChannel", (DatagramChannel, PortMonitorChannel, SyncChannel, ZkChannel, LoggingChannel), {}),
		channel_opts={"zk_handler": zk_handler},
		accept_versions=[1],
		message_handler=message_handler)
	serve_forever(tcpserv, udpserv)
