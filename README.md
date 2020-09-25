# SDP Local Monitoring and Control (Tango Devices)

This package contains the Tango device servers to control the SKA SDP.

Install with:

```bash
pip install -r requirements.txt
pip install .
```

If you have Tango set up locally, you can run the devices with:

```bash
SDPMaster <instance name> [-v4]
```

or:

```bash
SDPSubarray <instance name> [-v4]
```
