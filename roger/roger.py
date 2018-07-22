import copy
import datetime
import fabric
import boto3 as boto

DEFAULT_INSTANCE_PARAMETERS = {
    'ImageId': 'ami-c47c28bc',
    'MinCount': 1,
    'MaxCount': 1,
    ### TEMPORARY PARAMETERS ###
    'InstanceType': 't2.micro',
    'SubnetId': 'subnet-338dc669',
    'KeyName': 'ml-ec2-generic',
    ############################
    'InstanceMarketOptions': {
        'MarketType': 'spot',
        'SpotOptions': {
            'SpotInstanceType': 'persistent',
            'ValidUntil': None,
            'MaxPrice': None,
            'InstanceInterruptionBehavior': 'stop'
            }
        }
}

DEFAULT_SECURITY_GROUP = 'us-west-2-default-sg'
DEFAULT_KEY_PAIR = (pathlib.Path('~/.ssh/ml-ec2-generic.pem')
                        .expanduser().as_posix())

class Instance:
    def __init__(self):
        self.ec2 = boto.resource('ec2')
        self.security_group_ids = self.ec2.security_groups.all().filter(
                Filters=[{'Name': 'group-name',
                          'Values': (DEFAULT_SECURITY_GROUP,)}]).limit(1)
        self.security_group_ids = [x.id for x in self.security_group_ids]
        pass

    def spinup(self, *, code_path, data_path):
        pass

    def load_instance(self, *, days=3, max_price ='0.0035', parameters={}):
        instance_parameters = copy.deepcopy(DEFAULT_INSTANCE_PARAMETERS)
        spot_options = instance_parameters['InstanceMarketOptions']['SpotOptions']
        spot_options['ValidUntil'] = days_from_now(days)
        spot_options['MaxPrice'] = max_price
        instance_parameters['SecurityGroupIds'] = self.security_group_ids
        instance_parameters.update(parameters)

        verify()

        assert instance_parameters['MaxCount'] == 1
        assert instance_parameters['MinCount'] == 1
        self.instance = self.ec2.create_instances(**instance_parameters)[0]
        self._connect_to_instance()


    def load_code(self, *, code_path, remote_path, remote=False):
        pass

    def load_data(self, *, data_path, remote_path, remote=False):
        pass

    # Helpers


def verify():
    # stubbed method to do verification
    pass

def days_from_now(x):
    now = datetime.datetime.now()
    delta = datetime.timedelta(x)
    return now + delta

def log(*args):
    print(*args)
