"""Utilities."""
import copy
import inspect
import logging
import pathlib
import sys
from typing import List, Type, Optional

LOG = logging.getLogger('ska_sdp_lmc')


# This is to find the stack info of the caller, not the one in this module.
# For some reason the device subclass is not always in the stack when run from
# BDD and the test class is found instead (might be ok).
class _CallerFilter(logging.Filter):
    # pylint: disable=too-few-public-methods
    # pylint: disable=super-init-not-called

    def __init__(self, ignore=lambda f: False, match=lambda f: True):
        self.ignore = ignore
        self.match = match

    def filter(self, record: logging.LogRecord) -> bool:
        if record.pathname == __file__:
            frames = inspect.stack()
            frame = None
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


def is_test_env() -> bool:
    """Is the environment a test one?"""
    return 'pytest' in sys.modules


def terminate(signame, frame):
    """Signal handler to exit gracefully."""
    # pylint: disable=unused-argument
    sys.exit()


def check_args(cls: Type, args: Optional[List[str]]) -> Optional[List[str]]:
    """
    Make sure the first argument has the right name. It should be the name of
    the class but might not be depending on how it's called. If it isn't
    the tango database lookup will fail.

    :param cls: class to enforce
    :param args: command line arguments
    :return modified arguments
    """
    argv = copy.copy(args)
    if argv:
        argv[0] = cls.__name__
    return argv
