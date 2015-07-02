from __future__ import absolute_import
import gevent.subprocess as subprocess
import gevent.socket as socket
from gevent.queue import Queue
from gevent.event import Event
from gevent.lock import Semaphore as Lock
from gevent import spawn

__all__="subprocess socket Queue Lock Event spawn serve_forever".split()


def serve_forever(*servers, **opts):
	for serv in servers:
		serv.start()
	
	try:
		opts.get("main", Event()).wait()
	finally:
		for job in [spawn(serv.stop) for serv in servers]:
			job.join()


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

