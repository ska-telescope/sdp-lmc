"""Subarray command validation and parsing."""

import os
import json
import logging

import jsonschema
import ska_sdp_config

from ska_telmodel.schema import validate
from ska_telmodel.sdp.version import SDP_ASSIGNRES, SDP_CONFIG
from .exceptions import raise_command_failed
from .tango_logging import get_logger

MSG_VALIDATION_FAILED = "Configuration validation failed"
LOG = get_logger()
SCHEMA_VERSION = "0.2"


def validate_assign_resources(config_str):
    """Validate AssignResources command configuration.

    :param config_str: configuration string in dict format
    :returns: SBI and list of processing blocks

    """

    # Validate the configuration string against the JSON schema
    schema_uri = SDP_ASSIGNRES + SCHEMA_VERSION
    config = validate_json_config(config_str, schema_uri=schema_uri)

    if config is None:
        # Validation has failed, so raise an error
        raise_command_failed(MSG_VALIDATION_FAILED, __name__)

    # Parse the configuration to get the SBI and PBs
    sbi, pbs = _parse_sbi_and_pbs(config)

    return sbi, pbs


def _parse_sbi_and_pbs(config):
    """Parse the configuration to get the SBI and PBs.

    :param config: configuration data
    :returns: SBI and list of PBs

    """
    # Create scheduling block instance

    sbi_id = config.get("id")

    sbi = {
        "id": sbi_id,
        "subarray_id": None,
        "scan_types": config.get("scan_types"),
        "pb_realtime": [],
        "pb_batch": [],
        "pb_receive_addresses": None,
        "current_scan_type": None,
        "scan_id": None,
        "status": "ACTIVE",
    }

    # Loop over the processing block configurations

    pbs = []

    for pbc in config.get("processing_blocks"):

        pb_id = pbc.get("id")
        LOG.info("Parsing processing block %s", pb_id)

        # Get type of workflow and add the processing block ID to the
        # appropriate list.
        workflow = pbc.get("workflow")
        wf_type = workflow.get("type")
        if wf_type == "realtime":
            sbi["pb_realtime"].append(pb_id)
        elif wf_type == "batch":
            sbi["pb_batch"].append(pb_id)
        else:
            LOG.error("Unknown workflow type: %s", wf_type)

        parameters = pbc.get("parameters")

        dependencies = []
        if "dependencies" in pbc:
            if wf_type == "realtime":
                LOG.error(
                    "dependencies attribute must not appear in "
                    "real-time processing block configuration"
                )
            if wf_type == "batch":
                dependencies = pbc.get("dependencies")

        # Add processing block to list
        pbs.append(
            ska_sdp_config.ProcessingBlock(
                pb_id,
                sbi_id,
                workflow,
                parameters=parameters,
                dependencies=dependencies,
            )
        )

    return sbi, pbs


def validate_configure(config_str):
    """Validate Configure command configuration.

    :param config_str: configuration string
    :returns: update to be applied to SBI

    """

    # Validate the configuration string against the JSON schema
    schema_uri = SDP_CONFIG + SCHEMA_VERSION
    config = validate_json_config(config_str, schema_uri=schema_uri)

    if config is None:
        # Validation has failed, so raise an error
        raise_command_failed(MSG_VALIDATION_FAILED, __name__)

    new_scan_types = config.get("new_scan_types")
    scan_type = config.get("scan_type")

    return new_scan_types, scan_type


def validate_scan(config_str):
    """Validate Scan command configuration.

    :param config_str: configuration string
    :returns: update to be applied to SBI

    """
    # Validate the configuration string against the JSON schema
    config = validate_json_config(config_str, schema_filename="scan.json")

    if config is None:
        # Validation has failed, so raise an error
        raise_command_failed(MSG_VALIDATION_FAILED, __name__)

    scan_id = config.get("id")

    return scan_id


def validate_json_config(config_str, schema_uri=None, schema_filename=None):
    """
    Validate a JSON configuration against a schema.

    :param config_str: JSON configuration string
    :param schema_uri: Default schema from telescope model
    :param schema_filename: name of schema file in the 'schema'
            sub-directory
    :returns: validated configuration (as dict/list), or None if
        validation fails

    """

    config = None
    try:
        config = json.loads(config_str)
        if schema_filename is None:
            if "interface" in config.keys():
                schema = config["interface"]
                LOG.debug("Validating JSON configuration against schema %s", schema)
                validate(schema, config, 1)
            else:
                LOG.debug("Validating JSON configuration against schema %s", schema_uri)
                validate(schema_uri, config, 1)
        else:
            LOG.debug(
                "Validating JSON configuration against schema %s", schema_filename
            )
            schema_path = os.path.join(
                os.path.dirname(__file__), "schema", schema_filename
            )
            with open(schema_path, "r") as file:
                schema = json.load(file)
            jsonschema.validate(config, schema)
    except json.JSONDecodeError as error:
        LOG.error("Unable to decode configuration string as JSON: %s", error.msg)
        config = None
    except jsonschema.ValidationError as error:
        LOG.error("Unable to validate JSON configuration: %s", error.message)
        config = None
    except ValueError as error:
        LOG.error("Unable to validate JSON configuration: %s", str(error))
        config = None

    if config is not None:
        LOG.debug("Successfully validated JSON configuration")

    return config
