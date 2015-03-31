from . import base
from .base import *

class _sched_proxy(object):
	def __getattr__(self, name):
		if name in "subprocess socket Queue Lock Event spawn serve_forever".split():
			return getattr(base.sched, name)
		raise AttributeError("No such attribute")

sched = _sched_proxy()
serve_forever=sched.serve_forever
