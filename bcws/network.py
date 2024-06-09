# --------8<--------
import socket

from .utils import run_in_background

# --------8<--------
from .utils import log


class UDPPeer:
    """
    Represents a peer in a UDP network.

    Can be created from a string in the format "address:port", or a tuple of
    (address, port).
    """

    def __init__(self, address: tuple[str, int] | str):
        if isinstance(address, str):
            addr, port = tuple(address.split(":"))
            address = (addr, int(port))

        self.address = address[0], address[1]

    def __repr__(self):
        return f"<udp peer {self}>"

    def __str__(self):
        return f"{self.address[0]}:{self.address[1]}"

    def __eq__(self, other: object):
        if not isinstance(other, UDPPeer):
            return False

        return self.address == other.address

    def __hash__(self):
        return hash(self.address)


class UDPHandler:
    """
    Handles incoming UDP messages. Abstract base class.
    """

    def handle_receive(self, data: bytes, address: UDPPeer) -> None:
        raise NotImplementedError


class UDPNode:
    """
    The main implementation of a UDP node. This class is responsible for sending and receiving messages.
    """

    #! needs to be implemented

    def __init__(self, port: int, handler: UDPHandler):
        # <<raise NotImplementedError("UDPNode.__init__")
        # --------8<--------
        self.port = port
        self.handler = handler

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.socket.bind(("0.0.0.0", port))
        # --------8<--------

    def start(self) -> None:
        # <<raise NotImplementedError("UDPNode.start")
        # --------8<--------
        run_in_background(self._recv_loop)
        # --------8<--------

    def send(self, peer: UDPPeer, data: bytes) -> None:
        # <<raise NotImplementedError("UDPNode.send")
        # --------8<--------
        self.socket.sendto(data, peer.address)
        log("udp", f"send {peer} : {data.hex()}")

    def _recv_loop(self):
        log("udp", "started listening")
        while True:
            data, address = self.socket.recvfrom(1024)
            self.handler.handle_receive(data, UDPPeer(address))

        # --------8<--------


class PrintingHandler(UDPHandler):
    """
    A simple handler that prints received messages.
    """

    def handle_receive(self, data: bytes, address: UDPPeer):
        log("udp", f"recv {address}: {data.decode()}")
