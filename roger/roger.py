import sys
import os
import copy
import pathlib
import time
import datetime
import json
import uuid
from configparser import ConfigParser
import fabric
from fabric import Connection
import invoke
from invoke.watchers import StreamWatcher
import boto3 as boto
from botocore.exceptions import ClientError


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
        "Arn": "arn:aws:iam::686737240330:instance-profile/RogerInitatedInstance"
    },
}

PERMANENT_INSTANCE_PARAMETERS = copy.deepcopy(DEFAULT_INSTANCE_PARAMETERS)
PERMANENT_INSTANCE_PARAMETERS["InstanceType"] = "t2.micro"
PERMANENT_INSTANCE_PARAMETERS.pop("InstanceMarketOptions")


### TEMPORARY PARAMETERS ###
DEFAULT_SECURITY_GROUP = "us-west-2-default-sg"
DEFAULT_KEY_PAIR = pathlib.Path("~/.ssh/ml-ec2-generic.pem").expanduser().as_posix()
DEFAULT_BUCKET = "dalmatian"
DEFAULT_INSTANCE_NAME = "amazing-artichoke"

### Utils ###
def backoff_wait(predicate, update, backoff_max=30, backoff_step=5, initial=5):
    backoff = initial
    while not predicate():
        update(backoff=backoff)
        time.sleep(backoff)
        backoff = min(backoff_max, backoff + backoff_step)


def local_path(path):
    local_dir = os.path.dirname(__file__)
    return os.path.join(local_dir, path)


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
        self.ami_id = os.environ.get("AMI", None)

        self.snapshot_meta = {"name": "-".join((self.name, "snapshot"))}
        pass

    def spinup(self, *, package_path, data_path):
        self.load_data(data_path=data_path)
        self.load_package(package_path=package_path)
        self.build_run_script()
        self.build_userdata()
        self.load_instance()

    def load_package(self, *, package_path):
        # TODO fail loudly here when the package zip can't be found
        # TODO add package validation
        # TODO should we split this out somehow?
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
        if self.ami:
            instance_parameters["ImageId"] = self.ami_id

        verify()

        assert instance_parameters["MaxCount"] == 1
        assert instance_parameters["MinCount"] == 1
        self.instance = self.ec2.create_instances(**instance_parameters)[0]
        self.connect_to_instance()

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

    def load_data(self, *, data_path, remote=False):
        if not data_path:
            return

        if self.ami_id:
            log("Using AMI {}".format(self.ami_id))
            return

        def upload_callback(byte_count):
            log("{} bytes uploaded...".format(byte_count))

        log("Uploading data package to S3")
        self.bucket.upload_file(
            data_path,
            "data-packages/{}.zip".format(self.name),
            Callback=upload_callback,
        )
        log("Upload complete")

        instance_parameters = copy.deepcopy(PERMANENT_INSTANCE_PARAMETERS)
        instance_parameters["BlockDeviceMappings"] = [
            {
                "DeviceName": "/dev/sda1",
                "Ebs": {"VolumeSize": 80},  # TODO make this configurable
            }
        ]
        instance_parameters["SecurityGroupIds"] = self.security_group_ids

        roger_loc = os.path.dirname(os.path.realpath(__file__))

        snapshot_cc_loc = pathlib.Path(roger_loc, "snapshot-cloud-config")
        if not snapshot_cc_loc.is_file():
            log(
                "Could not find snapshot-cloud-config file. Looked at {}.".format(
                    cloud_config_loc
                )
            )
            raise Exception
        else:
            with open(snapshot_cc_loc) as snapshot_cc:
                snapshot_cc = snapshot_cc.read()
                snapshot_cc = snapshot_cc.format(data_package=self.name)
                instance_parameters["UserData"] = snapshot_cc

        log("Creating snapshot...")
        self.snapshot_instance = self.ec2.create_instances(**instance_parameters)[0]
        self.snapshot_instance.wait_until_running()

        # TODO insert a wait here to check for snapshot-ready file
        import pdb

        pdb.set_trace()

        # TODO verify before deleting previous snapshot
        matching_images = tuple(
            x
            for x in self.ec2.images.filter(
                Filters=[{"Name": "name", "Values": [self.snapshot_meta["name"]]}]
            )
        )
        for image in matching_images:
            # TODO check behaviour around EBS termination as a result
            if image.state == "available":
                image.deregister()

        # TODO how long to wait before creating image? how to check?
        self.ami = self.snapshot_instance.create_image(Name=self.snapshot_meta["name"])
        self.ami_id = self.ami.id
        log("Created AMI {} with data package".format(self.ami_id))

        # TODO Abstract away this internal AWS representation
        log("Waiting for AMI to exist")
        self.ami.wait_until_exists()

        ami_ready = lambda: self.ami.state != "pending"

        def update(**kwargs):
            log("Waiting for AMI to be available...")
            self.ami.reload()

        backoff_wait(ami_ready, update)

        if self.ami.state == "available":
            log("AMI available")
        elif self.ami.state == "failed":
            log("AMI failed to be created")
            # TODO better handling here
            return
        else:
            log("AMI in unhandled state")
            # TODO better handling here
            return

        self.snapshot_instance.terminate()
        log("Waiting for termination")
        self.snapshot_instance.wait_until_terminated()

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

    def _create_instance_connection(
        self, *, instance, key_pair, port=22, user="ubuntu"
    ):
        can_connect = lambda: self.instance.public_ip_address

        def update(**kwargs):
            self.instance.reload()
            log(
                "Waiting for {} seconds for instance IP address".format(
                    kwargs["backoff"]
                )
            )

        backoff_wait(can_connect, update)
        log("IP address obtained:", self.instance.public_ip_address)
        return Connection(
            host=public_ip,
            user=user,
            port=port,
            connect_kwargs={"key_filename": key_pair},
        )

    def connect_to_instance(self):
        self.connection = self._create_instance_connection(
            instance=self.instance, key_pair=DEFAULT_KEY_PAIR
        )
        self.connection.set_remote_interrupt(True)
        log("Waiting for instance to be in 'running' mode")
        self.instance.wait_until_running()

        def can_connect():
            try:
                self.connection.run('echo "Completed instance connection test"')
                return True
            except Exception:
                return False

        update = lambda **kwargs: log("Waiting for instance to respond")
        backoff_wait(can_connect, update)
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


