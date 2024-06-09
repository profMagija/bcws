import os
import threading
import typing as t

_enable_all_logs = False
_ENABLED_LOGS: set[str] = {"err", "log"}


def enable_log(kind: str):
    global _enable_all_logs

    if kind == "":
        return

    if kind == "all":
        _enable_all_logs = True

    _ENABLED_LOGS.add(kind)


_P = t.ParamSpec("_P")


def run_in_background(func: t.Callable[_P, t.Any], *args: _P.args, **kwargs: _P.kwargs):
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()


def generate_id(kind: str):
    return f"{kind}:{os.urandom(8).hex()}"


def log(kind: str, *args: t.Any):
    if not _enable_all_logs and kind not in _ENABLED_LOGS:
        return

    leader = "\x1b[1;32m"
    if kind == "err":
        leader = "\x1b[1;31m"
    elif kind == "log":
        leader = "\x1b[1;34m"

    print(f"{leader}[{kind}]\x1b[0m", *args)
