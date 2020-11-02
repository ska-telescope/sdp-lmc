"""Standard logging for TANGO devices."""
# pylint: disable=invalid-name
# pylint: disable=too-few-public-methods

import inspect
import logging
import pathlib
import sys
import threading
import typing

import tango
from ska.logging import configure_logging


_TANGO_TO_PYTHON = {
    tango.LogLevel.LOG_FATAL: logging.CRITICAL,
    tango.LogLevel.LOG_ERROR: logging.ERROR,
    tango.LogLevel.LOG_WARN: logging.WARNING,
    tango.LogLevel.LOG_INFO: logging.INFO,
    tango.LogLevel.LOG_DEBUG: logging.DEBUG,
    tango.LogLevel.LOG_OFF: logging.NOTSET
}


def to_python_level(tango_level: tango.LogLevel) -> int:
    """Convert a TANGO log level to a Python one.

    :param tango_level: TANGO log level
    :returns: Python log level
    """
    return _TANGO_TO_PYTHON[tango_level]


class LogManager:
    """Redirect log messages.

    This is redundant from Python 3.8 as the logging module then supports
    a "stacklevel" keyword.
    """

    def __init__(self):
        """Initialise the constructor."""
        self.frames = {}

    def make_fn(self, level: int) -> typing.Callable:
        """Create a redirection function.

        :param level: to log. default: INFO
        :returns: logging function to call
        """
        return lambda _, msg, *args: self._log_it(level, msg, *args)

    def _log_it(self, level: int, msg: str, *args) -> None:
        # There are two levels of indirection.
        # Remember the right frame in a thread-safe way.
        self.frames[threading.current_thread()] = inspect.stack()[2]
        print(f'frames {self.frames}')
        logging.log(level, msg, *args)


class TangoFilter(logging.Filter):
    """Replace the stack frame with the right one.

    This is partially redundant from Python 3.8 as the logging module
    then supports a "stacklevel" keyword.
    """

    device_name = ''
    transaction_id = ''
    log_man = LogManager()

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Modify the stack info if necessary.

        :param record: log record
        :return: true if record should be logged (always)
        """
        tags = TangoFilter.device_name
        if TangoFilter.transaction_id:
            tags += ','+TangoFilter.transaction_id
        record.tags = tags

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
    TangoFilter.transaction_id = txn_id


def get_logger() -> logging.Logger:
    """
    Get a logger instance.

    Call this after configuring.
    :return: logger
    """
    return logging.getLogger('ska_sdp_lmc')


def configure(level=tango.LogLevel.LOG_INFO, device_name: str = '',
              device_class=None) -> None:
    """Configure logging for a TANGO device.

    This modifies the logging behaviour of the device class.

    :param level: tango level to log. default: INFO
    :param device_name: name of TANGO device. default: ''
    :param device_class: class of TANGO device. default: DeviceClass
    """
    if device_class is None:
        device_class = tango.DeviceClass

    # Monkey patch the tango device logging to redirect to python.
    TangoFilter.device_name = device_name
    device_class.debug_stream = TangoFilter.log_man.make_fn(logging.DEBUG)
    device_class.info_stream = TangoFilter.log_man.make_fn(logging.INFO)
    device_class.warn_stream = TangoFilter.log_man.make_fn(logging.WARNING)
    device_class.error_stream = TangoFilter.log_man.make_fn(logging.ERROR)
    device_class.fatal_stream = TangoFilter.log_man.make_fn(logging.CRITICAL)
    device_class.get_logger = lambda self: get_logger()

    # Now initialise the logging.
    configure_logging(level=to_python_level(level),
                      tags_filter=TangoFilter)
    get_logger().debug(f'configured logging for device {device_name}')


def main(device_name: str = '', device_class=None) -> None:
    """
    Configure logging as main program.

    :param device_name: name of TANGO device. default: ''
    :param device_class: class of TANGO device. default: DeviceClass
    """
    log_level = tango.LogLevel.LOG_INFO
    if len(sys.argv) > 2 and '-v' in sys.argv[2]:
        log_level = tango.LogLevel.LOG_DEBUG
    configure(device_name=device_name, device_class=device_class, level=log_level)
