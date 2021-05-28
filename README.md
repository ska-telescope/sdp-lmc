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

## Contribute to this repository

We use [Black](https://github.com/psf/black) to keep the python code style in
good shape. Please make sure you have formatted your code with Black before
merging to master.

The linting job in the CI pipeline checks that the code complies with Black
formatting, and will fail if that is not the case.

## Releasing the Docker Image

When new release is ready:

  - check out master
  - update CHANGELOG.md
  - commit changes
  - make release-[patch||minor||major]

Note: bumpver needs to be installed
