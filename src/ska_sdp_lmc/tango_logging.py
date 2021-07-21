"""Standard logging for TANGO devices."""

import inspect
import logging
import pathlib
import sys
import threading
from typing import Any, Callable, Iterable
import contextvars
from contextlib import contextmanager

import tango
from tango.server import Device
from ska_ser_logging import configure_logging, get_default_formatter
from ska_tango_base.base.base_device import TangoLoggingServiceHandler

_TANGO_TO_PYTHON = {
    tango.LogLevel.LOG_FATAL: logging.CRITICAL,
    tango.LogLevel.LOG_ERROR: logging.ERROR,
    tango.LogLevel.LOG_WARN: logging.WARNING,
    tango.LogLevel.LOG_INFO: logging.INFO,
    tango.LogLevel.LOG_DEBUG: logging.DEBUG,
    tango.LogLevel.LOG_OFF: logging.NOTSET,
}
_PYTHON_TO_TANGO = {v: k for k, v in _TANGO_TO_PYTHON.items()}


def to_python_level(tango_level: tango.LogLevel) -> int:
    """Convert a Tango log level to a Python one.

    :param tango_level: Tango log level
    :returns: Python log level
    """
    return (
        _TANGO_TO_PYTHON[tango_level]
        if tango_level in _TANGO_TO_PYTHON
        else logging.INFO
    )


def to_tango_level(python_level: int) -> tango.LogLevel:
    """Convert a Python log level to a Tango one.

    :param python_level: Python log level
    :returns: Tango log level
    """
    return (
        _PYTHON_TO_TANGO[python_level]
        if python_level in _PYTHON_TO_TANGO
        else tango.LogLevel.LOG_INFO
    )


class LogManager:
    """Redirect log messages.

    This is redundant from Python 3.8 as the logging module then supports
    a "stacklevel" keyword.
    """

    # pylint: disable=too-few-public-methods

    def __init__(self):
        """Initialise the constructor."""
        self.frames = {}

    def make_fn(self, level: int) -> Callable:
        """Create a redirection function.

        :param level: to log. default: INFO
        :returns: logging function to call
        """
        return lambda _, msg, *args: self._log_it(level, msg, *args)

    def _log_it(self, level: int, msg: str, *args) -> None:
        # There are two levels of indirection.
        # Remember the right frame in a thread-safe way.
        self.frames[threading.current_thread()] = inspect.stack()[2]
        logging.log(level, msg, *args)


class TangoFilter(logging.Filter):
    """Replace the stack frame with the right one.

    This is partially redundant from Python 3.8 as the logging module
    then supports a "stacklevel" keyword.
    """

    # pylint: disable=too-few-public-methods

    device_name = ""
    # Use a context variable to store the transaction ID
    transaction_id = contextvars.ContextVar("transaction_id", default="")
    log_man = LogManager()

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Modify the stack info if necessary.

        :param record: log record
        :return: true if record should be logged (always)
        """
        tags = "tango-device:" + TangoFilter.device_name
        transaction_id = TangoFilter.transaction_id.get()
        if transaction_id:
            tags += "," + transaction_id
        record.tags = tags

        level = record.levelno
        # print(f'level = {level}')
        if level not in _PYTHON_TO_TANGO:
            record.levelno = to_python_level(tango.LogLevel(level))
        # print(f'level = {level} -> {record.levelno}')

        # If the record originates from this module, insert the
        # right frame info.
        if record.pathname == __file__:
            thread = threading.current_thread()
            # The thread should be in the dictionary, but may not be if the
            # module has been reloaded e.g. by unit test.
            if thread in TangoFilter.log_man.frames:
                frame = TangoFilter.log_man.frames[thread]
                record.funcName = frame.function
                record.filename = pathlib.Path(frame.filename).name
                record.lineno = frame.lineno
        return True


def set_level(level: tango.LogLevel) -> None:
    """
    Set log level after initialisation.

    :param level: tango level to log
    """
    logging.getLogger().setLevel(to_python_level(level))


def set_transaction_id(txn_id: str) -> None:
    """
    Inject transaction id into logging.

    :param txn_id: transaction id
    """
    TangoFilter.transaction_id.set(txn_id)


@contextmanager
def log_transaction_id(txn_id):
    """
    Context manager for logging with transaction ID.

    :param txn_id: transaction ID

    """
    set_transaction_id(txn_id)
    yield
    set_transaction_id("")


def get_logger() -> logging.Logger:
    """
    Get a logger instance.

    Call this after configuring.
    :return: logger
    """
    return logging.getLogger("ska_sdp_lmc")


def configure(
    device: Any,
    device_name: str = None,
    level=tango.LogLevel.LOG_INFO,
    handlers: Iterable[logging.Handler] = None,
) -> None:
    """Configure logging for a TANGO device.

    This modifies the logging behaviour of the device class.

    :param device: to configure.
    :param device_name: alternate device name. default: None
    :param level: tango level to log. default: INFO
    :param handlers iterable of extra log handlers to install
    """

    device_class = type(device)
    if device_name is None:
        device_name = device.get_name()

    # Monkey patch the tango device logging to redirect to python.
    TangoFilter.device_name = device_name
    device_class.debug_stream = TangoFilter.log_man.make_fn(logging.DEBUG)
    device_class.info_stream = TangoFilter.log_man.make_fn(logging.INFO)
    device_class.warn_stream = TangoFilter.log_man.make_fn(logging.WARNING)
    device_class.error_stream = TangoFilter.log_man.make_fn(logging.ERROR)
    device_class.fatal_stream = TangoFilter.log_man.make_fn(logging.CRITICAL)
    # device_class.get_logger = lambda self: get_logger()

    # Now initialise the logging.
    configure_logging(level=to_python_level(level), tags_filter=TangoFilter)
    log = get_logger()
    for handler in log.handlers:
        log.removeHandler(handler)

    if handlers is None:
        handlers = []

    # If it's a real tango device, add a handler.
    if isinstance(device, Device):
        log.info("Adding tango logging handler")
        handlers.append(TangoLoggingServiceHandler(device.get_logger()))
    else:
        cls = type(device)
        log.info("Device %s is not a tango server device: %s", cls, cls.mro())

    tango_filter = TangoFilter()
    for handler in handlers:
        handler.addFilter(tango_filter)
        handler.setFormatter(get_default_formatter(tags=True))
        log.addHandler(handler)

    log.debug("Configured logging for device %s", device_name)


def init_logger(device: Any) -> None:
    """
    Configure logging in device initialisation.

    :param device: to configure.
    """
    log_level = tango.LogLevel.LOG_INFO
    if len(sys.argv) > 2 and "-v" in sys.argv[2]:
        log_level = tango.LogLevel.LOG_DEBUG
    configure(device, level=log_level)
