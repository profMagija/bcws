import json
import typing as t
import os


class Storage:
    def __init__(self):
        os.makedirs(".stor", exist_ok=True)
        os.makedirs(".stor/objects", exist_ok=True)

    def exists_object(self, kind: str, ident: str):
        return os.path.exists(f".stor/objects/{kind}/{ident}.json")

    def get_all_objects(self, kind: str):
        for ident in os.listdir(f".stor/objects/{kind}"):
            with open(f".stor/objects/{kind}/{ident}", "r") as f:
                yield ident, json.load(f)

    def get_object(self, kind: str, ident: str):
        if not self.exists_object(kind, ident):
            return None

        with open(f".stor/objects/{kind}/{ident}.json", "r") as f:
            return json.load(f)

    def put_object(self, kind: str, ident: str, obj: t.Any):
        os.makedirs(f".stor/objects/{kind}", exist_ok=True)
        with open(f".stor/objects/{kind}/{ident}.json", "w") as f:
            json.dump(obj, f, indent=2)

    def delete_object(self, kind: str, ident: str):
        if self.exists_object(kind, ident):
            os.remove(f".stor/objects/{kind}/{ident}.json")
