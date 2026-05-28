#!/usr/bin/env python3
import json
import os
import signal
import socket
import threading
import time

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

from msg import SOCKET_PATH, Msg, Urgency

event = threading.Event()

# Applications where only the last notification is relevant (e.g. media players)
single_notification_app = ["VLC media player"]

# Applications that are allowed to expire
allowed_expire_app = []


class Rofication(threading.Thread):

    CACHE_DIR = os.path.join(
        os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "rofication"
    )
    QUEUE_FILE = os.path.join(CACHE_DIR, "not.json")

    def __init__(self):
        self.socket_path = SOCKET_PATH
        os.makedirs(os.path.dirname(self.socket_path), exist_ok=True)
        self.notification_queue_lock = threading.Lock()
        self.notification_queue = []
        self.last_id = 0
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        super().__init__()

    def load(self):
        print("Loading rofication")
        try:
            with open(self.QUEUE_FILE, "r") as f:
                self.notification_queue = [Msg.from_dict(d) for d in json.load(f)]
        except Exception:
            pass

        for noti in self.notification_queue:
            noti.notid = -1
            if self.last_id < noti.mid:
                self.last_id = int(noti.mid)
        print(f"Found last id: {self.last_id}")

    def save(self):
        print("Saving rofication")
        try:
            with open(self.QUEUE_FILE, "w") as f:
                json.dump([n.to_dict() for n in self.notification_queue], f)
        except Exception:
            print("Failed to store queue.")

    def update_queue(self):
        """Remove notifications that are expired and allowed to expire."""
        with self.notification_queue_lock:
            now = time.time()
            expired = [
                n
                for n in self.notification_queue
                if n.application in allowed_expire_app
                and n.deadline > 0
                and n.deadline < now
            ]
            for noti in expired:
                print(f"{noti.mid} expired.")
                self.notification_queue.remove(noti)

    def remove_notification(self, id):
        print(f"Removing: {id}")
        with self.notification_queue_lock:
            self.notification_queue = [
                n for n in self.notification_queue if n.notid != id
            ]

    def add_notification(self, notif):
        with self.notification_queue_lock:
            if notif.application in single_notification_app:
                self.notification_queue = [
                    n
                    for n in self.notification_queue
                    if n.application != notif.application
                ]
            self.notification_queue.append(notif)

    def communication_command_send_list(self, connection):
        with self.notification_queue_lock:
            for noti in self.notification_queue:
                connection.send(bytes(json.dumps(noti.to_dict()), "utf-8"))
                connection.send(b"\n")

    def communication_command_delete(self, connection, arg):
        mid = int(arg)
        with self.notification_queue_lock:
            self.notification_queue = [
                n for n in self.notification_queue if n.mid != mid
            ]

    def communication_command_delete_apps(self, connection, arg):
        with self.notification_queue_lock:
            self.notification_queue = [
                n for n in self.notification_queue if n.application != arg
            ]

    def communication_command_saw(self, connection, arg):
        mid = int(arg)
        with self.notification_queue_lock:
            for noti in self.notification_queue:
                if noti.mid == mid:
                    noti.urgency = int(Urgency.normal)
                    break

    def communication_command_delete_similar(self, connection, arg):
        mid = int(arg)
        with self.notification_queue_lock:
            application = None
            for noti in self.notification_queue:
                if noti.mid == mid:
                    application = noti.application
                    break
            if application:
                self.notification_queue = [
                    n for n in self.notification_queue if n.application != application
                ]

    def communication_command_num(self, connection):
        with self.notification_queue_lock:
            critical = sum(
                1 for n in self.notification_queue if n.urgency == Urgency.critical
            )
            mstr = f"{len(self.notification_queue)}\n{critical}"
            connection.send(bytes(mstr, "utf-8"))

    def run(self):
        # Remove stale socket from a previous unclean shutdown
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(self.socket_path)
            server.listen(1)
            server.settimeout(1)
            try:
                while True:
                    try:
                        connection, client_address = server.accept()
                        self.update_queue()
                        with connection:
                            data = connection.recv(1024).decode("utf-8")
                            command = data.split(":")[0]

                            if command == "num":
                                self.communication_command_num(connection)
                            elif command == "list":
                                self.communication_command_send_list(connection)
                            elif command == "del":
                                self.communication_command_delete(
                                    connection, data.split(":")[1]
                                )
                            elif command == "dels":
                                self.communication_command_delete_similar(
                                    connection, data.split(":")[1]
                                )
                            elif command == "dela":
                                self.communication_command_delete_apps(
                                    connection, data.split(":")[1]
                                )
                            elif command == "saw":
                                self.communication_command_saw(
                                    connection, data.split(":")[1]
                                )
                    except Exception:
                        if event.is_set():
                            break
            finally:
                if os.path.exists(self.socket_path):
                    os.unlink(self.socket_path)


class NotificationFetcher(dbus.service.Object):
    """D-Bus notification listener implementing org.freedesktop.Notifications."""

    def __init__(self, bus, path, rofication, start_id=0):
        super().__init__(bus, path)
        self._rofication = rofication
        self._id = start_id

    @dbus.service.method(
        "org.freedesktop.Notifications", in_signature="susssasa{ss}i", out_signature="u"
    )
    def Notify(
        self,
        app_name,
        notification_id,
        app_icon,
        summary,
        body,
        actions,
        hints,
        expire_timeout,
    ):
        self._id += 1
        msg = Msg(
            mid=self._id,
            notid=notification_id,
            application=str(app_name),
            summary=str(summary),
            body=str(body),
            app_icon=str(app_icon),
        )
        if int(expire_timeout) > 0:
            msg.deadline = time.time() + int(expire_timeout) / 1000.0
        if "urgency" in hints:
            msg.urgency = int(hints["urgency"])
        self._rofication.add_notification(msg)
        return notification_id

    @dbus.service.method(
        "org.freedesktop.Notifications", in_signature="", out_signature="as"
    )
    def GetCapabilities(self):
        return ["body"]

    @dbus.service.signal("org.freedesktop.Notifications", signature="uu")
    def NotificationClosed(self, id_in, reason_in):
        self._rofication.remove_notification(id_in)

    @dbus.service.method(
        "org.freedesktop.Notifications", in_signature="u", out_signature=""
    )
    def CloseNotification(self, id):
        self._rofication.remove_notification(id)

    @dbus.service.method(
        "org.freedesktop.Notifications", in_signature="", out_signature="ssss"
    )
    def GetServerInformation(self):
        return ("rofication", "http://gmpclient.org/", "0.0.1", "1")


if __name__ == "__main__":
    rofication = Rofication()

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    session_bus = dbus.SessionBus()
    name = dbus.service.BusName("org.freedesktop.Notifications", session_bus)
    rofication.load()
    nf = NotificationFetcher(
        session_bus,
        "/org/freedesktop/Notifications",
        rofication,
        rofication.last_id,
    )

    rofication.start()

    mainloop = GLib.MainLoop()

    def shutdown(signum, frame):
        mainloop.quit()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        mainloop.run()
    finally:
        event.set()
        rofication.join()
        rofication.save()
