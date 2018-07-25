# Spot Trainer
This project was started to support members at MachineLearning@Berkeley to easily
train ML models on spot instances. It comprises two sub-libraries, `dalmatian`
and `roger`. `dalmatian` is designed to be integrated into training code. It
allows for easy save and resume of training, by saving in-memory data to S3.
`roger` allows for easy spin-up and management of spot instances for training,
 by creating AWS spot instances and loading code and data onto them.

# Installation and Setup
1) Setup a new IAM user on AWS with programmatic access
2) Ensure the IAM user has the appropriate permissions (see IAM user permissions)
3) Install the AWS CLI if you do not have it installed (`pip install awscli`)
4) Run `aws configure` and set the Access Key ID and Secret Access Key to match
   your created IAM user. Choose your default region (`us-west-2` is common) and
   set the default output format to `json`
5) Run `configure.py`
6) You should be all set! Read the sections on `dalmatian` and `roger` for
   library usage details.

# IAM user permissions
TODO: These are a work in progress

Both EC2 access and S3 access are required. If you are just testing, creating a
user with AmazonEC2FullAccess and AmazonS3FullAccess is an insecure but workable
solution.

We're still looking into a better way to build/define these permissions to be
exactly what is required for running `dalmatian` or `roger`.

# Dalmatian
TODO: View the code examples for now.

# Roger
TODO
