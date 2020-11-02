"""Utilities."""

import inspect
import logging
import pathlib
import sys

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
