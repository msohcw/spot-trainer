import configparser
from haikunator import Haikunator
import boto3 as boto

# Haikunator builds two word random names
hkn = Haikunator()
def build_name(token_length=0):
    return hkn.haikunate(token_length=token_length)

"""
There are two overriding values, DEFAULT and CURRENT.
New Value > Current > Default
"""

DEFAULT = {
    # Ubuntu Deep Learning AMI
    'ImageId': 'ami-c47c28bc',
    # TODO change after testing to a GPU instance
    'InstanceType': 't2.micro',
    'InstanceName': build_name(),
    'S3Bucket': build_name(token_length=4)
    }

CURRENT = {
        'S3Bucket': 'dalmatian',
        'SubnetId': 'subnet-338dc669',
        'KeyName': 'ml-ec2-generic'
    }
