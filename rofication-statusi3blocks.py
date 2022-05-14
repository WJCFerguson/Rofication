#!/usr/bin/env python3
import socket
import sys

client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.connect("/tmp/rofi_notification_daemon")
client.sendall(bytes("num", "utf-8"))

val = client.recv(32)
val = val.decode("utf-8")
l = val.split("\n", 2)
num = int(l[0])
if num:
    print("%d📨" % num)
if int(l[1]) > 0:
    exit(33)
