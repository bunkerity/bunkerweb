This directory contains some sample programs using
LuaSocket. This code is not supported.

    listener.lua            -- socket to stdout
    talker.lua              -- stdin to socket

listener.lua and talker.lua are about  the simplest
applications you can write  using  LuaSocket.  Run   

	'lua listener.lua'  and  'lua talker.lua'

on different terminals. Whatever you type on talk.lua will
be printed by listen.lua.

    lpr.lua                 -- lpr client

This is a cool program written by David Burgess to print
files using the Line Printer Daemon protocol, widely used in
Unix machines.  It uses the lp.lua implementation, in the
etc directory.  Just run 'lua lpr.lua <filename>
queue=<printername>' and the file will print!

    cddb.lua                -- CDDB client

This is the first try on a simple CDDB client. Not really
useful, but one day it might become a module. 

    daytimeclnt.lua         -- day time client

Just run the program to retrieve the hour and date in
readable form from any server running an UDP daytime daemon.

    echoclnt.lua            -- UDP echo client
    echosrvr.lua            -- UDP echo server

These are a UDP echo client/server pair. They work with
other client and servers as well.

    tinyirc.lua             -- irc like broadcast server

This is a simple server that  waits simultaneously on two
server sockets for telnet connections.  Everything it
receives from  the telnet clients is  broadcasted to  every
other  connected client.  It tests  the select function and
shows  how to create a simple server  whith LuaSocket. Just
run tinyirc.lua and  then open as many telnet connections
as you want to ports 8080 and 8081.

Good luck,
Diego.
