from __future__ import annotations

import json
import time
import hashlib
import typing as t

from .search import Search
from .storage import Storage, StorageMaster
from .gossip import Gossip, GossipMessage
from .crypto import PrivateKey, PublicKey
from .utils import log, run_in_background

_DIFFICULTY = 6
_MAX_TRANSACTIONS_PER_BLOCK = 10
_BLOCK_REWARD = 10000


class Blockchain:
    def build_block(
        self,
        state: BlockchainState,
        coinbase: bytes,
        mempool: Mempool,
    ) -> Block:
        """
        Build a new block from the mempool.

        Args:
            state (BlockchainState): The current state of the blockchain.
            coinbase (bytes): The address of the miner.
            mempool (Mempool): The mempool to get transactions from.
        """
        # <<raise NotImplementedError("Blockchain.build_block")
        # ---------8<---------
        block = Block()
        block.number = state.block_number + 1
        block.parent_hash = state.block_hash
        block.coinbase = coinbase

        for tx in mempool.get_transactions():
            if not self._apply_transaction(tx, state):
                mempool.evict_transaction(tx)
            else:
                block.transactions.append(tx)

            if len(block.transactions) >= _MAX_TRANSACTIONS_PER_BLOCK:
                break

        return block
        # ---------8<---------

    def apply_block(self, block: Block, state: BlockchainState) -> None:
        """
        Apply a block to the blockchain state.

        Args:
            block (Block): The block to apply.
            state (BlockchainState): The current state of the blockchain.

        Raises:
            ValueError: If the block is invalid for whatever reason.
        """
        # <<raise NotImplementedError("Blockchain.apply_block")
        # ---------8<---------
        if block.number != state.block_number + 1:
            raise ValueError("Block number is not correct")

        if block.parent_hash != state.block_hash:
            raise ValueError("Parent hash is not correct")

        if not block.has_difficulty(_DIFFICULTY):
            raise ValueError("Block does not meet difficulty")

        for tx in block.transactions:
            if self._apply_transaction(tx, state) is not True:
                raise ValueError("Invalid transaction")

        cb_balance = state.balances.get(block.coinbase, 0)
        cb_balance += _BLOCK_REWARD
        state.balances[block.coinbase] = cb_balance

        state.block_number = block.number
        state.block_hash = block.hash

    def _apply_transaction(self, tx: Transaction, state: BlockchainState) -> bool:
        if not tx.validate_signature():
            return False

        state.balances.setdefault(tx.sender, 0)
        state.balances.setdefault(tx.receiver, 0)
        state.nonces.setdefault(tx.sender, 0)

        if state.nonces[tx.sender] != tx.nonce:
            return False

        if state.balances[tx.sender] < tx.amount:
            return False

        state.balances[tx.sender] -= tx.amount
        state.balances[tx.receiver] += tx.amount
        state.nonces[tx.sender] += 1

        return True

    # ---------8<---------


class Block:
    def __init__(self):
        self.number = 0
        self.nonce = 0
        self.parent_hash: bytes = b""
        self.coinbase: bytes = b""
        self.transactions: list[Transaction] = []
        self.hash: bytes = b""

    def has_difficulty(self, difficulty: int):
        self.calculate_hash()
        target = "0" * difficulty
        return self.hash.hex().startswith(target)

    def calculate_hash(self):
        data = self.serialize()
        self.hash = hashlib.sha256(data.encode()).digest()
        return self.hash

    def serialize(self):
        data = ""
        data += f"{self.number}"
        data += f":{self.nonce}"
        data += f":{self.parent_hash.hex()}"
        data += f":{self.coinbase.hex()}"
        for tx in self.transactions:
            data += f":{tx.serialize()}"
        return data

    @classmethod
    def deserialize(cls, data: str):
        block = cls()
        number, nonce, parent, coinbase, *transactions = data.split(":")
        block.number = int(number)
        block.nonce = int(nonce)
        block.parent_hash = bytes.fromhex(parent)
        block.coinbase = bytes.fromhex(coinbase)
        block.transactions = [Transaction.deserialize(tx) for tx in transactions]
        block.calculate_hash()
        return block

    def to_json(self) -> dict[str, t.Any]:
        self.calculate_hash()
        return {
            "number": self.number,
            "nonce": self.nonce,
            "parent_hash": self.parent_hash.hex(),
            "coinbase": self.coinbase.hex(),
            "transactions": [tx.to_json() for tx in self.transactions],
            "hash": self.hash.hex(),
        }

    def __repr__(self):
        return f"<Block {self.number} 0x..{self.hash.hex()[-8:]}>"


