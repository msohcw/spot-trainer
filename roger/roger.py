import copy
import os
import pathlib
import time
import datetime
import fabric
from fabric import Connection
import invoke
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

    def setup_instance(self):
        # HACK ~/.bashrc doesn't get run by Fabric commands so we need to copy
        # it manually to ~/.profile. TODO find a better way to do this
        log("Beginning instance setup")
        self.connection.run('cat ~/.bashrc | grep export >> ~/.profile')
        log("Instance setup complete")

    def load_code(self, *, code_path, remote_path, remote=False):
        if not code_path: return
        if not remote:
            self._load_local_code(code_path)

    def load_data(self, *, data_path, remote_path, remote=False):
        if not data_path: return

    # Helpers

    def _connect_to_instance(self):
        MAX_WAIT, backoff = 30, 5
        while True:
            self.instance.reload()
            public_ip = self.instance.public_ip_address
            if public_ip: break
            log("Waiting for {} seconds for instance IP address".format(backoff))
            time.sleep(backoff)
            backoff = min(30, backoff + 5)
        log("IP address obtained:", public_ip)

        port = 22
        user = 'ubuntu'
        self.connection = Connection(host=public_ip,
                                     user=user,
                                     port=port,
                                     connect_kwargs={
                                         'key_filename': DEFAULT_KEY_PAIR
                                         }
                                     )
        log("Waiting for instance to be in 'running' mode")
        self.instance.wait_until_running()
        while True:
            try:
                self.connection.run('echo "Completed instance connection test"')
            except Exception:
                log("Waiting for instance to respond")
                time.sleep(5)
                continue
            break
        log("Instance is now in 'running' mode")

    def _load_local_code(self, code_path):
        abs_path = pathlib.Path(code_path).resolve()
        verify()
        log("Loading code onto instance")
        self.connection.put(str(abs_path), remote=self.remote_code_path)
        log("Loading code complete")

def verify():
    # stubbed method to do verification
    pass

def days_from_now(x):
    now = datetime.datetime.now()
    delta = datetime.timedelta(x)
    return now + delta

def log(*args):
    print(*args)
