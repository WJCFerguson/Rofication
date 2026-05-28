#!/usr/bin/env python3
import sys

from msg import daemon_connection

with daemon_connection() as client:
    client.sendall(bytes("num", "utf-8"))
    val = client.recv(32).decode("utf-8")

l = val.split("\n", 2)
num = int(l[0])
if num:
    print("%d📨" % num)
if int(l[1]) > 0:
    exit(33)
