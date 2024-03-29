"""Base configuration interface."""

import ska_sdp_config
from .feature_toggle import FeatureToggle
from .tango_logging import get_logger

FEATURE_CONFIG_DB = FeatureToggle("config_db", True)
LOG = get_logger()


def new_config_db_client():
    """Return a config DB object (factory function)."""
    backend = "etcd3" if FEATURE_CONFIG_DB.is_active() else "memory"
    LOG.info("Using config DB %s backend", backend)
    config_db_client = ska_sdp_config.Config(backend=backend)
    return config_db_client


class BaseConfig:
    """
    Base configuration interface.
    """

    def __init__(self):
        self._client = new_config_db_client()

    def txn(self):
        """
        Transaction loop.

        :returns: configuration transaction iterator

        """
        return self._client.txn()

    def watcher(self):
        """
        Watcher loop.

        :returns: configuration watcher iterator

        """
        return self._client.watcher()

    def close(self):
        """Close connection to configuration."""
        self._client.close()
