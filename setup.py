#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PIP setup script for the SKA SDP LMC package."""
# pylint: disable=exec-used

import os
import setuptools

RELEASE_INFO = {}
RELEASE_PATH = os.path.join("src", "ska_sdp_lmc", "release.py")
exec(open(RELEASE_PATH).read(), RELEASE_INFO)

with open("README.md", "r") as file:
    LONG_DESCRIPTION = file.read()

setuptools.setup(
    name=RELEASE_INFO["NAME"],
    version=RELEASE_INFO["VERSION"],
    description="SKA SDP Local Monitoring and Control (Tango devices)",
    author=RELEASE_INFO["AUTHOR"],
    license=RELEASE_INFO["LICENSE"],
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    url="https://gitlab.com/ska-telescope/sdp/ska-sdp-lmc",
    package_dir={"": "src"},
    packages=setuptools.find_packages("src"),
    package_data={"ska_sdp_lmc": ["schema/*.json"]},
    install_requires=[
        "pytango",
        "jsonschema",
        "lmcbaseclasses>=0.8",
        "ska-sdp-config>=0.2.1",
        "ska-logging>=0.3.0",
        "ska-telescope-model>=0.3.0",
    ],
    entry_points={
        "console_scripts": [
            "SDPMaster = ska_sdp_lmc.master:main",
            "SDPSubarray = ska_sdp_lmc.subarray:main",
        ]
    },
    setup_requires=["pytest-runner"],
    tests_require=[
        "pylint2junit",
        "pytest",
        "pytest-bdd",
        "pytest-cov",
        "pytest-pylint",
        "ska-telescope-model",
    ],
    dependency_links=[
        "https://nexus.engageska-portugal.pt/repository/pypi/simple/",
    ],
    zip_safe=False,
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Astronomy",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3 :: Only",
        "License :: OSI Approved :: BSD License",
    ],
)
