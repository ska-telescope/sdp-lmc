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

## Releasing the Docker Image

When new release is ready:

  - check out master
  - update CHANGELOG.md
  - commit changes
  - make release-[patch||minor||major]

Note: bumpver needs to be installed

