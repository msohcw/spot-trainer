import tensorflow as tf
from dalmatian import dalmatian as dalm
import dalmatian.frameworks.keras as keras_shim

mnist = tf.keras.datasets.mnist

(x_train, y_train),(x_test, y_test) = mnist.load_data()
x_train, x_test = x_train / 255.0, x_test / 255.0

model = tf.keras.models.Sequential([
  # This is an important quirk of using Tensorflow-backed Keras:
  # the input shape *must* be specified, otherwise compilation only occurs
  # when first run on training data (aka eager execution)
  tf.keras.layers.Flatten(input_shape = (28,28)),
  tf.keras.layers.Dense(512, activation=tf.nn.relu),
  tf.keras.layers.Dropout(0.2),
  tf.keras.layers.Dense(10, activation=tf.nn.softmax)
])
model.compile(optimizer='adam',
              loss='sparse_categorical_crossentropy',
              metrics=['accuracy'])

#### Dalmatian ####
dalm.setup() # Initialize dalmatian

# Load any existing state
stored_state = dalm.get_params()
initial_epoch = keras_shim.load_initial_epoch(stored_state)
keras_shim.load_weights(stored_state, model)

model.fit(x_train,
          y_train,
          initial_epoch=initial_epoch,
          epochs = 10,
          # We pass in a Checkpoint as a callback for keras. Checkpoint takes
          # the dalm.instance object as a parameter which it uses to update S3
          callbacks=[keras_shim.Checkpoint(dalm.instance)])
###################

model.evaluate(x_test, y_test)
