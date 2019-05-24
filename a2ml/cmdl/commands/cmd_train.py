import click

from a2ml.cmdl.utils.context import pass_context
from a2ml.api import gc_a2ml
# import yaml

class TrainCmd(object):

    def __init__(self, ctx):
        self.ctx = ctx

    def train(self):
        pass
        # config = yaml.safe_load(open("config.yaml"))
        # if config['provider'] == "GC":
        #     print("Project: {}".format(config['project']))
        #     model = gc_a2ml.GCModel(config['name'],config['project'],config['region'])
        #     model.train(config['dataset_id'],config['target'],config['exclude'].split(','),config['budget'],config['metric'])

@click.command('train', short_help='Train the model.')
@pass_context
def cmdl(ctx):
    """Train the model."""
    ctx.setup_logger(format='')
    TrainCmd(ctx).train()
