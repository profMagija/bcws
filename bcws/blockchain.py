import hashlib
from .storage import Storage
from .crypto import PrivateKey, PublicKey

_DIFFICULTY = 3


class Block:
    def __init__(self):
        self.number = 0
        self.nonce = 0
        self.parent_hash: bytes = b""
        self.transactions: list[Transaction] = []
        self.hash: bytes = b""

    def pow(self, difficulty: int):
        while True:
            self.calculate_hash()
            if self.has_difficulty(difficulty):
                break
            self.nonce += 1

    def has_difficulty(self, difficulty: int):
        target = b"\0" * difficulty
        return self.hash.startswith(target)

    def calculate_hash(self):
        data = self.serialize()
        self.hash = hashlib.sha256(data.encode()).digest()
        return self.hash

    def serialize(self):
        data = f"{self.number}:{self.nonce}:{self.parent_hash.hex()}"
        for tx in self.transactions:
            data += f":{tx.serialize()}"
        return data

    @classmethod
    def deserialize(cls, data: str):
        block = cls()
        number, nonce, parent, *transactions = data.split(":")
        block.number = int(number)
        block.nonce = int(nonce)
        block.parent_hash = bytes.fromhex(parent)
        block.transactions = [Transaction.deserialize(tx) for tx in transactions]
        return block


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


class Blockchain:
    def __init__(self):
        self.storage = Storage()

        self.accounts: dict[bytes, tuple[int, int]] = {}
        self.modified_accounts: dict[bytes, tuple[int, int]] = {}

    def copy(self):
        bc = Blockchain()
        bc.accounts = self.accounts.copy()
        bc.modified_accounts = self.modified_accounts.copy()
        return bc

    def apply_block(self, block: Block):
        if block.has_difficulty(_DIFFICULTY):
            return False

        for tx in block.transactions:
            if not self._apply_transaction(tx):
                return False

        self._commit_accounts(block.number)
        return True

    def _apply_transaction(self, tx: Transaction):
        if not tx.validate_signature():
            return False

        s_balance, s_nonce = self.accounts.get(tx.sender, (0, 0))
        r_balance, r_nonce = self.accounts.get(tx.receiver, (0, 0))

        if s_nonce != tx.nonce:
            return False

        if s_balance < tx.amount:
            return False

        s_nonce += 1
        s_balance -= tx.amount
        r_balance += tx.amount

        self._put_account(tx.sender, s_balance, s_nonce)
        self._put_account(tx.receiver, r_balance, r_nonce)
        return True

    def _get_account(self, address: bytes):
        if address in self.modified_accounts:
            return self.modified_accounts[address]

        if address in self.accounts:
            return self.accounts[address]

        return 0, 0

    def _put_account(self, address: bytes, balance: int, nonce: int):
        self.modified_accounts[address] = (balance, nonce)

    def _commit_accounts(self, block_number: int):
        for address, (balance, nonce) in self.modified_accounts.items():
            self.accounts[address] = (balance, nonce)
            key = f"{block_number:09}:{address.hex()}"
            self.storage.put_object("account", key, [balance, nonce])

        addresses = [a.hex() for a in self.accounts.keys()]
        self.storage.put_object("bma", f"{block_number:09}", addresses)

        self.modified_accounts.clear()

    def _delete_block(self, block_number: int):
        key = f"{block_number:09}"
        addresses = self.storage.get_object("bma", key)
        if addresses is None:
            return

        for address in addresses:
            del self.accounts[bytes.fromhex(address)]
            self.storage.delete_object("account", f"{block_number:09}:{address}")

        self.storage.delete_object("bma", key)

    def load_from_storage(self, block_number: int):
        for address, (balance, nonce) in self.storage.get_all_objects("account"):
            self.accounts[bytes.fromhex(address)] = (balance, nonce)
