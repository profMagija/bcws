import hashlib
import json
import typing as t

from .messaging import UDPMessage, UDPMessaging
from .peering import P2PNetwork

# ---------8<---------
import time
from .messaging import UDPPeer
from .utils import run_in_background, log

# ---------8<---------


class GossipMessage:
    def __init__(self, kind: str, data: t.Any, *, _raw: str | None = None):
        if _raw is not None:
            self.kind, self.data = json.loads(_raw)
            self.raw = _raw
            self.ident = hashlib.sha256(self.raw.encode()).hexdigest()
            return

        self.kind: str = kind
        self.data: t.Any = data
        self.raw: str = json.dumps([self.kind, self.data])
        self.ident: str = hashlib.sha256(self.raw.encode()).hexdigest()

    def __repr__(self):
        return f"<gossip message {self.kind} {self.data!r} #{self.ident[:6]}..>"

    def to_message(self, kind: str) -> UDPMessage:
        return UDPMessage(kind, self.raw)

    @staticmethod
    def from_message(message: UDPMessage) -> "GossipMessage":
        content = message.data
        return GossipMessage("", "", _raw=content)


GossipHandler = t.Callable[[GossipMessage], None]


class Gossip:
    def __init__(self, messaging: UDPMessaging, network: P2PNetwork):
        """
        Initialize the gossip service.

        Args:
            messaging (UDPMessaging): The messaging service.
            network (P2PNetwork): The network service.
        """
        # <<raise NotImplementedError("Gossip.__init__")
        # ---------8<---------
        self.messaging = messaging
        self.network = network
        self._handlers: dict[str, GossipHandler] = {}
        self._known_messages: dict[str, GossipMessage] = {}
        self._message_timeout: dict[str, float] = {}

        self.messaging.register("gossip:send", self._handle_send)
        # ---------8<---------

    def start(self) -> None:
        """
        Start the gossip service cleanup loop in the background.
        """
        # <<raise NotImplementedError("Gossip.start")
        # ---------8<---------
        run_in_background(self._cleanup_loop)
        # ---------8<---------

    def register(self, kind: str, handler: GossipHandler) -> None:
        """
        Register a handler for a specific kind of gossip message.

        Args:
            kind (str): The kind of gossip message to register.
            handler (GossipHandler): The handler function.

        Raises:
            ValueError: If a handler for the kind is already registered.
        """
        # <<raise NotImplementedError("Gossip.register")
        # ---------8<---------
        if kind in self._handlers:
            raise ValueError(f"Handler for {kind} already registered")
        self._handlers[kind] = handler
        # ---------8<---------

    def broadcast(self, message: GossipMessage) -> None:
        """
        Broadcast a gossip message to all peers.

        Args:
            message (GossipMessage): The message to broadcast.
        """
        # <<raise NotImplementedError("Gossip.broadcast")
        # ---------8<---------
        self._known_messages[message.ident] = message
        self._message_timeout[message.ident] = time.time() + 30

        log("gsp", "broadcasting message:", message)

        run_in_background(self.network.broadcast, message.to_message("gossip:send"))

    def _handle_send(self, message: UDPMessage, _: UDPPeer):
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
            for ident, timeout in list(self._message_timeout.items()):
                if timeout < now:
                    log("gsp", f"timing out message #{ident[:6]}...")
                    del self._known_messages[ident]
                    del self._message_timeout[ident]
            time.sleep(10)
