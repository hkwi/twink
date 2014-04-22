from __future__ import absolute_import
import logging
import threading
import signal
import subprocess
import socket
try:
	from queue import Queue
except ImportError:
	from Queue import Queue

__all__="subprocess socket Queue Lock Event spawn serve_forever".split()

Lock = threading.RLock
Event = threading.Event

class Threadlet(object):
	def __init__(self, func, *args, **kwargs):
		result = Queue()
		def wrap():
			try:
				obj = (func(*args, **kwargs), None)
			except Exception as e:
				logging.warn("fail in thread", exc_info=True)
				obj = (None, e)
			result.put(obj)
		
		self.thread = threading.Thread(target=wrap)
		self.result = result
		self.value = None
	
	def start(self):
		self.thread.start()
	
	def join(self, timeout=None):
		self.thread.join(timeout)
	
	def get(self, block=True, timeout=None):
		if self.thread.ident is None:
			self.thread.start()
		
		if self.result:
			values = self.result.get(block=block, timeout=timeout)
			self.result = None
			if values[1] is None:
				self.value = values[0]
			else:
				raise values[1]
		return self.value

def spawn(func, *args, **kwargs):
	th = Threadlet(func, *args, **kwargs)
	th.start()
	return th


def serve_forever(*servers, **opts):
	ev = opts.get("main")
	if not ev:
		ev = Event()
		signal.signal(signal.SIGINT, lambda num,fr: ev.set())
	
	for serv in servers:
		serv.start()
	
	try:
		while not ev.is_set():
			ev.wait(timeout=0.5)
	finally:
		for serv in servers:
			serv.stop()


if __name__=="__main__":
	with Lock():
		r = spawn(lambda x: x, 1)
		assert r.get() == 1
	
	e = Event()
	def remote():
		e.set()
	r = spawn(remote)
	assert e.wait(0.5)
	assert r.get() == None
	r.join()

