"""Functions for creating Tango device commands."""

import json
import functools
from typing import Optional, Callable

from tango.server import command
from ska.log_transactions import transaction

from .feature_toggle import FeatureToggle
from .tango_logging import log_transaction_id, get_logger

LOG = get_logger()
FEATURE_ALL_COMMANDS_HAVE_ARGUMENT = FeatureToggle(
    'all_commands_have_argument', True
)


def command_transaction(argdesc: Optional[str] = None):
    """
    Create a decorator for device command methods to add transaction
    processing.

    If called with the description of the argument, it creates a decorator that
    passes the transaction ID and the argument to the underlying method,
    otherwise the decorator passes only the transaction ID.

    :param argdesc: description of argument

    """
    def _decorator(command_method: Callable):

        # Define a wrapper that takes an optional string argument.

        @functools.wraps(command_method)
        def wrapper(self, params_json='{}'):
            name = command_method.__name__
            LOG.info('command %s device %s', name, type(self).__name__)
            params = json.loads(params_json)

            def do_command():
                if argdesc:
                    result = command_method(self, txn_id, params_json)
                else:
                    result = command_method(self, txn_id)
                return result

            # The idea here is to execute the command with a lock that will then
            # wait for notification from the event loop. Note that command
            # execution is actually in the main thread. Push events from the event
            # thread fail while a command is executing, so issue them afterwards.
            # FIXME: only commands that write to the db should lock.
            with transaction(name, params, logger=LOG) as txn_id:
                with log_transaction_id(txn_id):
                    self._in_command = True
                    ret = self._event_loop.do(do_command, name)
                    self._in_command = False
                    self.flush_event_queue()

            return ret

        # Use the Tango command function to create the command.

        if argdesc:
            # Create command with a string argument and use the supplied
            # description
            desc = f'JSON string containing {argdesc} and optional transaction ID'
            command_wrapped = command(f=wrapper, dtype_in=str, doc_in=desc)
        elif FEATURE_ALL_COMMANDS_HAVE_ARGUMENT.is_active():
            # Create command with a string argument and a generic description
            desc = 'JSON string containing optional transaction ID'
            command_wrapped = command(f=wrapper, dtype_in=str, doc_in=desc)
        else:
            # Create command with no argument for backwards compatibility
            command_wrapped = command(f=wrapper, dtype_in=None)

        return command_wrapped

    return _decorator