def make_uuid(label):
    return "{}_{}".format(label, uuid.uuid4().hex)


class Saveable:
    directory = None

    @property
    def filename(self):
        raise NotImplementedError

    def save(self, *, directory=None):
        directory = directory or Saveable.directory

        filepath = os.path.join(directory, self.filename)

        dirname = os.path.dirname(filepath)
        os.makedirs(dirname, exist_ok=True)

        with open(filepath, "w") as file:
            file.write(json.dumps(self.encode()))

    def load(self, *, directory=None):
        directory = directory or Saveable.directory

        filepath = os.path.join(directory, self.filename)
        with open(filepath, "r") as file:
            self.decode(json.loads(file.read()))

        return self

    def encode(self):
        raise NotImplementedError

    def decode(self, data):
        raise NotImplementedError


class User(Saveable):
    iam = boto.resource("iam")

    """
    A User wraps around service credentials, e.g. AWS account ids and secret keys
    """

    def __init__(self):
        self.uuid = make_uuid("user")
        self.credentials = {}

    def encode(self):
        return self.credentials

    def decode(self, data):
        self.credentials = data

    @property
    def filename(self):
        return "user.json"

    @property
    def iam_user(self):
        try:
            user_name = self.credentials["user_name"]
        except KeyError:
            raise Exception("No credentials found, have you called `load_credentials`?")

        return User.iam.User(user_name)


class Session(Saveable):
    """
    Wraps around an active roger session

    - active training instance
    """

    def __init__(self):
        self.available_training_instances = set()
        self.active_training_instance = SentinelTrainingInstance()

    @property
    def filename(self):
        return "session.json"

    @property
    def active_training_instance(self):
        return self._active_training_instance

    @active_training_instance.setter
    def active_training_instance(self, ti):
        if isinstance(ti, str):
            if ti == SentinelTrainingInstance.uuid:
                self._active_training_instance = SentinelTrainingInstance()
            else:
                self._active_training_instance = TrainingInstance(
                    uuid=ti, user=None
                ).load()
        elif isinstance(ti, TrainingInstance):
            self._active_training_instance = ti
        else:
            raise Exception(
                "Tried to set active training instance to not a TrainingInstance or "
                "TrainingInstance id"
            )  # TODO make this informative

        if not isinstance(self._active_training_instance, SentinelTrainingInstance):
            self.available_training_instances.add(self._active_training_instance)

    def encode(self):
        available_training_instances = tuple(
            x.uuid for x in self.available_training_instances
        )
        return {
            "active_training_instance": self.active_training_instance.uuid,
            "available_training_instances": available_training_instances,
        }

    def decode(self, data):
        # TODO verify keys in data
        self.active_training_instance = data["active_training_instance"]
        self.available_training_instances = set(
            TrainingInstance(uuid=uuid, user=None).load()
            for uuid in data["available_training_instances"]
        )

    def __repr__(self):
        return "<Training Instance {}>".format(self.uuid)


