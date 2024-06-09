import time
import typing as t

from .gossip import Gossip, GossipMessage
from .utils import generate_id, run_in_background

SearchResultHandler = t.Callable[[t.Any], bool | None]
Searcher = t.Callable[[str], t.Any]


class Search:
    def __init__(self, gossip: Gossip):
        self.gossip = gossip
        self._searchers: dict[str, Searcher] = {}

        self._queries: dict[str, tuple[float, SearchResultHandler]] = {}

        self.gossip.register("search:query", self._handle_query)
        self.gossip.register("search:response", self._handle_response)

    def start(self):
        run_in_background(self._cleanup_loop)

    def register(self, kind: str, searcher: Searcher):
        if kind in self._searchers:
            raise ValueError(f"Searcher for {kind} already registered")
        self._searchers[kind] = searcher

    def search_for(
        self,
        kind: str,
        ident: str,
        handler: SearchResultHandler,
        timeout: int = 60,
    ):
        query_id = generate_id("q")
        self._queries[query_id] = (time.time() + timeout, handler)
        self.gossip.broadcast(GossipMessage("search:query", [query_id, kind, ident]))

    def _handle_query(self, message: GossipMessage):
        query_id, kind, ident = message.data
        searcher = self._searchers.get(kind)
        if searcher is None:
            return

        result = searcher(ident)
        if result is None:
            return

        self.gossip.broadcast(GossipMessage("search:response", [query_id, result]))

    def _handle_response(self, message: GossipMessage):
        query_id, result = message.data

        _, handler = self._queries.get(query_id, (0, None))
        if handler is None:
            return

        if handler(result):
            del self._queries[query_id]

    def _cleanup_loop(self):
        to_cleanup: list[str] = []
        for key, (timeout, _) in self._queries.items():
            if timeout < time.time():
                to_cleanup.append(key)

        for key in to_cleanup:
            _, handler = self._queries.pop(key)
            handler(None)
