import contextlib
import json
import logging
import sys


# Unified Configuration
def configure_logging():
    # If using Django, you could also configure this via settings.LOGGING.
    # But since we need a single module for both Django and standalone scripts,
    # we can call this function from settings or script entry points.
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)


class JSONFormatter(logging.Formatter):
    def format(self, record):
        # Base structured log
        log_data = {
            "event": record.getMessage(),
            "level": record.levelname.lower(),
        }
        # Add kwargs if captured by the adapter
        if hasattr(record, "kwargs_data"):
            log_data.update(record.kwargs_data)

        return json.dumps(log_data, default=str)


class StructlogAdapter(logging.LoggerAdapter):
    def __init__(self, logger, extra=None):
        super().__init__(logger, extra or {})

    def process(self, msg, kwargs):
        # Extract stdlib logging kwargs so we don't put them in the payload
        # Standard keywords from logging/__init__.py
        std_keys = {"exc_info", "stack_info", "stacklevel", "extra"}
        kwargs_data = {}
        for key in list(kwargs.keys()):
            if key not in std_keys:
                kwargs_data[key] = kwargs.pop(key)

        extra = kwargs.get("extra", {})
        # Store our custom kwargs so the formatter can use them
        extra["kwargs_data"] = kwargs_data
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name):
    # Auto-configure logging if it hasn't been set up yet
    # (Though calling configure_logging explicitly is preferred)
    if not logging.getLogger().handlers:
        configure_logging()

    logger = logging.getLogger(name)
    return StructlogAdapter(logger)


class CaptureLogsHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        log_entry = {"event": record.getMessage(), "level": record.levelname.lower()}
        if hasattr(record, "kwargs_data"):
            log_entry.update(record.kwargs_data)
        self.records.append(log_entry)


@contextlib.contextmanager
def capture_logs():
    handler = CaptureLogsHandler()
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    # Store old handlers to avoid duplicate prints during tests
    old_handlers = root_logger.handlers[:]
    root_logger.handlers = [handler]

    try:
        yield handler.records
    finally:
        root_logger.handlers = old_handlers