class PermissionedResource:
    """
    A PermissionedResource is a wrapper around any AWS resource that requires
    appropriate IAM roles to access, e.g. an S3 bucket or an EC2 instance.

    This is an abstract class that expects certain methods to be overridden in the
    implementing class.

    """

    iam = boto.resource("iam")

    def __init__(self, training_instance):
        self.training_instance = training_instance
        self._permission_resource()

    def _permission_resource(self):
        policy = PermissionedResource.iam.create_policy(**self._policy_parameters())
        iam_user = self.training_instance.user.iam_user
        iam_user.attach_policy(PolicyArn=policy.arn)

    @staticmethod
    def _read_policy_file(policy_filename, mapping=None):
        with open(policy_filename, "r") as policy_file:
            policy_document = policy_file.read()

        mapping = mapping or {}
        for label, replacement in mapping.items():
            policy_document = policy_document.replace(label, replacement)

        try:
            policy_document = json.dumps(json.loads(policy_document))
        except json.decoder.JSONDecodeError as e:
            raise e

        return policy_document

    def _policy_parameters(self):
        raise NotImplementedError


class ComputeNode(PermissionedResource):
    """
    A wrapper around an EC2 instance.
    """

    def __init__(self):
        pass


class StorageNode(PermissionedResource):
    """
    A wrapper around an S3 Bucket.
    """

    def __init__(self, *, training_instance):
        super().__init__(training_instance)

    def _policy_parameters(self):
        uuid = self.training_instance.uuid
        return {
            "PolicyName": "{}-s3".format(uuid),
            "Path": "/{}/".format(uuid),
            "Description": "Grants S3 access to {}".format(uuid),
            "PolicyDocument": PermissionedResource._read_policy_file(
                # TODO verify access only to folder, and not bucket
                local_path("iam-templates/s3.json"),
                {"$TRAINING_INSTANCE_UUID": uuid},
            ),
        }


class Orchestrator:
    """
    The Orchestrator is the logical representation of the permissioned AWS profile. It
    can create buckets, instances and IAM profiles. One instance of an Orchestrator is
    built around one TrainingInstance.
    """

    iam = boto.resource("iam")

    def __init__(self, *, training_instance):
        self.training_instance = training_instance
        if not self._is_registered_training_instance():
            raise Exception

    @staticmethod
    def register_user():
        """
        Registers an AWS user that can be used for a specific project, that has the
        appropriate policies tied to it.
        """

        new_user = User()
        aws_user = Orchestrator.iam.create_user(UserName=new_user.uuid)
        access_key_pair = aws_user.create_access_key_pair()

        new_user.credentials = {
            "user_name": access_key_pair.user_name,
            "access_key_id": access_key_pair.id,
            "access_key_secret": access_key_pair.secret,
        }

        return new_user

    @staticmethod
    def register_training_instance():
        """
        Registers a training instance specific UUID
        """
        # TODO Human readable UUIDs
        # TODO Register UUID

        return make_uuid("ti")

    def _is_registered_training_instance(self):
        return True

    def create_storage_node(self):
        """
        Provisions an S3 folder for parameters and data
        Returns the appropriate permissions.
        """
        storage_node = StorageNode(training_instance=self.training_instance)

        # create S3 folder
        # create IAM policy
        # create IAM role


class TrainingInstance(Saveable):
    def __init__(self, *, uuid, user, create_storage_node=False):
        self.uuid = uuid
        self.user = user
        self.orchestrator = Orchestrator(training_instance=self)

        # TODO this should really query the Orchestrator to see if it needs to create
        # a new storage node or not
        if create_storage_node:
            self.orchestrator.create_storage_node()

    def upload(self):
        """ Uploads data to the tied storage node. """
        pass

    @staticmethod
    def list_all():
        pass

    @property
    def filename(self):
        return "training-instances/{}.json".format(self.uuid)

    def encode(self):
        return {"uuid": self.uuid, "owner": self.user.uuid}

    def decode(self, data):
        self.uuid = data["uuid"]
        # TODO what about user?


class SentinelTrainingInstance(TrainingInstance):
    uuid = "ti_sentinel"

    def __init__(self):
        pass

    # Does not save or load
    def save(self, *, directory=None):
        pass

    def load(self, *, directory=None):
        pass
