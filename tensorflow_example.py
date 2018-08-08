# Copyright 2015 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

"""A very simple MNIST classifier.
See extensive documentation at
http://tensorflow.org/tutorials/mnist/beginners/index.md
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import sys

from tensorflow.examples.tutorials.mnist import input_data

import tensorflow as tf

FLAGS = None


def main(_):
    # Import data
    mnist = input_data.read_data_sets(FLAGS.data_dir, one_hot=True)

    # Create the model
    x = tf.placeholder(tf.float32, [None, 784])

    W1 = tf.Variable(tf.truncated_normal([784, 10], stddev=0.1))
    b1 = tf.Variable(tf.zeros([10]))
    y1 = tf.nn.relu(tf.matmul(x, W1) + b1)

    W2 = tf.Variable(tf.truncated_normal([10, 10], stddev=0.1))
    b2 = tf.Variable(tf.zeros([10]))
    y2 = tf.matmul(y1, W2) + b2

    # Define loss and optimizer
    y_ = tf.placeholder(tf.float32, [None, 10])

    # The raw formulation of cross-entropy,
    #
    #   tf.reduce_mean(-tf.reduce_sum(y_ * tf.log(tf.nn.softmax(y)),
    #                                 reduction_indices=[1]))
    #
    # can be numerically unstable.
    #
    # So here we use tf.nn.softmax_cross_entropy_with_logits on the raw
    # outputs of 'y', and then average across the batch.
    cross_entropy = tf.reduce_mean(
        tf.nn.softmax_cross_entropy_with_logits(labels=y_, logits=y2)
    )

    # The learning rate here is deliberately low to obviously visualize the effect of
    # restoring weights from S3
    train_step = tf.train.GradientDescentOptimizer(0.01).minimize(cross_entropy)
    correct_prediction = tf.equal(tf.argmax(y2, 1), tf.argmax(y_, 1))
    accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))

    # Train
    from dalmatian import dalmatian as dalm
    import dalmatian.frameworks.tensorflow as tf_shim

    dalm.setup()
    stored_state = dalm.get_params()
    initial_epoch = stored_state.get('epoch', 0)
    checkpoint = tf_shim.Checkpoint(dalm.instance)

    sess = tf.Session()
    sess.run(tf.global_variables_initializer())
    checkpoint.restore(sess)
    
    for epoch in range(initial_epoch, 10000):
        batch_xs, batch_ys = mnist.train.next_batch(100)
        sess.run(train_step, feed_dict={x: batch_xs, y_: batch_ys})
        if epoch % 100 == 0:
            print(
                "Epoch:",
                epoch,
                "Train Accuracy:",
                sess.run(accuracy, feed_dict={x: batch_xs, y_: batch_ys}),
            )
            dalm.store_params({'epoch': epoch})
            dalm.checkpoint()
            checkpoint.save(sess)

    # Test trained model
    print(
        "Final Accuracy:",
        sess.run(accuracy, feed_dict={x: mnist.test.images, y_: mnist.test.labels}),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data_dir",
        type=str,
        default="/tmp/tensorflow/mnist/input_data",
        help="Directory for storing input data",
    )
    FLAGS, unparsed = parser.parse_known_args()
tf.app.run(main=main, argv=[sys.argv[0]] + unparsed)
