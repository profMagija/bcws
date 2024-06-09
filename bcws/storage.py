import os


class StorageMaster:
    def __init__(self, root: str):
        self.root = root


class Storage:
    def __init__(self, master: StorageMaster, name: str):
        self.master = master
        self.name = name

        if not os.path.exists(os.path.join(self.master.root, name)):
            os.makedirs(os.path.join(self.master.root, name))

    def exists(self, path: str) -> bool:
        return os.path.exists(self._make_path(path))

    def load(self, path: str) -> str | None:
        try:
            with open(self._make_path(path), "r") as f:
                return f.read()
        except FileNotFoundError:
            return None

    def save(self, path: str, content: str):
        with open(self._make_path(path), "w") as f:
            f.write(content)

    def delete(self, path: str):
        os.remove(self._make_path(path))

    def _make_path(self, path: str) -> str:
        return os.path.join(self.master.root, self.name, path)

    def __repr__(self) -> str:
        return f"Storage({self.name!r})"
