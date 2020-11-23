"""Config DB related tasks for SDP devices."""

import logging

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
