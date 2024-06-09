import json
import traceback
import typing as t

from .network import UDPHandler, UDPNode, UDPPeer
from .utils import log


class UDPMessage:
    """
    Represents a message in the network. A message has a kind, data, and an
    optional sender. This is a higher-level abstraction on top of raw bytes.
    """

    def __init__(self, kind: str, data: t.Any, sender: t.Optional[UDPPeer] = None):
        self.kind = kind
        self.sender = sender
        self.data = data

    @staticmethod
    def from_bytes(content: bytes, sender: t.Optional[UDPPeer] = None) -> "UDPMessage":
        kind, data = json.loads(content)
        return UDPMessage(kind, data, sender)

    def to_bytes(self) -> bytes:
        return json.dumps([self.kind, self.data]).encode()


MessageHandler = t.Callable[[UDPMessage], None]


class MessageDispatchHandler(UDPHandler):
    """
    A handler that dispatches messages to the appropriate handlers.
    """

    def __init__(self, dispatch: "UDPMessaging"):
        self.dispatch = dispatch

    def handle_receive(self, data: bytes, address: UDPPeer):
        try:
            message = UDPMessage.from_bytes(data, address)
            self.dispatch.dispatch(message)
        except:
            traceback.print_exc()


class UDPMessaging:
    """
    A higher-level messaging system that builds on top of UDPNode. This class allows registering message handlers
    """

    def __init__(self, port: int):
        """
        Initializes the messaging system.

        :param port: The port to listen on.
        """
        self.handler = MessageDispatchHandler(self)
        self.udp = UDPNode(port, self.handler)

        self.handlers: dict[str, MessageHandler] = {}

    def start(self):
        """Starts the underlying UDP node."""
        self.udp.start()

    def send(self, peer: UDPPeer, message: UDPMessage):
        """Sends a message to a peer."""
        self.udp.send(peer, message.to_bytes())
        log("msg", f"send {peer}: {message.kind} {message.data!r}")

    def register(self, kind: str, handler: MessageHandler):
        """Registers a message handler for a specific message kind."""
        if kind in self.handlers:
            raise ValueError(f"handler for {kind} already registered")

        self.handlers[kind] = handler

    def dispatch(self, message: UDPMessage):
        """Dispatches a message to the appropriate handler."""
        log("msg", f"recv {message.sender}: {message.kind} {message.data!r}")
        handler = self.handlers.get(message.kind)
        if handler is not None:
            handler(message)
        else:
            log("err", f"no handler for {message.kind}")
