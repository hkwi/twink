import gevent.server
# fortunatelly, gevent server handle is a duck.

class ChannelStreamServer(gevent.server.StreamServer):
	channel_cls = None
	def handle(self. *args):
		socket, client_address = args
		ch = self.channel_cls(
			socket=socket,
			peer=client_address)
		ch.messages = read_message(socket.recv)
		ch.start()
		ch.loop()
		ch.close()

class ChannelDatagramServer(gevent.server.DatagramServer):
	channel_cls = None
	channels = None
	def handle(self, *args):
		data, client_address = args
		
		if self.channels is None:
			self.channels = {}
		
		ch = self.channels.get(client_address)
		if ch is None:
			ch = self.channel_cls(
				sendto=self.sendto,
				peer=client_address)
			self.channels[client_address] = ch
			ch.start()
		
		f = StringIO.StringIO(data)
		ch.messages = read_message(f.read)
		ch.loop()
		
		if f.tell() < len(data):
			warnings.warn("%d bytes not consumed" % (len(data)-f.tell()))
		ch.messages = None