class Transaction:
    def __init__(self):
        self.sender = b""
        self.receiver = b""
        self.nonce = 0
        self.amount = 0
        self.sig = b""

    def data_to_sign(self):
        sender = self.sender.hex()
        receiver = self.receiver.hex()
        return f"{sender},{receiver},{self.nonce},{self.amount}"

    def serialize(self):
        assert self.sig, "Transaction not signed"

        data_to_sign = self.data_to_sign()
        sig = self.sig.hex()
        return f"{data_to_sign},{sig}"

    @classmethod
    def deserialize(cls, data: str):
        tx = cls()
        sender, receiver, nonce, amount, sig = data.split(",")
        tx.sender = bytes.fromhex(sender)
        tx.receiver = bytes.fromhex(receiver)
        tx.nonce = int(nonce)
        tx.amount = int(amount)
        tx.sig = bytes.fromhex(sig)
        return tx

    def sign(self, key: PrivateKey):
        data = self.data_to_sign().encode()
        self.sig = key.sign(data)

    def validate_signature(self):
        assert self.sig, "Transaction not signed"
        key = PublicKey.from_bytes(self.sender)
        return key.verify(self.data_to_sign().encode(), self.sig)

    def hash(self):
        return hashlib.sha256(self.serialize().encode()).digest()

    def to_json(self) -> dict[str, t.Any]:
        return {
            "hash": self.hash().hex(),
            "sender": self.sender.hex(),
            "receiver": self.receiver.hex(),
            "nonce": self.nonce,
            "amount": self.amount,
            "sig": self.sig.hex(),
        }

    def __repr__(self):
        return (
            f"<Transaction {self.sender.hex()} -> {self.receiver.hex()} {self.amount}>"
        )


class BlockchainState:
    def __init__(self, block_number: int):
        self.block_number = block_number
        self.block_hash = b""
        self.balances: dict[bytes, int] = {}
        self.nonces: dict[bytes, int] = {}

    @classmethod
    def load_from_disk(cls, blockstate_storage: Storage, block_number: int):
        data_str = blockstate_storage.load(str(block_number))
        if data_str is None:
            raise ValueError("Block state not found", block_number)

        data = json.loads(data_str)
        state = cls.from_json(data)
        assert state.block_number == block_number
        return state

    def save_to_disk(self, blockstate_storage: Storage):
        data = self.to_json()
        blockstate_storage.save(str(self.block_number), json.dumps(data))

    @classmethod
    def from_json(cls, data: dict[str, t.Any]):
        state = cls(data["block_number"])
        state.block_hash = bytes.fromhex(data["block_hash"])
        state.balances = {bytes.fromhex(k): v for k, v in data["balances"].items()}
        state.nonces = {bytes.fromhex(k): v for k, v in data["nonces"].items()}
        return state

    def to_json(self):
        return {
            "block_number": self.block_number,
            "block_hash": self.block_hash.hex(),
            "balances": {k.hex(): v for k, v in self.balances.items()},
            "nonces": {k.hex(): v for k, v in self.nonces.items()},
        }

    def copy(self):
        state = BlockchainState(self.block_number)
        state.block_hash = self.block_hash
        state.balances = self.balances.copy()
        state.nonces = self.nonces.copy()
        return state


