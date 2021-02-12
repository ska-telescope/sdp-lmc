"""Config DB related tasks for SDP devices."""

import logging
import threading

import ska_sdp_config
from .feature_toggle import FeatureToggle

FEATURE_CONFIG_DB = FeatureToggle('config_db', True)
LOG = logging.getLogger('ska_sdp_lmc')


def new_config_db_client():
    """Return a config DB object (factory function)."""
    backend = 'etcd3' if FEATURE_CONFIG_DB.is_active() else 'memory'
    LOG.info("Using config DB %s backend", backend)
    config_db_client = ska_sdp_config.Config(backend=backend)
    return config_db_client


class ThreadsafeIter:
    """Takes an iterator/generator and makes it thread-safe by
    serializing call to the `next` method of given iterator/generator.
    """
    def __init__(self, it):
        self.it = it
        self.lock = threading.Lock()

    def __iter__(self):
        return self

    def __next__(self):
        with self.lock:
            return next(self.it)

    def close(self):
        with self.lock:
            self.it.close()


class BaseConfig:
    """
    Base configuration interface.
    """

    def __init__(self):
        self._client = new_config_db_client()
        self._watcher = None

    def txn(self):
        """
        Transaction loop.

        :returns: configuration transaction iterator

        """
        return self._client.txn()

    def watcher(self):
        """
        Get a watcher.

        :returns: configuration watcher

        """
        return self._client.watcher()
        #self._watcher = ThreadsafeIter(self._client.watcher())
        #return self._watcher

    def stop_watcher(self):
        if self._watcher is not None:
            self._watcher.close()
