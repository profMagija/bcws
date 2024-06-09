import click
import time

from .utils import enable_log, log


@click.group()
@click.option("--log", "-L", default="")
def main(log: str):
    for item in log.split(","):
        enable_log(item)


@main.command()
@click.option("--port", "-p", default=12345, help="The port to listen on.")
@click.option(
    "--peer",
    "-P",
    help="The initial peer to connect to.",
    multiple=True,
    required=True,
)
def messaging(port: int, peer: list[str]):
    from .network import PrintingHandler, UDPNode, UDPPeer

    # initialization
    udp = UDPNode(port, PrintingHandler())

    # start
    udp.start()

    while True:
        message = input("Enter message: ")
        udp.send(UDPPeer(peer[0]), message.encode())


@main.command()
@click.option("--port", "-p", default=12345, help="The port to listen on.")
@click.option(
    "--peer",
    "-P",
    help="The initial peer to connect to.",
    multiple=True,
)
def peering(port: int, peer: list[str]):
    from .messaging import UDPMessage, UDPMessaging
    from .peering import P2PNetwork

    # initialization
    udpMessaging = UDPMessaging(port)
    network = P2PNetwork(udpMessaging)

    # handler registration
    def _hello(message: UDPMessage):
        log("log", message.sender, message.data)

    udpMessaging.register("hello", _hello)

    # start & joining
    network.start()
    for p in peer:
        network.announce_to(p)

    while True:
        message = input("Enter message: ")
        network.broadcast(UDPMessage("hello", message))


@main.command()
@click.option("--port", "-p", default=12345, help="The port to listen on.")
@click.option(
    "--peer",
    "-P",
    help="The initial peer to connect to.",
    multiple=True,
)
@click.option("--nd", is_flag=True, help="Enable network discovery.")
def gossip(port: int, peer: list[str], nd: bool):
    from .messaging import UDPMessaging
    from .peering import P2PNetwork
    from .gossip import Gossip, GossipMessage

    # initialization
    udpMessaging = UDPMessaging(port)
    network = P2PNetwork(udpMessaging)
    gossip = Gossip(udpMessaging, network)

    # handler registration
    def _print_msg(message: GossipMessage):
        sender, text, _ = message.data
        log("log", "message:", sender, ":", text)

    gossip.register("msg", _print_msg)

    # start & joining
    network.start()
    network.start_network_discovery(nd)

    for p in peer:
        network.announce_to(p)

    # while True:
    #     text = input("Enter message: ")
    #     message = [network.my_id, text, time.time()]
    #     gossip.broadcast(GossipMessage("msg", message))
    time.sleep(1000)


if __name__ == "__main__":
    main()
