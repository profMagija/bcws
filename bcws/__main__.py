import json
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
    from .messaging import UDPMessage, UDPMessaging, UDPPeer
    from .peering import P2PNetwork

    # initialization
    udpMessaging = UDPMessaging(port)
    network = P2PNetwork(udpMessaging)

    # handler registration
    def _hello(message: UDPMessage, sender: UDPPeer):
        log("log", sender, message.data)

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


@main.command()
@click.option("--port", "-p", default=12345, help="The port to listen on.")
@click.option(
    "--peer",
    "-P",
    help="The initial peer to connect to.",
    multiple=True,
)
@click.option("--nd", is_flag=True, help="Enable network discovery.")
def search(port: int, peer: list[str], nd: bool):
    from .messaging import UDPMessaging
    from .peering import P2PNetwork
    from .gossip import Gossip
    from .search import Search

    udpMessaging = UDPMessaging(port)
    network = P2PNetwork(udpMessaging)
    gossip = Gossip(udpMessaging, network)
    search = Search(gossip)

    udpMessaging.start()
    network.start()
    network.start_network_discovery(nd)
    gossip.start()
    search.start()

    for p in peer:
        network.announce_to(p)

    my_items: dict[str, str] = {}

    def _item_searcher(query: str):
        if query in my_items:
            return my_items[query]

    search.register("item", _item_searcher)

    while True:
        action = input("[s]earch, [p]rovide, [q]uit: ").lower()
        if action == "s":
            query = input("Enter query: ")

            def _result_handler(message: str):
                print(f"Received result for '{query}':", message)

            search.search_for("item", query, _result_handler)
        elif action == "p":
            item = input("Enter item: ")
            value = input("Enter value: ")
            my_items[item] = value
        elif action == "q":
            break
        else:
            print("Invalid action. Try again.")


@main.command()
@click.option("--port", "-p", default=12345, help="The port to listen on.")
@click.option(
    "--peer",
    "-P",
    help="The initial peer to connect to.",
    multiple=True,
)
@click.option("--nd", is_flag=True, help="Enable network discovery.")
@click.option("--ds", is_flag=True, help="Dump blockchain state periodically.")
@click.option("--state-dir", default=".stor")
def blockchain(port: int, peer: list[str], nd: bool, ds: bool, state_dir: str):
    from .messaging import UDPMessaging
    from .peering import P2PNetwork
    from .gossip import Gossip
    from .search import Search
    from .blockchain import BlockchainNode, Transaction
    from .storage import Storage, StorageMaster
    from .crypto import PrivateKey
    from .utils import run_in_background

    udpMessaging = UDPMessaging(port)
    network = P2PNetwork(udpMessaging)
    gossip = Gossip(udpMessaging, network)
    search = Search(gossip)
    sm = StorageMaster(state_dir)
    blockchain_node = BlockchainNode(sm, gossip, search)

    pk_storage = Storage(sm, "privkey")
    pk_str = pk_storage.load("privkey")
    if pk_str is None:
        pk = PrivateKey.generate()
        pk_storage.save("privkey", pk.to_bytes().hex())
    else:
        pk = PrivateKey.from_bytes(bytes.fromhex(pk_str))

    my_address = pk.to_public().to_bytes()

    blockchain_node.coinbase = my_address

    udpMessaging.start()
    network.start()
    network.start_network_discovery(nd)
    gossip.start()
    search.start()
    blockchain_node.start()

    for p in peer:
        network.announce_to(p)

    if ds:

        @run_in_background
        def _():
            while True:
                blocks = [
                    b.to_json() for b in blockchain_node.canonicaliser.iter_blocks()
                ]
                latest_state = (
                    blockchain_node.canonicaliser.get_latest_state().to_json()
                )
                with open("state.json", "w") as f:
                    json.dump(
                        {"blocks": blocks, "latest_state": latest_state},
                        f,
                        indent=2,
                    )
                time.sleep(10)

    while True:
        action = input("[s]end, [b]alance, [n]once, [l]atest, [q]uit: ").lower()
        if action == "s":
            receiver = input("Enter recipient: ")
            amount = int(input("Enter amount: "))

            tx = Transaction()
            tx.nonce = blockchain_node.get_nonce(my_address)
            tx.sender = my_address
            tx.receiver = bytes.fromhex(receiver)
            tx.amount = amount
            tx.sign(pk)

            blockchain_node.send_transaction(tx)

        elif action == "b":
            address = input("Enter address: ")
            if address == "":
                address = my_address.hex()
            print(blockchain_node.get_balance(bytes.fromhex(address)))
        elif action == "n":
            address = input("Enter address: ")
            if address == "":
                address = my_address.hex()
            print(blockchain_node.get_nonce(bytes.fromhex(address)))
        elif action == "l":
            state = blockchain_node.canonicaliser.get_latest_state()
            print("Latest state:")
            print("  Block number:", state.block_number)
            print("  Block hash:", state.block_hash.hex())
            print("  Accounts:")
            for address, balance in state.balances.items():
                print("    ", address.hex(), balance, state.nonces.get(address, 0))
            print()

        elif action == "q":
            break
        else:
            print("Invalid action. Try again.")


if __name__ == "__main__":
    main()
