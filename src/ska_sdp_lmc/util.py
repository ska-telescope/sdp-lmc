"""Utilities."""
import functools
import inspect
import logging
import pathlib
import sys
from typing import Callable

from ska.log_transactions import transaction

LOG = logging.getLogger('ska_sdp_lmc')


# This is to find the stack info of the caller, not the one in this module.
# For some reason the device subclass is not always in the stack when run from
# BDD and the test class is found instead (might be ok).
class _CallerFilter(logging.Filter):
    def __init__(self, ignore=lambda f: False, match=lambda f: True):
        self.ignore = ignore
        self.match = match

    def filter(self, record: logging.LogRecord) -> bool:
        if record.pathname == __file__:
            frames = inspect.stack()
            for frame in frames:
                if self.ignore(frame):
                    continue
                if self.match(frame):
                    break
            record.funcName = frame.function
            record.filename = pathlib.Path(frame.filename).name
            record.lineno = frame.lineno
        return True


def transaction_command(command_function: Callable):
    """
    Decorate a command function call in a device to add transaction processing.

    :param command_function: to decorate
    :return: any result of function
    """
    @functools.wraps(command_function)
    def wrapper(self, *args, **kwargs):
        # This is a DeviceConfig. Don't use type annotation to avoid a potentially
        # circular reference. This decorator is in this module so that the
        # logging works correctly.
        config = self._config
        name = command_function.__name__
        LOG.info('-------------------------------------------------------')
        LOG.info('%s (%s)', name, self.get_name())
        LOG.info('-------------------------------------------------------')
        with transaction(name, logger=LOG) as txn_id:
            config.transaction_id = txn_id
            ret = command_function(self, *args, **kwargs)
        LOG.info('-------------------------------------------------------')
        LOG.info('%s Successful', name)
        LOG.info('-------------------------------------------------------')
        return ret
    return wrapper


LOG.addFilter(_CallerFilter(
    ignore=lambda f: f.filename == __file__,
    match=lambda f: any([text in f.filename for text in ('lmc', 'tests')])))


def terminate(signame, frame):
    """Signal handler to exit gracefully."""
    # pylint: disable=unused-argument
    sys.exit()


def log_lines(string: str, header: str = '') -> None:
    """
    Log a string split into lines.

    :param string: to split
    :param header: context information to log first
    """
    if header != '':
        LOG.info(header)
    for line in string.splitlines():
        LOG.info(line)
