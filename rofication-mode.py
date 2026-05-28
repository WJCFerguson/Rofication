#!/usr/bin/env python3
import json
import os
import sys

from gi.repository import GLib

from msg import Msg, Urgency, daemon_connection, linesplit, strip_tags


def send_command(cmd):
    with daemon_connection() as client:
        client.send(bytes(cmd, "utf-8"))


def print_entries():
    entries = []
    if int(os.getenv("ROFI_RETV")) == 0:
        sys.stdout.write("\0delim\x1f\3\n")
    sys.stdout.write("\0markup-rows\x1ftrue\3")
    sys.stdout.write("\0prompt\x1fNotifications\3")
    sys.stdout.write("\0use-hot-keys\x1ftrue\3")
    sys.stdout.write(
        "\0message\x1fPress <i>kb-custom-1</i> dismiss, press <i>kb-custom-2</i> dismiss all from application\3"
    )
    sys.stdout.flush()
    with daemon_connection() as client:
        client.send(b"list", 4)
        for a in linesplit(client):
            if len(a) > 0:
                msg = Msg.from_dict(json.loads(a))
                mst = f"<b>{GLib.markup_escape_text(strip_tags(msg.summary))}</b> <small>({GLib.markup_escape_text(strip_tags(msg.application))})</small>"
                if msg.body:
                    mst += f"\n<i>{GLib.markup_escape_text(strip_tags(msg.body.replace(chr(10), ' ')))}</i>"
                mst += f"\0info\x1f{msg.mid}"
                if msg.app_icon:
                    mst += f"\x1ficon\x1f{msg.app_icon}"
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
        mid = int(os.getenv("ROFI_INFO"))
        if retv == 1:
            send_command(f"saw:{mid}")
        elif retv == 10:
            send_command(f"del:{mid}")
        elif retv == 11:
            send_command(f"dels:{mid}")
    print_entries()
