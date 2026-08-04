import logging
from pathlib import Path

from request_context import RequestIdFilter

LOG_DIRECTORY = Path("logs")
LOG_DIRECTORY.mkdir(exist_ok=True)

LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s | request_id=%(request_id)s | %(message)s"
)


def configure_logging() -> None:
    handlers = [
        logging.StreamHandler(),
        logging.FileHandler(
            LOG_DIRECTORY / "app.log",
            encoding="utf-8",
        ),
    ]

    request_id_filter = RequestIdFilter()

    for handler in handlers:
        handler.addFilter(request_id_filter)

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=handlers,
    )
