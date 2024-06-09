import typing as t

from .gossip import Gossip

# ---------8<---------
import time
from .gossip import GossipMessage
from .utils import generate_id, run_in_background, log

# ---------8<---------

SearchResultHandler = t.Callable[[t.Any], bool | None]
Searcher = t.Callable[[t.Any], t.Any]


class Search:
    def __init__(self, gossip: Gossip):
        self.gossip = gossip
        # <<raise NotImplementedError("Search.__init__")
        # ---------8<---------
        self._searchers: dict[str, Searcher] = {}
        self._queries: dict[str, tuple[float, SearchResultHandler]] = {}

        self.gossip.register("search:query", self._handle_query)
        self.gossip.register("search:response", self._handle_response)
        # ---------8<---------

    def start(self) -> None:
        """
        Start the search service in the background.
        """
        # <<raise NotImplementedError("Search.start")
        # ---------8<---------
        run_in_background(self._cleanup_loop)
        # ---------8<---------

    def register(self, kind: str, searcher: Searcher) -> None:
        """
        Register a searcher for a specific kind of search.

        A searcher is a function that takes an identifier and returns the
        result, or None if not found.

        Args:
            kind (str): The kind of search to register.
            searcher (Searcher): The searcher function.

        Raises:
            ValueError: If a searcher for the kind is already registered.
        """
        # <<raise NotImplementedError("Search.register")
        # ---------8<---------
        if kind in self._searchers:
            raise ValueError(f"Searcher for {kind} already registered")
        self._searchers[kind] = searcher
        # ---------8<---------

    def search_for(
        self,
        kind: str,
        query: t.Any,
        handler: SearchResultHandler,
        timeout: int = 60,
    ) -> None:
        """
        Search for an identifier of a specific kind. The handler will be called
        with the result when found, or None if not found.

        If the handler returns True, the search will be stopped, and not called again.

        Args:
            kind (str): The kind of search to perform.
            query (Any): The query for the search. The type is specific to the search kind.
            handler (SearchResultHandler): The handler to call with the result.
            timeout (int, optional): The timeout in seconds. Defaults to 60.
        """
        # <<raise NotImplementedError("Search.search_for")
        # ---------8<---------
        query_id = generate_id("q")
        log("sch", f"search {query_id} for {kind}: {query}")
        self._queries[query_id] = (time.time() + timeout, handler)
        self.gossip.broadcast(GossipMessage("search:query", [query_id, kind, query]))

    def _handle_query(self, message: GossipMessage):
        query_id, kind, query = message.data
        searcher = self._searchers.get(kind)
        if searcher is None:
            log("err", f"no searcher found for {kind}")
            return

        result = searcher(query)
        log("sch", f"search {query_id} for {kind}: found {result}")
        if result is None:
            return

        self.gossip.broadcast(GossipMessage("search:response", [query_id, result]))

    def _handle_response(self, message: GossipMessage):
        query_id, result = message.data

        _, handler = self._queries.get(query_id, (0, None))
        if handler is None:
            return

        log("sch", f"received result for {query_id}: {result}")

        if handler(result):
            log("sch", f"handler for {query_id} returned True, stopping search")
            del self._queries[query_id]

    def _cleanup_loop(self):
        for key, (timeout, _) in list(self._queries.items()):
            if timeout < time.time():
                _, handler = self._queries.pop(key)
                handler(None)
                log("sch", f"query {key} timed out")
