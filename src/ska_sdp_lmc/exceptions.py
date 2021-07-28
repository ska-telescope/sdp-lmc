"""Tango exceptions."""

import logging

from tango import Except, ErrSeverity

LOG = logging.getLogger("ska_sdp_lmc")


def raise_exception(reason, desc, origin, severity=ErrSeverity.ERR):
    """Raise a Tango DevFailed exception.

    :param reason: Reason for the error.
    :param desc: Error description.
    :param origin: Error origin.
    :param severity Error severity

    """
    LOG.error("Raising DevFailed exception...")
    LOG.error("Reason: %s", reason)
    LOG.error("Description: %s", desc)
    LOG.error("Origin: %s", origin)
    LOG.error("Severity: %s", severity)
    Except.throw_exception(reason, desc, origin, severity)


def raise_command_not_allowed(desc, origin):
    """Raise a command-not-allowed exception.

    :param desc: Error description.
    :param origin: Error origin.

    """
    raise_exception("API_CommandNotAllowed", desc, origin)


def raise_command_failed(desc, origin):
    """Raise a command-failed exception.

    :param desc: Error description.
    :param origin: Error origin.

    """
    raise_exception("API_CommandFailed", desc, origin)
