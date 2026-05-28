import re
from dataclasses import dataclass, field, asdict
from enum import IntEnum


class Urgency(IntEnum):
    low = 0
    normal = 1
    critical = 2


@dataclass
class Msg:
    mid: int = 0
    notid: int = -1
    message: str = ""
    deadline: float = -1
    summary: str = ""
    body: str = ""
    application: str = "n/a"
    app_icon: str = ""
    urgency: int = int(Urgency.normal)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Msg":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def linesplit(sock):
    buffer = sock.recv(16)
    buffer = buffer.decode("UTF-8")
    buffering = True
    while buffering:
        if "\n" in buffer:
            (line, buffer) = buffer.split("\n", 1)
            yield line
        else:
            more = sock.recv(16)
            more = more.decode("UTF-8")
            if not more:
                buffering = False
            else:
                buffer += more
    if buffer:
        yield buffer


def strip_tags(value: str) -> str:
    """Return the given HTML with all tags stripped."""
    return re.sub(r"<[^>]*?>", "", value)
