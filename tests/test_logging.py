import logging
import sys

import tango
from typing import Iterable

from ska_sdp_lmc import tango_logging

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

    def get_logger(self) -> logging.Logger:
        return tango_logging.get_logger()


def test_stuff():
    sys.argv = ['test']
    tango_logging.init_logger(device_name='test', device_class=FakeDevice)

    sys.argv = ['test', 'test', '-v']
    tango_logging.init_logger(device_name='test', device_class=FakeDevice)
    tango_logging.set_level(tango.LogLevel.LOG_DEBUG)

    dev = FakeDevice()
    log = tango_logging.get_logger()
    assert log is dev.get_logger()
    log.info(MSG)
    dev.info_stream(MSG)
