import os
import uuid
import click

from roger import Orchestrator, TrainingInstance, User, Saveable, Session

"""
roger init --credential
    - returns training instance uuid
    - stores it to local directory

roger status
    - provides known resources

roger list resource
    - returns active credentials

roger use $TI_ID
    - changes active training instance

roger upload --data
    -

roger deploy --train-zip

roger train

"""

FOLDER_NAME = ".roger"
orchestrator, training_instance = None, None
Saveable.directory = FOLDER_NAME


@click.group()
@click.pass_context
def cli(ctx):
    if ctx.invoked_subcommand not in ("init",):
        try:
            ctx.obj = Session().load()
        except Exception:
            # TODO This is a FileNotFoundException right now, but should be made specific
            # in the Saveable class instead.
            raise click.UsageError("No session found. Have you called roger init?")


@cli.command()
def init():
    try:
        os.mkdir(FOLDER_NAME)
    except FileExistsError:
        raise click.UsageError(
            "It looks like roger has already been initialized in this project. "
            "('{}' folder already exists)".format(FOLDER_NAME)
        )

    new_user = Orchestrator.register_user().save()
    new_session = Session().save()

    click.echo("Project initialized.")


@cli.command()
@click.pass_obj
def create(session):
    """
    Creates a TrainingInstance
    """
    user = User().load()

    new_training_instance_uuid = Orchestrator.register_training_instance()
    training_instance = TrainingInstance(
        uuid=new_training_instance_uuid,
        user=user,
        create_storage_node=True,  # TODO remove this parameter
    )

    session.active_training_instance = training_instance

    training_instance.save()
    session.save()

    click.echo("Training Instance ({}) created.".format(training_instance.uuid))


@cli.command()
@click.argument("training_instance_id")
@click.pass_obj
def use(session, training_instance_id):
    session.active_training_instance = training_instance_id
    session.save()

    click.echo(
        "Now using Training Instance {}".format(session.active_training_instance.uuid)
    )


@cli.command()
@click.pass_obj
def status(session):
    click.echo(
        "Using Training Instance {}".format(session.active_training_instance.uuid)
    )
    if session.available_training_instances:
        click.echo("Available Training Instances:")
        for training_instance in session.available_training_instances:
            click.echo(training_instance.uuid)


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


if __name__ == "__main__":
    cli()
