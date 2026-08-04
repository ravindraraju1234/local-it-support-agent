import logging
import re
import uuid
from contextvars import ContextVar

REQUEST_ID_HEADER = "X-Request-ID"

MAX_REQUEST_ID_LENGTH = 64

# Client-supplied IDs land in log lines and in a response header, so restrict
# them to characters that cannot forge a log record or split a header.
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,%d}$" % MAX_REQUEST_ID_LENGTH)

_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def resolve_request_id(incoming: str | None) -> str:
    """Reuse a valid caller-supplied ID, otherwise mint a new one."""
    if incoming and SAFE_REQUEST_ID.match(incoming):
        return incoming

    return str(uuid.uuid4())


def set_request_id(request_id: str):
    return _request_id.set(request_id)


def reset_request_id(token) -> None:
    _request_id.reset(token)


def get_request_id() -> str:
    return _request_id.get()


class RequestIdFilter(logging.Filter):
    """Stamps every log record with the current request's ID."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True
