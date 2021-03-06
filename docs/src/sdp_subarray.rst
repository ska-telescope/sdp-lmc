SDP Subarray Device
===================

Introduction
------------

The SDP Subarray Tango device is the principal means by which processing is
initiated in SDP.


State Model
-----------

The present implementation is shown in the diagram below. Here the state is the
combination of the Tango device state and the observing state (obsState).

.. image:: images/sdp_subarray_states.svg
   :align: center


Behaviour
---------

The interaction between TMC (Telescope Manager Control) and the SDP Subarray
device is shown below. The SDP Subarray device receives commands from the TMC
SDP Subarray leaf node, and the consequent changes to the state of SDP are
reported in the device attributes.

.. image:: images/sdp_subarray_interaction_tango.svg
   :align: center


Interface
---------

Attributes
^^^^^^^^^^

================ ======= ========== =========================== ===========
Attribute        Type    Read/Write Values                      Description
================ ======= ========== =========================== ===========
version          String  Read       Semantic version            Subarray device server version
---------------- ------- ---------- --------------------------- -----------
obsState         Enum    Read       :ref:`subarray_obsstate`    Subarray observing state
---------------- ------- ---------- --------------------------- -----------
adminMode        Enum    Read-write :ref:`subarray_adminmode`   Subarray admin mode
---------------- ------- ---------- --------------------------- -----------
healthState      Enum    Read       :ref:`subarray_healthstate` Subarray health state
---------------- ------- ---------- --------------------------- -----------
receiveAddresses String  Read       JSON object                 Host addresses for receiving visibilities
---------------- ------- ---------- --------------------------- -----------
scanType         String  Read                                   Scan type, or 'null' if scan type is not configured
---------------- ------- ---------- --------------------------- -----------
scanID           Integer Read                                   Scan ID, or 0 if not scanning
================ ======= ========== =========================== ===========

.. _subarray_obsstate:

obsState values
"""""""""""""""

=============== ===========
obsState        Description
=============== ===========
EMPTY (0)       No receive and real-time processing resources are assigned to the subarray
--------------- -----------
RESOURCING (1)  Resources are being assigned or released
--------------- -----------
IDLE (2)        Receive and real-time processing resources are assigned to the subarray as specified in the Scheduling Block Instance
--------------- -----------
CONFIGURING (3) Scan type is being configured
--------------- -----------
READY (4)       Scan type is configured and the subarray is ready to scan
--------------- -----------
SCANNING (5)    Scanning
--------------- -----------
ABORTING (6)    Current activity is being aborted
--------------- -----------
ABORTED (7)     Most recent activity has been aborted
--------------- -----------
RESETTING (8)   Resetting to IDLE obsState
--------------- -----------
FAULT (9)       A fault has occurred in observing
--------------- -----------
RESTARTING (10) Restarting in EMPTY obsState
=============== ===========

.. _subarray_adminmode:

adminMode values
""""""""""""""""

=============== ===========
adminMode       Description
=============== ===========
OFFLINE (0)
--------------- -----------
ONLINE (1)
--------------- -----------
MAINTENANCE (2)
--------------- -----------
NOT_FITTED (3)
--------------- -----------
RESERVED (4)
=============== ===========

.. _subarray_healthstate:

healthState values
""""""""""""""""""

============ ===========
healthState  Description
============ ===========
OK (0)
------------ -----------
DEGRADED (1)
------------ -----------
FAILED (2)
------------ -----------
UNKNOWN (3)
============ ===========


Commands
^^^^^^^^

