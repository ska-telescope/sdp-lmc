"""Subarray command validation and parsing."""

import json
import logging

import ska_sdp_config

from ska_telmodel.schema import validate
from ska_telmodel.sdp.version import (
    SDP_ASSIGNRES_PREFIX,
    SDP_CONFIGURE_PREFIX,
    SDP_SCAN_PREFIX,
    check_sdp_interface_version,
)
from .exceptions import raise_command_failed

LOG = logging.getLogger("ska_sdp_lmc")

MSG_VALIDATION_FAILED = "Configuration validation failed"

SCHEMA_VERSION_0_2 = "0.2"
SCHEMA_VERSION_0_3 = "0.3"
SCHEMA_VERSION_DEFAULT = SCHEMA_VERSION_0_2
SCHEMA_VERSION_ALLOWED = (SCHEMA_VERSION_0_2, SCHEMA_VERSION_0_3)


def validate_assign_resources(config_str):
    """
    Validate AssignResources command configuration.

    :param config_str: configuration string in dict format
    :returns: SBI and list of processing blocks

    """
    version, config = validate_json_config(
        config_str,
        SDP_ASSIGNRES_PREFIX,
        SCHEMA_VERSION_DEFAULT,
        SCHEMA_VERSION_ALLOWED,
    )

    if config is None:
        # Validation has failed, so raise an error
        raise_command_failed(MSG_VALIDATION_FAILED, __name__)

    if version == SCHEMA_VERSION_0_2:
        # Convert keys to version 0.3
        config["eb_id"] = config.pop("id")

        for scan_type in config.get("scan_types"):
            scan_type["scan_type_id"] = scan_type.pop("id")
            if "coordinate_system" in scan_type:
                scan_type["reference_frame"] = scan_type.pop("coordinate_system")

        for pbc in config.get("processing_blocks"):
            pbc["pb_id"] = pbc.pop("id")
            workflow = pbc.get("workflow")
            workflow["kind"] = workflow.pop("type")
            workflow["name"] = workflow.pop("id")
            if "dependencies" in pbc:
                dependencies = pbc.get("dependencies")
                for dependency in dependencies:
                    dependency["kind"] = dependency.pop("type")

    # Parse the configuration to get the SBI and PBs
    sbi, pbs = _parse_sbi_and_pbs(config)

    return sbi, pbs


def _parse_sbi_and_pbs(config):
    """
    Parse the configuration to get the SBI and PBs.

    :param config: configuration data
    :returns: SBI and list of PBs

    """
    # Create scheduling block instance

    eb_id = config.get("eb_id")

    # Convert "scan_type_id" to "id"
    scan_types = config.get("scan_types")
    for scan_type in scan_types:
        scan_type["id"] = scan_type.pop("scan_type_id")

    sbi = {
        "id": eb_id,
        "subarray_id": None,
        "scan_types": scan_types,
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

        pb_id = pbc.get("pb_id")
        LOG.info("Parsing processing block %s", pb_id)

        # Get type of workflow and add the processing block ID to the
        # appropriate list.
        workflow = pbc.get("workflow")

        # Temporary - config DB currently doesn't support new schema
        workflow["type"] = workflow.pop("kind")
        workflow["id"] = workflow.pop("name")

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
                eb_id,
                workflow,
                parameters=parameters,
                dependencies=dependencies,
            )
        )

    return sbi, pbs


def validate_configure(config_str):
    """
    Validate Configure command configuration.

    :param config_str: configuration string
    :returns: update to be applied to SBI

    """
    # Validate the configuration string against the schema
    version, config = validate_json_config(
        config_str,
        SDP_CONFIGURE_PREFIX,
        SCHEMA_VERSION_DEFAULT,
        SCHEMA_VERSION_ALLOWED,
    )

    if config is None:
        # Validation has failed, so raise an error
        raise_command_failed(MSG_VALIDATION_FAILED, __name__)

    if version == SCHEMA_VERSION_0_2:
        # Convert the keys to version 0.3.
        new_scan_types = config.get("new_scan_types")
        if new_scan_types is not None:
            for new_scan_type in new_scan_types:
                new_scan_type["scan_type_id"] = new_scan_type.pop("id")
                if "coordinate_system" in new_scan_type:
                    new_scan_type["reference_frame"] = new_scan_type.pop(
                        "coordinate_system"
                    )

    new_scan_types = config.get("new_scan_types")
    scan_type = config.get("scan_type")

    # Convert "scan_type_id" to "id"
    if new_scan_types is not None:
        for new_scan_type in new_scan_types:
            new_scan_type["id"] = new_scan_type.pop("scan_type_id")

    return new_scan_types, scan_type


def validate_scan(config_str):
    """
    Validate Scan command configuration.

    :param config_str: configuration string
    :returns: update to be applied to SBI

    """
    # Validate the configuration string against the schema
    version, config = validate_json_config(
        config_str,
        SDP_SCAN_PREFIX,
        SCHEMA_VERSION_DEFAULT,
        SCHEMA_VERSION_ALLOWED,
    )

    if config is None:
        # Validation has failed, so raise an error
        raise_command_failed(MSG_VALIDATION_FAILED, __name__)

    if version == SCHEMA_VERSION_0_2:
        # Convert to version 0.3
        config["scan_id"] = config.pop("id")

    scan_id = config.get("scan_id")

    return scan_id


def validate_json_config(config_str, prefix, default, allowed):
    """
    Validate a JSON configuration string against a schema.

    :param config_str: JSON configuration string
    :param prefix: schema prefix
    :param default: default version of schema to validate against
    :param allowed: allowed versions of the schema
    :returns: version and validated configuration, or both are set to None if
        validation fails

    """
    try:
        config = json.loads(config_str)
        if "interface" in config:
            schema = config.get("interface")
        else:
            schema = prefix + default
        version = check_sdp_interface_version(schema, prefix)
        validate(schema, config, 1)
    except json.JSONDecodeError as error:
        LOG.error("Unable to decode configuration string as JSON: %s", error.msg)
        version, config = None, None
    except ValueError as error:
        LOG.error("Unable to validate JSON configuration: %s", str(error))
        version, config = None, None

    if version not in allowed:
        LOG.error("Schema version is not allowed: %s", version)
        version, config = None, None

    if config is not None:
        LOG.debug("Successfully validated JSON configuration")

    return version, config
