import click

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

orchestrator, training_instance = None, None

@click.group()
def cli():
    pass

@cli.command()
def init():
    click.echo("roger init")

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

if __name__ == '__main__':
    cli()
