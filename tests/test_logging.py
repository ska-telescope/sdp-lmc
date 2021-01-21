import logging
import sys

import tango
from typing import Iterable

from ska_sdp_lmc import tango_logging as tl

MSG = "Running tango test"


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.list = []

    def emit(self, record: logging.LogRecord) -> None:
        self.list.append(self.format(record))

    def get_last(self) -> str:
        return self.list[-1]

    def get_last_tag(self) -> str:
        return self.get_last().split('|')[6]

    def __iter__(self) -> Iterable[str]:
        return self.list.__iter__()


class FakeDevice:
    def info_stream(self, _: str, *args) -> None:
        print("info stream should not be called")

    def get_name(self) -> str:
        return 'fake'

    def get_logger(self) -> logging.Logger:
        return tl.get_logger()


def test_stuff():
    dev = FakeDevice()

    sys.argv = ['test']
    tl.init_logger(dev)

    sys.argv = ['test', 'test', '-v']
    tl.init_logger(dev)
    tl.set_level(tango.LogLevel.LOG_DEBUG)

    assert tl.to_tango_level(logging.INFO) == tango.LogLevel.LOG_INFO
    assert tl.to_python_level(tango.LogLevel.LOG_INFO) == logging.INFO

    log = tl.get_logger()
    assert log is dev.get_logger()
    log.info(MSG)
    dev.info_stream(MSG)
