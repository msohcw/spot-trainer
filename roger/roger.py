import sys
import os
import copy
import pathlib
import time
import datetime
from configparser import ConfigParser
import fabric
from fabric import Connection
import invoke
from invoke.watchers import StreamWatcher
import boto3 as boto

### Monkey Patching for Invoke ###

"""
In the migration from Fabric 1 to Fabric 2, the option to send the interrupt
exclusively to the remote process (remote_interrupt) was not ported. This monkey
patch brings it back.

This hack seems to have some issues with KeyboardInterrupts when using an
interactive Python REPL.
"""

original_send_interrupt = fabric.runners.Remote.send_interrupt


def send_interrupt(self, interrupt):
    if not self.remote_interrupt:
        self.remote_interrupt = True
        raise interrupt
    else:
        original_send_interrupt(self, interrupt)


def set_remote_interrupt(self, value):
    self.config.runners["remote"].remote_interrupt = value


fabric.runners.Remote.send_interrupt = send_interrupt
fabric.Connection.set_remote_interrupt = set_remote_interrupt

##################################

DEFAULT_INSTANCE_PARAMETERS = {
    "ImageId": "ami-c47c28bc",
    "MinCount": 1,
    "MaxCount": 1,
    ### TEMPORARY PARAMETERS ###
    "InstanceType": "t2.micro",
    "SubnetId": "subnet-338dc669",
    "KeyName": "ml-ec2-generic",
    ############################
    "InstanceMarketOptions": {
        "MarketType": "spot",
        "SpotOptions": {
            "SpotInstanceType": "persistent",
            "ValidUntil": None,
            "MaxPrice": None,
            "InstanceInterruptionBehavior": "stop",
        },
    },
    "IamInstanceProfile": {
        "Arn": "arn:aws:iam::686737240330:instance-profile/RogerInitatedInstance",
    }
}

### TEMPORARY PARAMETERS ###
DEFAULT_SECURITY_GROUP = "us-west-2-default-sg"
DEFAULT_KEY_PAIR = pathlib.Path("~/.ssh/ml-ec2-generic.pem").expanduser().as_posix()
DEFAULT_BUCKET = "dalmatian"
DEFAULT_INSTANCE_NAME = "amazing-artichoke"


class Instance:
    def __init__(self):
        self.ec2 = boto.resource("ec2")
        self.s3 = boto.resource("s3")
        self.bucket = self.s3.Bucket(DEFAULT_BUCKET)
        self.security_group_ids = (
            self.ec2.security_groups.all()
            .filter(
                Filters=[{"Name": "group-name", "Values": (DEFAULT_SECURITY_GROUP,)}]
            )
            .limit(1)
        )
        self.security_group_ids = [x.id for x in self.security_group_ids]
        self.remote_code_path = "/home/ubuntu/code.py"
        self.remote_data_path = "/not/yet/implemented/data"
        self.conda_env = "pytorch_p36"
        self.name = os.environ.get("DALMATIAN_INSTANCE", DEFAULT_INSTANCE_NAME)
        pass

    def spinup(self, *, package_path, data_path):
        self.load_package(package_path=package_path)
        self.build_run_script()
        self.build_userdata()
        self.load_instance()
        # self.load_code(code_path=code_path, remote_path=self.remote_code_path)
        # self.load_data(data_path=data_path, remote_path=self.remote_data_path)
        # self.setup_instance()
        # self.run()

    def load_package(self, *, package_path):
        # TODO fail loudly here when the package zip can't be found
        # TODO add package validation
        self.bucket.upload_file(package_path, "packages/{}.zip".format(self.name))

    def build_run_script(self):
        pass

    def build_userdata(self):
        roger_loc = os.path.dirname(os.path.realpath(__file__))

        cloud_config_loc = pathlib.Path(roger_loc, "cloud-config")
        if not cloud_config_loc.is_file():
            log(
                "Could not find cloud-config file. Looked at {}.".format(
                    cloud_config_loc
                )
            )
            raise Exception
        else:
            with open(cloud_config_loc) as cloud_config:
                self.userdata = cloud_config.read()

        credentials_loc = pathlib.Path(roger_loc, "../secrets/dalmatian-client")
        config = ConfigParser()
        if not credentials_loc.is_file():
            log("Could not find AWS credentials. Looked at {}.".format(credentials_loc))
            raise Exception
        else:
            # TODO this is clearly not the best way of putting secrets in
            with open(credentials_loc) as credentials:
                config.read_file(credentials)
                self.userdata = self.userdata.format(
                    DALMATIAN_INSTANCE=self.name,
                    AWS_ACCESS_KEY_ID=config.get("default", "aws_access_key_id"),
                    AWS_SECRET_ACCESS_KEY=config.get(
                        "default", "aws_secret_access_key"
                    ),
                )

    def load_instance(self, *, days=3, max_price="0.0035", parameters={}):
        instance_parameters = copy.deepcopy(DEFAULT_INSTANCE_PARAMETERS)
        spot_options = instance_parameters["InstanceMarketOptions"]["SpotOptions"]
        spot_options["ValidUntil"] = days_from_now(days)
        spot_options["MaxPrice"] = max_price
        instance_parameters["SecurityGroupIds"] = self.security_group_ids
        instance_parameters.update(parameters)
        # UserData should always be as specified
        instance_parameters["UserData"] = self.userdata

        verify()

        assert instance_parameters["MaxCount"] == 1
        assert instance_parameters["MinCount"] == 1
        self.instance = self.ec2.create_instances(**instance_parameters)[0]
        self._connect_to_instance()

    def setup_instance(self):
        # HACK ~/.bashrc doesn't get run by Fabric commands so we need to copy
        # it manually to ~/.profile. TODO find a better way to do this
        log("Beginning instance setup")
        self.connection.run("cat ~/.bashrc | grep export >> ~/.profile")
        log("Instance setup complete")

    def load_code(self, *, code_path, remote_path, remote=False):
        if not code_path:
            return
        if not remote:
            self._load_local_code(code_path)

    def load_data(self, *, data_path, remote_path, remote=False):
        if not data_path:
            return

    def run(self):
        log("Initiating screen job")
        # This repeated prefixing is kinda hacky. TODO look into better ways of
        # getting persistent context/environment
        with self.connection.prefix("source ~/.profile"):
            with self.connection.prefix("source activate {}".format(self.conda_env)):
                self.connection.run(
                    "screen -dmL python -u {}".format(self.remote_code_path)
                )
        log("Screen job initiated")

    def listen(self):
        log("Listening to job output")
        self.connection.set_remote_interrupt(False)
        self.connection.run("screen -RR", pty=True)

    # Helpers

    def _connect_to_instance(self):
        MAX_WAIT, backoff = 30, 5
        while True:
            self.instance.reload()
            public_ip = self.instance.public_ip_address
            if public_ip:
                break
            log("Waiting for {} seconds for instance IP address".format(backoff))
            time.sleep(backoff)
            backoff = min(30, backoff + 5)
        log("IP address obtained:", public_ip)

        port = 22
        user = "ubuntu"
        self.connection = Connection(
            host=public_ip,
            user=user,
            port=port,
            connect_kwargs={"key_filename": DEFAULT_KEY_PAIR},
        )
        self.connection.set_remote_interrupt(True)
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


class LogReader(StreamWatcher):
    def __init__(self, file_path=None):
        pass

    def submit(self, stream):
        print(stream)
        return []


def verify():
    # stubbed method to do verification
    pass


def days_from_now(x):
    now = datetime.datetime.now()
    delta = datetime.timedelta(x)
    return now + delta


def log(*args):
    print(*args)
