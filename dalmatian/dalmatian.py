import os
import boto3 as boto
import pickle
import copy

###### For testing ######
DEFAULT_INSTANCE_NAME = 'amazing-artichoke'

#########################


instance = None
s3 = boto.resource('s3')
bucket = s3.Bucket('dalmatian')
watch_set = {}

class Instance:
    def __init__(self, instance_name):
        self.name = instance_name
        self.s3_client = boto.client('s3')
        self.ec2_client = boto.client('ec2')
        self.state = {
            'parameters': {}
        }

        self._initialize_storage()

    def _initialize_storage(self):
        _log("Initializing storage")
        self.state_name = "{}-state".format(self.name)

        # Check if data already exists
        state_keys = [state.key for state in bucket.objects.filter(Prefix=self.state_name)]

        if self.state_name in state_keys:
            _log("Prior state found, loading state")
            self._safe_retry(self._get_state)
        else: # we need to initialize the state object
            _log("Initializing remote state")
            self._safe_retry(self._put_state)

        _log("Initializing of storage complete")

    def _bytedata(self):
        return pickle.dumps(self.state)

    def _get_state(self):
        _log("Requesting state from S3")
        response = self.s3_client.get_object(Bucket=bucket.name,
                                             Key=self.state_name)

        status = response['ResponseMetadata']['HTTPStatusCode']
        if status != 200:
            _log("Request failed")
            return False


        stream = response['Body']
        bytedata = stream.read()
        self.state = pickle.loads(bytedata)
        _log("Request succeeded")
        return True

    def _put_state(self):
        _log("Storing state into S3")
        response = self.s3_client.put_object(Bucket=bucket.name,
                                             Key=self.state_name,
                                             Body=self._bytedata())

        status = response['ResponseMetadata']['HTTPStatusCode']
        if status != 200: 
            _log("Storage failed")
            return False
        _log("Storage succeeded")
        return True

    def _safe_retry(self, method):
        # TODO This method doesn't actually retry anything right now
        method()

    ### Public Interface ###

    def save(self):
        _log("Initializing save")
        self._safe_retry(self._put_state)
        _log("Save complete")

def _log(message):
    print(message)

def _preflight_checks():
    assert instance != None, (
           "No instance found, have you run dalmatian.setup() yet?")

### Public Interface ###

def setup():
    global instance
    instance_name = (os.environ.get('DALMATIAN_INSTANCE')
                    or DEFAULT_INSTANCE_NAME)
    _log("Beginning setup")
    instance = Instance(instance_name)
    _log("Setup complete")

def store_params(d):
    _preflight_checks()
    instance.state['parameters'].update(d)
    return get_params()

def store_param(key, value):
    store_params({key: value})

def get_params():
    _preflight_checks()
    return copy.deepcopy(instance.state['parameters'])

def get_param(key, default=None):
    return instance.state['parameters'].get(key, default)

class ImmutableObjectException(Exception):
    def __init__(self, item):
        self.type_name = type(item).__name__.capitalize()

    def __str__(self):
        return """ Immutable object given of type {}. This will not change and
                   not useful to watch. If you really need to store a constant,
                   use store_params instead. """.format(self.type_name)

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
    pass
