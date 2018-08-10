# We could really redo this with Docker more properly, but this will work for now

import os
import sys
from pathlib import Path
import zipfile
import boto3 as boto
from botocore.exceptions import ClientError

DEFAULT_INSTANCE_NAME = "amazing-artichoke"
DEFAULT_BUCKET = "dalmatian"
BASE_DIR = os.environ.get("BASE_DIR", os.getcwd() + "/build")
INSTANCE_NAME = os.environ.get("DALMATIAN_INSTANCE", DEFAULT_INSTANCE_NAME)
PACKAGE_KEY = "packages/{}.zip".format(INSTANCE_NAME)
PACKAGE_LOCAL_LOCATION = "{}/package.zip".format(BASE_DIR)
# TODO I'm not sure how best to do imports of a python script in a subfolder, e.g. a
# build folder, so I have temporarily made the build folder and the run_script folder
# the same, i.e. home.
BUILD_DIR = BASE_DIR


def terminate():
    # TODO terminate the spot instance here as well
    sys.exit()


def log(msg):
    print(msg)


# Create the build directory (Commented out until I have a better way of doing this.)
# See above.
# build_dir = Path(BUILD_DIR)
# build_dir.mkdir(parents=True, exist_ok=True)

# Check that the package exists, download it if necessary
s3 = boto.resource("s3")
package = Path(PACKAGE_LOCAL_LOCATION)
if not package.is_file():
    try:
        s3.Object(DEFAULT_BUCKET, PACKAGE_KEY).download_file(PACKAGE_LOCAL_LOCATION)
    except ClientError as e:
        if "Not Found" in repr(e):
            log(
                "Package for {} not found. Are you sure it exists?".format(
                    INSTANCE_NAME
                )
            )
            terminate()

    # TODO There is an edge case here if the operation is not atomic and gets killed
    # between downloading the zip and unzipping it. This needs to somehow be made an
    # atomic transaction that can be rolled back if necessary.

    # Safely unzip the package into the build directory
    package_zip = zipfile.ZipFile(PACKAGE_LOCAL_LOCATION)
    # TODO verify that zipfile >= 2.7.4 does safe extraction below
    package_zip.extractall(BUILD_DIR)

# Apply data validation checks
# At present, none.

# Run the package
import main

# Terminate this instance
