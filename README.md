# Let's make some money - Blockchain workshop

## Introduction

This workshop is designed to give you a deeper understanding how decentralized systems work and how to build your own blockchain. We will start with simple networking primitives, build some decentralized communication primitives on top of those, and finally build a simple blockchain.

## Prerequisites

- Basic understanding of Python
- Basic understanding of networking
- Basic understanding of cryptography

# Part 1: Networking

## Introduction

In this part we will build a simple networking layer that will allow us to send messages between nodes. The networking layer will be based on the `socket` module in Python, UDP protocol, and will be able to send and receive messages.

## Your task

In the file [networking.py](bcws/networking.py) you will find a skeleton of a `UDPNode` class. This class should implement a simple UDP networking layer that will allow us to send and receive messages between nodes.

Your task is to implement this class. The class should have the following methods:

* `__init__` - a constructor that should initialize the socked and bind it to the given port. The arguments are:
  * `port: int` - the port to bind the socket to. You should listen on all addresses.
  * `handler: UDPHandler` - an object that will handle incoming messages. You must call this objects `handle_receive(data, peer)` method when a message is received.
* `start` - a method that starts the node in the background. This method should start a new thread that will listen for incoming messages.
* `send` - a method that sends a message to a given address. The arguments are:
  * `peer: UDPPeer` - the address to send the message to.
  * `data: bytes` - the data to send.

# Part 2: Messaging

To simplify the communication between nodes, we will introduce a simple messaging abstraction over the raw UDP layer. Each message sent will contain the **message kind** and **message payload**. The kind is a string identifying the type of the message, and the payload is the actual data.

You can use the `UDPMessaging` class to send and receive messages. To send the message simply construct it using the `UDPMessage` constructor, and send it using the `send` method:

```python
messaging = UDPMessaging(1234)
message = UDPMessage('hello', ['some', 'data', 'here'])
messaging.send(UDPPeer('192.168.10.1', 1235), message)
```

To receive the message, you first have to register the message handler. The handler will be invoked whenever a message is received. It must be a function that takes two arguments: the received message and the peer that sent the message.

```python
def _handle_hello(message: UDPMessage, peer: UDPPeer):
  print(f'Received message from {peer}: {message.kind} {message.data}')

messaging.register('hello', _handle_hello)
```

For each message kind, we will define the format of the payload as it is introduced. 

# Part 3: Peering

## Introduction

Peering is a process of connecting multiple nodes together in a peer-to-peer network. In this part we will build a simple peering layer that will allow us to connect multiple nodes together into a mesh network.

Each node has a unique identifier, and maintains a list of peers. When a node connects to another node, it sends an `p2p:announce` message to the other node, which should add the sender as a peer. The receiver should also respond with an `p2p:announce` message, so that the sender can add the receiver as a peer.

The nodes can send eachother `p2p:ask_for_peers` to ask for the list of peers of the other node. The receiver should respond with a `p2p:peers` message, containing the addresses of its peers.

### Messages involved

We will use a number of messages with the following kinds:

* `p2p:announce` - the sender announces itself to the receiver, who should add it as a peer. Payload: `id: str`.
* `p2p:ask_for_peers` - the sender asks the receiver for the list of its peers. Payload: `None`.
* `p2p:peers` - the sender is sending its list of peers to the receiver. Payload: `peers: List[str]`. Send as an answer to `p2p:ask_for_peers`.
* `p2p:ping` - the sender is pinging the receiver to check if it is still alive. Payload: `None`.
* `p2p:pong` - the sender is responding to the ping. Payload: `None`. Sent as an answer to `p2p:ping`.

## Your task

In the file [peering.py](bcws/peering.py) you will find a skeleton of a `P2PNetwork` class. This class should implement a simple peering layer that will allow us to connect multiple nodes together.

Your task is to implement this class. The class should have the following methods:

* `__init__` - a constructor that should initialize the network. The arguments are:
  * `messaging: UDPMessaging` - a messaging layer that will be used to send and receive messages.
  * `peer_limit: int` - the maximum number of peers that can be connected to this node.
* `announce_to` - a method that should announce this node to a given address, and ask for the peer's peers. The arguments are:
  * `peer: UDPPeer` - the peer to announce to.
* `add_peer` - a method that should add a peer to the list of our peers. It just takes the `peer: P2PPeer` as an argument. Make sure that:
  * We are not connected to the same peer multiple times.
  * We are not connected to ourselves.
  * We are not connected to more peers than `peer_limit`. If we would exceed the limit, we should disconnect from one of the peers at random.
  * After we connect to the peer, we should announce ourselves to the peer, just in case they don't know about us yet.
* `start` - a method that should start the network in the background. In the background process, we should periodically:
  * ping all of our peers to check if they are still alive.
  * remove all peers that we haven't seen for a while.
* `send` - a method that should send a message to a given peer. The arguments are:
  * `peer: P2PPeer` - the peer to send the message to.
  * `data: UDPMessage` - the message to send.
* `broadcast` - a method that should send a message to all of our peers. The arguments are:
  * `data: UDPMessage` - the message to send.

# Part 4: Gossip

## Introduction

Gossip is a simple protocol that allows nodes to share information with each other, even if they are not directly connected. In this part we will build a simplified gossip layer that will allow us to share messages between nodes.

Each node maintains a list of messages that it has seen. When a node receives a new message (via a `gossip:send`), it should add it to the list of seen messages, and broadcast it to all of its peers.

Gossip is implemented similarly to messaging, where each message has a kind and a payload, and you register handlers for specific kinds. Note that it still uses the previously implemented messaging layer, wrapping each gossip message in a `gossip:send` UDP message (which is then wrapped in a UDP packet (which is then wrapped in an IP packet (which is then wrapped in an Ethernet frame (and its turtles all the way down)))).

Each message contains a unique identifier, which is the SHA256 hash of the message kind and payload. This identifier is then used to check if we have already seen the message. This also means that the users of the gossip layer should not send the same message multiple times, as it will be ignored.

## Your task

In the file [gossip.py](bcws/gossip.py) you will find a skeleton of a `Gossip` class. This class should implement a simple gossip layer that will allow us to share messages between nodes. Your task is to implement this class. The class should have the following methods:

* `__init__` - a constructor that should initialize the gossip layer. The arguments are:
  * `messaging: UDPMessaging` - a messaging layer that will be used to send and receive messages.
  * `network: P2PNetwork` - the reference to the peering network, for peer management.
* `start` - a method that should start the gossip layer in the background. In the background process, we should periodically time out messages we received more than `message_timeout` seconds ago.
* `broadcast` - a method that should broadcast a message to the entire network, by gossiping it to all of our peers. The argument is `message: GossipMessage`.