================ ============= =========== ======
Command          Argument type Return type Action
================ ============= =========== ======
On               None          None        Sets the device state to ON and obsState to EMPTY.
Off              None          None        Sets the device state to OFF.
AssignResources  String (JSON) None        :ref:`Assigns processing resources to the SBI. Sets obsState to IDLE <subarray_assign_resources>`.
ReleaseResources None          None        Releases all real-time processing in the SBI. Sets obsState to EMPTY.
Configure        String (JSON) None        :ref:`Configures scan type for the next scans. Sets obsState to READY <subarray_configure>`.
Scan             String (JSON) None        :ref:`Begins a scan of the configured type. Sets obsState to SCANNING <subarray_scan>`.
EndScan          None          None        Ends the scan. Sets obsState to READY.
End              None          None        Clears the scan type. Sets obsState to IDLE.
Abort            None          None        Aborts current activity. Sets obsState to ABORTED.
ObsReset         None          None        Resets to last known stable state. Sets obsState to IDLE.
Restart          None          None        Restarts the subarray device. Sets obsState to EMPTY.
================ ============= =========== ======

.. _subarray_assign_resources:

AssignResources command
"""""""""""""""""""""""

The argument of the AssignResources command is a JSON object describing the processing to be done
for the scheduling block instance (SBI). It contains a set of scan types and processing blocks.
The scan types contain information about the frequency channels output by CSP, which is important
for configuring the receive processes in SDP. The processing blocks define the workflows to be run
and the parameters to be passed to the workflows.

An example of the argument is below. Note that:

- ``max_length`` specifies the maximum length of the SBI in seconds.
- In ``scan_types``, the channel information is for example only.
- In ``processing_blocks``, the workflow parameters will not actually be empty. Each workflow will have its
  own schema for its parameters.

.. code-block:: json

    {
      "id": "sbi-mvp01-20200425-00000",
      "max_length": 21600.0,
      "scan_types": [
        {
          "id": "science",
          "channels": [
            {"count": 372, "start": 0, "stride": 2, "freq_min": 0.35e9, "freq_max": 0.358e9, "link_map": [[0,0], [200,1]]}
          ]
        },
        {
          "id": "calibration",
          "channels": [
            {"count": 372, "start": 0, "stride": 2, "freq_min": 0.35e9, "freq_max": 0.358e9, "link_map": [[0,0], [200,1]]}
          ]
        }
      ],
      "processing_blocks": [
        {
          "id": "pb-mvp01-20200425-00000",
          "workflow": {"type": "realtime", "id": "test_receive_addresses", "version": "0.3.2"},
          "parameters": {}
        },
        {
          "id": "pb-mvp01-20200425-00001",
          "workflow": {"type": "realtime", "id": "test_realtime", "version": "0.2.0"},
          "parameters": {}
        },
        {
          "id": "pb-mvp01-20200425-00002",
          "workflow": {"type": "batch", "id": "test_batch", "version": "0.2.0"},
          "parameters": {},
          "dependencies": [
            {"pb_id": "pb-mvp01-20200425-00000", "type": ["visibilities"]}
          ]
        },
        {
          "id": "pb-mvp01-20200425-00003",
          "workflow": {"type": "batch", "id": "test_batch", "version": "0.2.0"},
          "parameters": {},
          "dependencies": [
            {"pb_id": "pb-mvp01-20200425-00002", "type": ["calibration"]}
          ]
        }
      ]
    }


.. _subarray_configure:

Configure command
"""""""""""""""""

The argument of the Configure command is a JSON object specifying the scan type for the next scans.
``new_scan_types`` is optional, it is only present if a new scan type needs to be declared. This
would only happen for special SBIs (and underlying SDP workflows) meant to support dynamic
reconfiguration.

An example of the argument:

.. code-block:: json

    {
      "new_scan_types": [
        {
          "id": "new_calibration",
          "channels": [
            {"count": 372, "start": 0, "stride": 2, "freq_min": 0.35e9, "freq_max": 0.358e9, "link_map": [[0,0], [200,1]]}
          ]
        }
      ],
      "scan_type": "new_calibration"
    }


.. _subarray_scan:

Scan command
""""""""""""

The argument of the Scan command is a JSON object which specifies the scan ID.

An example of the argument:

.. code-block:: json

    {
      "id": 1
    }

Python API
----------

.. autoclass:: ska_sdp_lmc.SDPSubarray
   :members:
   :undoc-members:
