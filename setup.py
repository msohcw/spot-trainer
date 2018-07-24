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

def build_config():

    print()
    print("###############################")
    print("### Dalmatian Configuration ###")
    print("###############################")
    dalmatian = {}
    ask(dalmatian, 'S3Bucket', 'S3 Bucket')
    ask(dalmatian, 'InstanceName', 'Instance Name')

    print("###############################")
    print("###   Roger Configuration   ###")
    print("###############################")
    roger = {}
    ask(roger, 'ImageId', 'Instance AMI', info={
        'ami-c47c28bc': 'Ubuntu Deep Learning AMI'
        })
    ask(roger, 'InstanceType', 'Instance Type')
    ask(roger, 'SubnetId', 'Subnet ID')
    ask(roger, 'KeyName', 'Key Pair Name')

    print()
    print("###############################")
    print("###   Final Configuration   ###")
    print("###############################")
    print(dalmatian)
    print(roger)

def ask(section, key, item, info=None):
    if info is None: info = {}
    for x in info.values():
        assert type(x) == str, "All given values should be strings"
    while True:
        appendix = []
        if key in CURRENT:
            appendix.append('current=' + CURRENT[key])
        if key in DEFAULT:
            appendix.append('default=' + DEFAULT[key])
        print("{}? {}".format(item, ', '.join(appendix)))
        if info:
            print("({})".format(
                ', '.join(': '.join(kv) for kv in info.items())))


        user_specified = input().strip()
        final_value = (user_specified
                        or CURRENT.get(key, None)
                        or DEFAULT.get(key, None))

        if not final_value:
            print("A non-empty value is required.")
        else:
            section[key] = final_value
            break

if __name__ == '__main__':
    build_config()
