import random
import time

from .messaging import UDPMessage, UDPMessaging, UDPPeer
from .utils import generate_id, run_in_background, log

_PING_INTERVAL = 10
_ACTIVITY_TIMEOUT = 30


class P2PPeer:
    """
    Represents a peer in a P2P network.
    """

    def __init__(self, network: "P2PNetwork", udp: UDPPeer, ident: str):
        self.network = network
        self.udp = udp
        self.ident = ident

    def send(self, message: UDPMessage):
        self.network.send(self, message)

    def __repr__(self):
        return f"<p2p peer {self.ident}>"

    def __eq__(self, other: object):
        if not isinstance(other, P2PPeer):
            return False

        return self.ident == other.ident

    def __hash__(self):
        return hash(self.ident)


class P2PNetwork:
    # ! needs to be implemented

    def __init__(self, messaging: UDPMessaging, peer_limit: int = 4):
        self.messaging = messaging
        self.my_id = generate_id("p2p")
        self.peers: dict[str, P2PPeer] = {}
        self.last_seen: dict[str, float] = {}
        self.peer_limit = peer_limit

        self.messaging.register("p2p:announce", self._handle_announce)
        self.messaging.register("p2p:ask_for_peers", self._handle_ask_for_peers)
        self.messaging.register("p2p:peers", self._handle_peers)
        self.messaging.register("p2p:ping", self._handle_ping)
        self.messaging.register("p2p:pong", self._handle_pong)

    def make_peer(self, addr: str | tuple[str, int] | UDPPeer, ident: str):
        if not isinstance(addr, UDPPeer):
            addr = UDPPeer(addr)

        return P2PPeer(self, addr, ident)

    def announce_to(self, addr: str | tuple[str, int] | UDPPeer):
        if not isinstance(addr, UDPPeer):
            addr = UDPPeer(addr)

        self.messaging.send(addr, UDPMessage("p2p:announce", self.my_id))
        self.messaging.send(addr, UDPMessage("p2p:ask_for_peers", None))

    def add_peer(self, peer: P2PPeer):
        if peer.ident in self.peers:
            # don't add peer if already in peers
            return

        if peer.ident == self.my_id:
            # don't add self to peers
            return

        log("p2p", "new peer", peer.udp)
        self.peers[peer.ident] = peer
        self.last_seen[peer.ident] = time.time()

        if len(self.peers) > self.peer_limit:
            # remove random peer
            log("p2p", "peer limit reached, removing random peer")
            del self.peers[random.choice(list(self.peers.keys()))]

        self.announce_to(peer.udp)

    def start(self):
        self.messaging.start()
        run_in_background(self._peer_loop)

    def start_network_discovery(self, start_loop: bool = True):
        run_in_background(_network_discovery_loop, self, start_loop)

    def send(self, peer: P2PPeer, message: UDPMessage):
        log("p2p", "sending message to", peer)
        self.messaging.send(peer.udp, message)

    def broadcast(self, message: UDPMessage):
        targets = self.peers.values()
        log("p2p", f"broadcasting message to {len(targets)} peers")

        for peer in targets:
            self.messaging.send(peer.udp, message)

    def _peer_loop(self):
        while True:
            log("p2p", "pinging peers")

            for peer in list(self.peers.values()):
                self.messaging.send(peer.udp, UDPMessage("p2p:ping", self.my_id))

            for id, last_seen in list(self.last_seen.items()):
                if last_seen + _ACTIVITY_TIMEOUT < time.time():
                    log("p2p", f"peer {id} timed out")
                    del self.peers[id]
                    del self.last_seen[id]

            time.sleep(_PING_INTERVAL)

    def _handle_ping(self, message: UDPMessage):
        if message.sender is None:
            return

        log("p2p", "received ping from", message.sender)

        self.messaging.send(message.sender, UDPMessage("p2p:pong", self.my_id))

    def _handle_pong(self, message: UDPMessage):
        if message.sender is None:
            return

        log("p2p", "received pong from", message.sender)

        self.last_seen[message.data] = time.time()

    def _handle_announce(self, message: UDPMessage):
        if message.sender is None:
            return

        log("p2p", "received announce from", message.sender)

        ident = message.data
        peer = self.make_peer(message.sender, ident)
        self.add_peer(peer)

    def _handle_ask_for_peers(self, message: UDPMessage):
        if message.sender is None:
            return

        log("p2p", "sending peers to", message.sender)

        peers: list[tuple[tuple[str, int], str]] = []
        for ident, peer in self.peers.items():
            peers.append((peer.udp.address, ident))

        self.messaging.send(message.sender, UDPMessage("p2p:peers", peers))

    def _handle_peers(self, message: UDPMessage):
        log("p2p", "received peers from", message.sender)

        peers = message.data
        for addr, ident in peers:
            self.add_peer(self.make_peer(addr, ident))


def _network_discovery_loop(net: P2PNetwork, start_loop: bool = True):
    node_peer: dict[str, P2PPeer] = {}
    node_last_seen: dict[str, float] = {}
    node_peers: dict[str, list[str]] = {}

    def _handle_get_peers(message: UDPMessage):
        if message.sender is None:
            return

        peers: list[str] = []
        for node_id in net.peers.keys():
            peers.append(node_id)

        net.send(
            net.make_peer(message.sender, message.data),
            UDPMessage("p2pd:get_peers_resp", [net.my_id, peers]),
        )

    def _handle_get_peers_resp(message: UDPMessage):
        node_id, peers = message.data
        node_peers[node_id] = peers
        node_last_seen[node_id] = time.time()

        log("p2d", f"got peers from {node_id}")

    net.messaging.register("p2pd:get_peers", _handle_get_peers)
    net.messaging.register("p2pd:get_peers_resp", _handle_get_peers_resp)

    if not start_loop:
        return

    while True:
        for node_id, peer in list(net.peers.items()):
            if node_id not in node_peer:
                log("p2d", f"discovered node {node_id}")
                node_peer[node_id] = peer
                node_last_seen[node_id] = time.time()
                node_peers[node_id] = []

        for node_id, peer in node_peer.items():
            peer.send(UDPMessage("p2pd:get_peers", net.my_id))

        for node_id, last_seen in list(node_last_seen.items()):
            if last_seen + _ACTIVITY_TIMEOUT < time.time():
                log("p2d", f"node {node_id} timed out")
                del node_peer[node_id]
                del node_last_seen[node_id]
                del node_peers[node_id]

        node_peers[net.my_id] = list(net.peers.keys())
        for node_id, peers in node_peers.items():
            node_peers[node_id] = peers

        with open("network_layout.txt", "w") as f:
            for node_id in sorted(node_peers.keys()):
                f.write(f"{node_id}: {', '.join(node_peers[node_id])}\n")

        time.sleep(2)