class Mempool:
    def __init__(self, gossip: Gossip):
        self.gossip = gossip
        self._transactions: dict[bytes, Transaction] = {}
        self._last_seen: dict[bytes, float] = {}

        self.gossip.register("bc:new_tx", self._handle_new_tx)

    def start(self):
        run_in_background(self._cleanup_loop)

    def announce_transaction(self, tx: Transaction):
        log("blc", "Announcing new transaction", tx)
        self.gossip.broadcast(GossipMessage("bc:new_tx", tx.serialize()))
        self.add_transaction(tx)

    def get_transactions(self) -> list[Transaction]:
        return list(self._transactions.values())

    def evict_transaction(self, tx: Transaction) -> None:
        log("blc", "Evicting transaction", tx)
        self._transactions.pop(tx.hash(), None)
        self._last_seen.pop(tx.hash(), None)

    def add_transaction(self, tx: Transaction) -> None:
        if tx.hash() not in self._transactions:
            log("blc", "Discovered new transaction", tx)
        self._transactions[tx.hash()] = tx
        self._last_seen[tx.hash()] = time.time()

    def _handle_new_tx(self, message: GossipMessage):
        tx = Transaction.deserialize(message.data)

        if not tx.validate_signature():
            log("blc", "Invalid transaction signature:", tx)
            return

        self.add_transaction(tx)

    def _cleanup_loop(self):
        now = time.time()
        while True:
            for tx in self.get_transactions():
                if self._last_seen[tx.hash()] + 60 < now:
                    self.evict_transaction(tx)
            time.sleep(10)


class ForkManager:
    def __init__(self, gossip: Gossip, search: Search, block_storage: Storage):
        self.gossip = gossip
        self.search = search
        self.block_storage = block_storage

        self._known_blocks: dict[bytes, Block] = {}
        self._confirmed_blocks: set[bytes] = set()

        self.highest_block: Block | None = None

        self.gossip.register("bc:new_block", self._handle_new_block)
        self.search.register("block", self._search_block)

    def produce_block(self, block: Block):
        self._confirm_block_and_ancestors(block)

    def _search_block(self, block_hash: str):
        log("blc", "Searching for block", block_hash)
        block = self._get_known_block(bytes.fromhex(block_hash))
        if block is None:
            return None
        return block.serialize()

    def _handle_new_block(self, message: GossipMessage):
        block = Block.deserialize(message.data)
        log("blc", "Received new block", block)

        if not self._prevalidate_block(block.hash, block):
            log("blc", "Invalid block", block)
            return

        self._add_block_and_ancestors(block)

    def _prevalidate_block(self, hash: bytes, block: Block):
        if block.hash != hash:
            log("blc", "Block hash does not match", block, block.hash.hex())
            return False

        if not block.has_difficulty(_DIFFICULTY):
            log("blc", "Block does not meet difficulty", block, block.hash.hex())
            return False

        return True

    def _add_block_and_ancestors(self, block: Block):
        log("blc", "Adding block and ancestors", block)
        self._add_block(block)

        cur_block = block

        # find the first unknown block in the parent chain
        while True:
            if cur_block.number == 0:
                self._confirm_block_and_ancestors(block)
                return

            if self._is_confirmed_block(cur_block.hash):
                # found a confirmed block, we can mark everything as confirmed
                self._confirm_block_and_ancestors(block)
                return

            if not self._is_known_block(cur_block.parent_hash):
                # found it, it's the parent
                break

            cur_block = self.get_parent(cur_block)

        log("blc", "Found unknown parent", cur_block)

        # we don't know the parent, need to fetch it
        def _result_handler(result: str | None):
            if result is None:
                # timed out, give up
                return

            parent_block = Block.deserialize(result)
            if cur_block.parent_hash != parent_block.hash:
                return False

            if cur_block.number != parent_block.number + 1:
                return True

            if not self._prevalidate_block(parent_block.hash, parent_block):
                return True

            self._add_block(parent_block)

            # retry from start
            self._add_block_and_ancestors(block)

        self.search.search_for("block", cur_block.parent_hash.hex(), _result_handler)
        return

    def _add_block(self, block: Block):
        self._known_blocks[block.hash] = block

    def _confirm_block_and_ancestors(self, block: Block):
        log("blc", "Confirming block and ancestors", block)
        cur_block = block
        while True:
            if self._is_confirmed_block(cur_block.hash):
                break

            self._confirm_block(cur_block)

            if cur_block.number == 0:
                break

            cur_block = self.get_parent(cur_block)

        self._update_chain_tip(block)

    def _confirm_block(self, block: Block):
        self._confirmed_blocks.add(block.hash)
        self.block_storage.save(block.hash.hex(), block.serialize())
        log("blc", "Confirmed block", block)

    def _update_chain_tip(self, block: Block):
        if self.highest_block is None or block.number > self.highest_block.number:
            log("blc", "New chain tip", block)
            self.highest_block = block

    def get_highest_block(self) -> Block | None:
        return self.highest_block

    def get_parent(self, block: Block) -> Block:
        data = self._get_known_block(block.parent_hash)
        if data is None:
            raise ValueError("Parent block not found", block.parent_hash)
        return data

    def _is_known_block(self, hash: bytes) -> bool:
        return hash in self._known_blocks or self._is_confirmed_block(hash)

    def _get_known_block(self, hash: bytes) -> Block | None:
        if hash in self._known_blocks:
            return self._known_blocks[hash]

        data = self.block_storage.load(hash.hex())
        if data is None:
            return None

        block = Block.deserialize(data)
        return block

    def _is_confirmed_block(self, hash: bytes) -> bool:
        return hash in self._confirmed_blocks or self.block_storage.exists(hash.hex())


