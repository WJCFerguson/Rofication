#!/usr/bin/env python3
import json
import struct
import subprocess

from gi.repository import GLib

from msg import Msg, Urgency, daemon_connection, linesplit, strip_tags


msg = """<span font-size='small'><i>Super+s</i>:    Dismiss notification.  <i>Super+Enter</i>:  Mark notification seen.\n"""
msg += """<i>Super+r</i>:    Reload                             <i>Super+a</i>:          Delete application notification</span>"""
rofi_command = ["rofi", "-dmenu", "-p", "Notifications:", "-markup", "-mesg", msg]


def call_rofi(entries, additional_args=[]):
    additional_args.extend(
        [
            "-kb-custom-1",
            "Super+s",
            "-kb-custom-2",
            "Super+Return",
            "-kb-custom-3",
            "Super+r",
            "-kb-custom-4",
            "Super+a",
            "-markup-rows",
            "-sep",
            "\3",
            "-format",
            "i",
            "-columns",
            "3",
            "-lines",
            "4",
            "-eh",
            "2",
            "-width",
            "-70",
        ]
    )
    proc = subprocess.Popen(
        rofi_command + additional_args, stdin=subprocess.PIPE, stdout=subprocess.PIPE
    )
    for e in entries:
        proc.stdin.write(e.encode("utf-8"))
        proc.stdin.write(struct.pack("B", 3))
    proc.stdin.close()
    answer = proc.stdout.read().decode("utf-8")
    exit_code = proc.wait()
    if answer == "":
        return None, exit_code
    else:
        return int(answer), exit_code


def send_command(cmd):
    with daemon_connection() as client:
        print(f"Send: {cmd}")
        client.send(bytes(cmd, "utf-8"))


did = None
cont = True
first_time = True
while cont:
    cont = False
    ids = []
    entries = []
    index = 0
    urgent = []
    low = []
    args = []
    with daemon_connection() as client:
        client.send(b"list", 4)
        for a in linesplit(client):
            if len(a) > 0:
                msg = Msg.from_dict(json.loads(a))
                ids.append(msg)
                mst = f"<b>{GLib.markup_escape_text(strip_tags(msg.summary))}</b> <small>({GLib.markup_escape_text(strip_tags(msg.application))})</small>"
                if msg.body:
                    mst += f"\n<i>{GLib.markup_escape_text(strip_tags(msg.body.replace(chr(10), ' ')))}</i>"
                if msg.app_icon:
                    mst += f"\0icon\x1f{msg.app_icon}"

                entries.append(mst)
                if Urgency(msg.urgency) is Urgency.critical:
                    urgent.append(str(index))
                if Urgency(msg.urgency) is Urgency.low:
                    low.append(str(index))
                index += 1
    if urgent:
        args.append("-u")
        args.append(",".join(urgent))
    if low:
        args.append("-a")
        args.append(",".join(low))

    if not (first_time or entries):
        break
    first_time = False

    if did is not None:
        args.append("-selected-row")
        args.append(str(did))
    did, code = call_rofi(entries, args)
    print(f"{did},{code}")
    if did is not None and code == 10:
        send_command(f"del:{ids[did].mid}")
        cont = True
    elif did is not None and code == 11:
        send_command(f"saw:{ids[did].mid}")
        cont = True
    elif did is not None and code == 12:
        first_time = True
        cont = True
    elif did is not None and code == 13:
        send_command(f"dela:{ids[did].application}")
        cont = True
