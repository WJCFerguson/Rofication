#!/usr/bin/env python3
import json
import os
import socket
import sys

from gi.repository import GLib

from msg import SOCKET_PATH, Msg, Urgency, linesplit, strip_tags


def send_command(cmd):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(SOCKET_PATH)
    client.send(bytes(cmd, "utf-8"))
    client.close()


def print_entries():
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(SOCKET_PATH)
    client.send(b"list", 4)
    entries = []
    urgent = []
    low = []
    args = []
    if int(os.getenv("ROFI_RETV")) == 0:
        sys.stdout.write("\0delim\x1f\3\n")
    sys.stdout.write("\0markup-rows\x1ftrue\3")
    sys.stdout.write("\0prompt\x1fNotifications\3")
    sys.stdout.write("\0use-hot-keys\x1ftrue\3")
    sys.stdout.write(
        "\0message\x1fPress <i>kb-custom-1</i> dismiss, press <i>kb-custom-2</i> dismiss all from application\3"
    )
    sys.stdout.flush()
    for a in linesplit(client):
        if len(a) > 0:
            msg = Msg.from_dict(json.loads(a))
            mst = "<b>{summ}</b> <small>({app})</small>".format(
                summ=GLib.markup_escape_text(strip_tags(msg.summary)),
                app=GLib.markup_escape_text(strip_tags(msg.application)),
            )
            if len(msg.body) > 0:
                mst += "\n<i>{}</i>".format(
                    GLib.markup_escape_text(strip_tags(msg.body.replace("\n", " ")))
                )
            mst += "\0info\x1f{id}".format(id=msg.mid)
            if msg.app_icon:
                mst += "\x1ficon\x1f{app_icon}".format(app_icon=msg.app_icon)
            if Urgency(msg.urgency) is Urgency.critical:
                mst += "\x1furgent\x1ftrue"

            if Urgency(msg.urgency) is Urgency.low:
                mst += "\x1factive\x1ftrue"
            entries.append(mst)
    entries.reverse()
    for entry in entries:
        os.write(sys.stdout.fileno(), bytes(entry, "utf-8"))
        os.write(sys.stdout.fileno(), b"\3")
        sys.stdout.flush()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        retv = int(os.getenv("ROFI_RETV"))
        if retv == 1:
            mid = int(os.getenv("ROFI_INFO"))
            send_command("saw:{mid}".format(mid=mid))
        elif retv == 10:
            mid = int(os.getenv("ROFI_INFO"))
            send_command("del:{mid}".format(mid=mid))
        elif retv == 11:
            mid = int(os.getenv("ROFI_INFO"))
            send_command("dels:{mid}".format(mid=mid))
        pass
    print_entries()
