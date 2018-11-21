import os
import uuid
import click

from roger import Orchestrator, TrainingInstance, User, Saveable

"""
roger init --credential
    - returns training instance uuid
    - stores it to local directory

roger status
    - provides known resources

roger list resource
    - returns active credentials

roger upload --data
    -

roger deploy --train-zip

roger train

"""

FOLDER_NAME = ".roger"
orchestrator, training_instance = None, None


@click.group()
def cli():
    Saveable.directory = FOLDER_NAME


@cli.command()
def init():
    try:
        os.mkdir(FOLDER_NAME)
    except FileExistsError:
        click.echo(
            "It looks like roger has already been initialized in this project. "
            "('{}' folder already exists)".format(FOLDER_NAME)
        )
        return

    new_user = Orchestrator.register_user()
    new_user.save(directory=FOLDER_NAME)
    click.echo("Project initialized.")


@cli.command()
def create():
    """
    Creates a TrainingInstance
    """
    user = User()
    user.load(directory=FOLDER_NAME)
    new_training_instance_uuid = Orchestrator.register_training_instance()
    training_instance = TrainingInstance(uuid=new_training_instance_uuid, user=user)
    training_instance.save(directory=FOLDER_NAME)
    click.echo("Training Instance ({}) created.".format(training_instance.uuid))


@cli.command()
def status():
    click.echo("roger status")


@cli.command()
def list():
    click.echo("roger list")


@cli.command()
def upload():
    click.echo("roger upload")


@cli.command()
def deploy():
    click.echo("roger deploy")


@cli.command()
def train():
    click.echo("roger train")


def init():
    pass


if __name__ == "__main__":
    cli()