class ChainCanonicaliser:
    def __init__(
        self,
        fork_manager: ForkManager,
        blockchain: Blockchain,
        blocknum_storage: Storage,
        block_storage: Storage,
        blockstate_storage: Storage,
    ):
        self.fork_manager = fork_manager
        self.blockchain = blockchain
        self.blocknum_storage = blocknum_storage
        self.block_storage = block_storage
        self.blockstate_storage = blockstate_storage

        self.latest_num: int = self._get_latest_num()
        self.latest_hash: bytes = self._get_latest_hash()

    def update_canonical(self):
        tip = self.fork_manager.get_highest_block()
        if tip is None:
            return

        cur_latest = self._get_latest_block()

        todo: list[Block] = []

        while tip.number > cur_latest.number:
            todo.append(tip)
            tip = self.fork_manager.get_parent(tip)

        while tip.hash != cur_latest.hash:
            todo.append(tip)
            tip = self.fork_manager.get_parent(tip)
            cur_latest = self.get_block_by_hash(cur_latest.parent_hash)

        state = BlockchainState.load_from_disk(
            self.blockstate_storage, cur_latest.number
        )
        for block in reversed(todo):
            self.blockchain.apply_block(block, state)
            assert state.block_number == block.number

            state.save_to_disk(self.blockstate_storage)
            self.blocknum_storage.save(str(block.number), block.hash.hex())
            self.blocknum_storage.save("latest", str(block.number))

            self.latest_num = block.number
            self.latest_hash = block.hash

    def get_latest_state(self):
        latest_num = self._get_latest_num()
        return BlockchainState.load_from_disk(self.blockstate_storage, latest_num)

    def get_block_by_hash(self, hash: bytes) -> Block:
        data = self.block_storage.load(hash.hex())
        if data is None:
            raise ValueError("Block not found", hash)
        return Block.deserialize(data)

    def get_block_by_number(self, number: int) -> Block:
        if number == -1:
            number = self.latest_num
        hash = self.blocknum_storage.load(str(number))
        if hash is None:
            raise ValueError("Block not found", number)
        return self.get_block_by_hash(bytes.fromhex(hash))

    def get_state_at(self, number: int) -> BlockchainState:
        if number == -1:
            number = self.latest_num
        return BlockchainState.load_from_disk(self.blockstate_storage, number)

    def _get_latest_num(self):
        latest_num = self.blocknum_storage.load("latest")
        if latest_num is None:
            return 0
        return int(latest_num)

    def _get_latest_hash(self):
        latest_num = self._get_latest_num()
        latest_hash = self.blocknum_storage.load(str(latest_num))
        if latest_hash is None:
            raise ValueError("Latest block not found")
        return bytes.fromhex(latest_hash)

    def _get_latest_block(self):
        return self.get_block_by_hash(self._get_latest_hash())

    def iter_blocks(self):
        for num in range(self.latest_num + 1):
            yield self.get_block_by_number(num)


