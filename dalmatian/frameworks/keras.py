from tensorflow.keras.callbacks import Callback

DALMATIAN_NAMESPACE = "dalmatian-internal"
EPOCH_KEY = "-".join((DALMATIAN_NAMESPACE, "keras-epoch"))
MODEL_KEY = "-".join((DALMATIAN_NAMESPACE, "keras-model-weights"))
OPTIMIZER_KEY = "-".join((DALMATIAN_NAMESPACE, "keras-optimizer-weights"))


class Checkpoint(Callback):
    def __init__(self, instance):
        self.instance = instance
        super().__init__()

    def on_epoch_end(self, epoch, logs=None):
        state_parameters = self.instance.state["parameters"]
        state_parameters[EPOCH_KEY] = epoch
        state_parameters[MODEL_KEY] = self.model.get_weights()
        state_parameters[OPTIMIZER_KEY] = self.model.optimizer.get_weights()
        self.instance.save()


def load_weights(stored_state, model):
    if MODEL_KEY in stored_state and model:
        model.set_weights(stored_state[MODEL_KEY])
        if OPTIMIZER_KEY in stored_state and model.optimizer:
            model._make_train_function()  # needed to initialize the optimizer
            model.optimizer.set_weights(stored_state[OPTIMIZER_KEY])


def load_initial_epoch(stored_state):
    if EPOCH_KEY in stored_state:
        return stored_state[EPOCH_KEY] + 1
    else:
        return 0
