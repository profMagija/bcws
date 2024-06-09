import hashlib
import json
import time
import typing as t

from .messaging import UDPMessage, UDPMessaging
from .peering import P2PNetwork
from .utils import run_in_background, log


class GossipMessage:
    def __init__(self, kind: str, data: t.Any, _raw: str | None = None):
        if _raw is not None:
            self.kind, self.data = json.loads(_raw)
            self.raw = _raw
            self.ident = hashlib.sha256(self.raw.encode()).hexdigest()
            return

        self.kind = kind
        self.data = data
        self.raw = json.dumps([self.kind, self.data])
        self.ident = hashlib.sha256(self.raw.encode()).hexdigest()

    def __repr__(self):
        return f"<gossip message {self.kind} {self.data!r} #{self.ident[:6]}..>"

    def to_message(self, kind: str) -> UDPMessage:
        return UDPMessage(kind, self.raw)

    @staticmethod
    def from_message(message: UDPMessage) -> "GossipMessage":
        content = message.data
        return GossipMessage("", "", content)


GossipHandler = t.Callable[[GossipMessage], None]


class Gossip:
    def __init__(self, messaging: UDPMessaging, network: P2PNetwork):
        self.messaging = messaging
        self.network = network
        self._known_messages: dict[str, GossipMessage] = {}
        self._message_timeout: dict[str, float] = {}

        self._handlers: dict[str, GossipHandler] = {}

        self.messaging.register("gossip:send", self._handle_send)

    def start(self):
        run_in_background(self._cleanup_loop)

    def register(self, kind: str, handler: GossipHandler):
        if kind not in self._handlers:
            self._handlers[kind] = handler
        else:
            raise ValueError(f"Handler for {kind} already registered")

    def broadcast(self, message: GossipMessage):
        self._known_messages[message.ident] = message
        self._message_timeout[message.ident] = time.time() + 30

        log("gsp", "broadcasting message:", message)

        run_in_background(self.network.broadcast, message.to_message("gossip:send"))

    def _handle_send(self, message: UDPMessage):
        gossip = GossipMessage.from_message(message)
        if gossip.ident in self._known_messages:
            return

        if gossip.kind in self._handlers:
            self._handlers[gossip.kind](gossip)
        else:
            log("err", f"unhandled gossip message kind: {gossip.kind}")

        self.broadcast(gossip)

    def _cleanup_loop(self):
        while True:
            now = time.time()
            for ident, timeout in self._message_timeout.items():
                if timeout < now:
                    log("gsp", f"timing out message #{ident[:6]}...")
                    del self._known_messages[ident]
                    del self._message_timeout[ident]
            time.sleep(10)
