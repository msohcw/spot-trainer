import os
import boto3 as boto
import pickle
import copy

###### For testing ######
DEFAULT_INSTANCE_NAME = "amazing-artichoke"

#########################


instance = None
watch_set = {}


class Instance:
    def __init__(self, instance_name):
        self.name = instance_name
        self.s3_client = boto.client("s3")
        self.ec2_client = boto.client("ec2")

        s3 = boto.resource("s3")
        self.bucket = s3.Bucket("dalmatian")

        try:
            self.state = {"parameters": {}}
            self._initialize_storage()
            self.storage_initialized = True
        except Exception as e:
            _log("Failed to initialize storage")
            # TODO this needs to fail louder
            self.storage_initialized = False

    def _initialize_storage(self):
        _log("Initializing storage")
        self.state_name = "{}-state".format(self.name)

        # Check if data already exists
        state_keys = [
            state.key for state in self.bucket.objects.filter(Prefix=self.state_name)
        ]

        if self.state_name in state_keys:
            _log("Prior state found, loading state")
            self._safe_retry(self._get_state)
        else:  # we need to initialize the state object
            _log("Initializing remote state")
            self._safe_retry(self._put_state)

        _log("Initializing of storage complete")

    def _bytedata(self):
        return pickle.dumps(self.state)

    def _get_state(self):
        _log("Requesting state from S3")
        response = self.s3_client.get_object(
            Bucket=self.bucket.name, Key=self.state_name
        )

        status = response["ResponseMetadata"]["HTTPStatusCode"]
        if status != 200:
            _log("Request failed")
            return False

        stream = response["Body"]
        bytedata = stream.read()
        try:
            self.state = pickle.loads(bytedata)
        except ModuleNotFoundError as e:
            _log(e.msg)
            _log(
                "A module used to save the data is missing and the data cannot"
                " be loaded. Check if the required module is installed in your"
                " local environment."
            )
            raise e
        _log("Request succeeded")
        return True

    def _put_state(self):
        _log("Storing state into S3")
        response = self.s3_client.put_object(
            Bucket=self.bucket.name, Key=self.state_name, Body=self._bytedata()
        )

        status = response["ResponseMetadata"]["HTTPStatusCode"]
        if status != 200:
            _log("Storage failed")
            return False
        _log("Storage succeeded")
        return True

    def _erase_state(self):
        _log("Erasing state from S3")
        response = self.s3_client.delete_object(
            Bucket=self.bucket.name, Key=self.state_name
        )

        status = response["ResponseMetadata"]["HTTPStatusCode"]
        if status != 204:
            _log("Erasure failed")
            return False
        _log("Erasure succeeded")
        return True

    def _safe_retry(self, method):
        # TODO This method doesn't actually retry anything right now
        method()

    ### Public Interface ###

    def save(self):
        _log("Initializing save")
        self._safe_retry(self._put_state)
        _log("Save complete")

    def erase(self):
        self._safe_retry(self._erase_state)


def _log(message):
    print(message)


def _preflight_checks(storage=True):
    assert instance != None, "No instance found, have you run dalmatian.setup() yet?"
    if storage:
        assert (
            instance.storage_initialized
        ), "Storage not initialized. Retry dalmatian.setup()"


### Public Interface ###


def setup():
    global instance
    instance_name = os.environ.get("DALMATIAN_INSTANCE") or DEFAULT_INSTANCE_NAME
    _log("Beginning setup")
    instance = Instance(instance_name)
    _log("Setup complete")


def store_params(d):
    _preflight_checks()
    instance.state["parameters"].update(d)
    return get_params()


def store_param(key, value):
    store_params({key: value})


def get_params():
    _preflight_checks()
    return copy.deepcopy(instance.state["parameters"])


def get_param(key, default=None):
    return instance.state["parameters"].get(key, default)


class ImmutableObjectException(Exception):
    def __init__(self, item):
        self.type_name = type(item).__name__.capitalize()

    def __str__(self):
        return """ Immutable object given of type {}. This will not change and
                   not useful to watch. If you really need to store a constant,
                   use store_params instead. """.format(
            self.type_name
        )


def watch_param(key, value):
    _preflight_checks()
    if type(value) in (bool, int, float, tuple, str):
        raise ImmutableObjectException(value)
    else:
        watch_set[key] = value


def checkpoint():
    _preflight_checks()
    instance.save()


def wipe():
    # TODO This is a temporary way of handling the need to erase past training
    # cycles. Ideally, there should be a way to use S3 versioning to do this
    # instead. After that change, this should be a method of last-resort that
    # wipes all data.
    global instance
    _preflight_checks(storage=False)

    _log("Beginning wipe")
    instance.erase()
    instance = None
    _log("Wipe complete")


def terminate():
    # This is a stubbed method that could be used to do self-termination for
    # AWS spot instances triggered without an orchestrator
    pass
