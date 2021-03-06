from pprint import pprint
from collections import OrderedDict
import configparser
from haikunator import Haikunator
import boto3 as boto

# Haikunator builds two word random names
hkn = Haikunator()
def build_name(token_length=0):
    return hkn.haikunate(token_length=token_length)

DEFAULT_CONFIG_FILENAME = 'default_config.ini'
CONFIG_FILENAME = 'config.ini'

# Dynamic defaults are created here
DEFAULT = {
    'InstanceName': build_name(),
    'S3Bucket': build_name(token_length=4)
    }

# AWS interface used for validating config
ec2 = boto.resource('ec2')

def build_config():

    print()
    print("###############################")
    print("### Dalmatian Configuration ###")
    print("###############################")
    dalmatian = OrderedDict()
    ask(dalmatian, 'S3Bucket', 'S3 Bucket')
    ask(dalmatian, 'InstanceName', 'Instance Name')

    print("###############################")
    print("###   Roger Configuration   ###")
    print("###############################")
    roger = OrderedDict()
    ask(roger, 'ImageId', 'Instance AMI', info={
        'ami-c47c28bc': 'Ubuntu Deep Learning AMI'
        },
        validate=validate_ami)
    ask(roger, 'InstanceType', 'Instance Type', validate=validate_instance_type)
    ask(roger, 'SubnetId', 'Subnet ID')
    ask(roger, 'KeyName', 'Key Pair Name')

    print()
    print("###############################")
    print("###   Final Configuration   ###")
    print("###############################")
    config = OrderedDict()
    config['dalmatian'] = dalmatian
    config['roger'] = roger
    pprint({'dalmatian': dict(dalmatian),
            'roger': dict(roger)})
    return config

def ask(section, key, item, info=None, validate=lambda x: True):
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

        # There are two overriding values, DEFAULT and CURRENT.
        # New Value > Current > Default
        final_value = (user_specified
                        or CURRENT.get(key, None)
                        or DEFAULT.get(key, None))

        if not final_value:
            print("A non-empty value is required.")
        elif not validate(final_value):
            continue
        else:
            section[key] = final_value
            break

def validator(test):
    def validate(value):
        try:
            return test(value)
        except Exception as e:
            print("Validation failed: {}".format(str(e)))
            return False
    return validate

@validator
def validate_ami(ami):
    image = ec2.Image(ami)
    if image.name: return True

@validator
def validate_instance_type(instance_type):
    # boto3 does not actually provide a way of listing all the valid instance
    # types on AWS.
    # TODO fill out this list with all the instance types
    INSTANCE_TYPES = [
            't2.micro',
            'p2.xlarge',
            'p2.8xlarge',
            'p2.16xlarge'
            ]
    if instance_type in INSTANCE_TYPES: return True
    raise Exception("Invalid instance type")

if __name__ == '__main__':
    config = configparser.ConfigParser()
    # Override to prevent lowercasing of keys
    config.optionxform = lambda option: option

    # First load the defaults, then try and load the present configuration
    config_file = open(DEFAULT_CONFIG_FILENAME)
    try:
        config_file = open(CONFIG_FILENAME)
    except FileNotFoundError:
        pass

    config_dict = config.read_file(config_file)
    DEFAULT.update(config['default'])
    CURRENT = {**config['dalmatian'], **config['roger']}

    config_dict = build_config()
    config.read_dict(config_dict)

    with open(CONFIG_FILENAME, 'w') as config_file:
      config.write(config_file)
