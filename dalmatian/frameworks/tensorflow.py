from tensorflow.train import Saver
from tensorflow.python.framework.errors_impl import NotFoundError


class Checkpoint:
    def __init__(self, instance):
        self.instance = instance
        self.saver = Saver()
        self.s3_path = "s3://{}/{}-state-tensorflow/model.ckpt".format(
            instance.bucket.name, instance.name
        )

    def save(self, sess):
        self.saver.save(sess, self.s3_path)

    def restore(self, sess):
        # This is obviously a hacky way of making restore a no-op when we have nothing
        # to restore, but I am not certain right now of a better way of doing this
        try:
            self.saver.restore(sess, self.s3_path)
        except NotFoundError as e:
            if "Failed to find any matching files" in e.message:
                # There was nothing to restore
                return
            else:
                raise e
