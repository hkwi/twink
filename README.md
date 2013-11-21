twink
=====
`twink` is a python openflow library.

`twink` use plain openflow binary message instead of forcing 
you mastering a bundled complicated openflow protocol classes. 
You may use whatever openflow message parsing, building libraries. 
`twink` supports all openflow versions (1.0--1.4).

`twink.threading` provides a `threading`-based server implementation. 
You can start running with standard libraries.

`twink.gevent` has a gevent based openflow server, so for example, 
you can create an openflow controller server with websocket support.

`twink.ovs` offers you ovs-ofctl based openflow message creation.

`twink.ext` provides utility functionality.

For convenience, twink has `ofp4` openflow 1.3 message parser/builder
as `twink.ofp4`, and `twink.ofp5` for openflow 1.4.

parallel and concurrency
------------------------
With `twink.gevent`, openflow message handling will be parallel.
During handling a specific message, you can suspend it and wait for 
next openflow message incoming using `gvent.event`.
`twink.standard` provides per connection concurrency.
You must use mutex that lives across connections.

server or client
----------------
It does not matter because Openflow protocol is symmetric in syntax.
Not only creating server-controller or client-switch, `twink` helps 
creating server-switch and client-controller, which are not standard style.
You can use this library even in python interactive mode.
`twink` is useful in debugging openflow protocol.
The most import part in creating server, is writing a handler function,
which symbol is `func(openflow_message, channel_instance)` and 
passed to Channel class as `handle` member.

LICENSE
-------
This software is licensed under Apache software license 2.0
http://www.apache.org/licenses/LICENSE-2.0
