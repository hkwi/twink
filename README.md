twink
=====
`twink` is a python openflow library.

`twink` use plain openflow binary message instead of forcing 
you mastering a bundled complicated openflow protocol classes. 
You may use whatever openflow message parsing, building libraries. 
`twink` supports all openflow versions (1.0--1.4).

`twink.gevent` has a gevent based openflow server, so for example, 
you can create an openflow controller server with websocket support.

`twink.gevent_ovs` offers you ovs-ofctl based openflow message 
creation.

For convenience, twink has `ofp4` openflow 1.3 message parser/builder
as `twink.ofp4`, and `twink.ofp5` for openflow 1.4.


LICENSE
-------
This software is licensed under Apache software license 2.0
http://www.apache.org/licenses/LICENSE-2.0