def _make_genesis():
    genesis = Block()
    genesis.number = 0
    genesis.nonce = 0
    genesis.parent_hash = b"\0" * 32
    genesis.coinbase = b"\0" * 33
    genesis.calculate_hash()

    state = BlockchainState(0)
    state.block_hash = genesis.hash
    state.balances = {}
    state.nonces = {}

    return genesis, state


class BlockchainNode:
    def __init__(self, sm: StorageMaster, gossip: Gossip, search: Search):
        self.gossip = gossip
        self.search = search

        self.blocknum_storage = Storage(sm, "blocknum")
        self.block_storage = Storage(sm, "block")
        self.blockstate_storage = Storage(sm, "blockstate")

        if not self.blocknum_storage.exists("latest"):
            self._create_genesis()

        self.blockchain = Blockchain()
        self.mempool = Mempool(gossip)
        self.fork_manager = ForkManager(gossip, search, self.block_storage)
        self.canonicaliser = ChainCanonicaliser(
            self.fork_manager,
            self.blockchain,
            self.blocknum_storage,
            self.block_storage,
            self.blockstate_storage,
        )
        self.coinbase = b"\0" * 33

    def start(self):
        self.mempool.start()

        run_in_background(self._block_producer)

    def get_block_by_number(self, number: int) -> Block:
        return self.canonicaliser.get_block_by_number(number)

    def get_balance(self, address: bytes, number: int = -1) -> int:
        state = self.canonicaliser.get_state_at(number)
        return state.balances.get(address, 0)

    def get_nonce(self, address: bytes, number: int = -1) -> int:
        state = self.canonicaliser.get_state_at(number)
        return state.nonces.get(address, 0)

    def send_transaction(self, tx: Transaction):
        self.mempool.announce_transaction(tx)

    def _block_producer(self):
        while True:
            block = self._produce_block()
            if block is None:
                continue

            log("blc", "Produced block", block)
            self.fork_manager.produce_block(block)
            self.gossip.broadcast(GossipMessage("bc:new_block", block.serialize()))

    def _produce_block(self):
        tip_block = self.fork_manager.get_highest_block()
        self.canonicaliser.update_canonical()

        state = self.canonicaliser.get_latest_state()
        coinbase = self.coinbase
        block = self.blockchain.build_block(state, coinbase, self.mempool)

        while True:
            block.calculate_hash()

            if block.has_difficulty(_DIFFICULTY):
                return block

            block.nonce += 1

            if self.fork_manager.get_highest_block() != tip_block:
                log("blc", "Chain tip changed, aborting block production")
                return None

    def _create_genesis(self):
        genesis, genesis_state = _make_genesis()
        self.block_storage.save(genesis.hash.hex(), genesis.serialize())
        self.blocknum_storage.save("0", genesis.hash.hex())
        self.blocknum_storage.save("latest", "0")
        genesis_state.save_to_disk(self.blockstate_storage)
