from .celery_app import celeryApp
import logging
import copy
import os

from a2ml.api.utils.context import Context
from auger.api.cloud.rest_api import RestApi
from a2ml.api.a2ml import A2ML


def create_context(params, new_project=False):
    # TODO:path to config files
    project_path = os.path.join(
        os.environ.get('A2ML_PROJECT_PATH'), params.get('project_name'))

    providers_info = {
        "auger" :{
            'organization' : os.environ.get('AUGER_ORGANIZATION'),
            'api_url' : os.environ.get('HUB_APP_URL'),
            'token' : os.environ.get('AUGER_PROJECT_API_TOKEN')
        }
    }
    ctx = Context(path=project_path, debug = params.get("debug_log", False),
        providers_info = providers_info)

    ctx.setup_logger(format='')

    if not new_project:
        if params.get("provider"):
            ctx.config.set('config', 'providers', [params.get("provider")])

        if params.get("source_path"):
            ctx.config.set('config', 'source', params.get("source_path"))

    return ctx    
    # ctx.config['config'].write()

    # return Context(path=project_path, debug = params.get("debug_log", False),
    #     providers_info = providers_info)


def execute_tasks(tasks_func, params):
    if os.environ.get('TEST_CALL_CELERY_TASKS', True):
        return tasks_func(params)
    else:
        raise Exception("Not implemented.")


@celeryApp.task()
def new_project_task(params):
    from a2ml.cmdl.commands.cmd_new import NewCmd

    ctx = create_context(params, new_project = True)        

    NewCmd(ctx, params.get('project_name'), params.get('providers'),
        params.get('target'), params.get("source_path"), 
        params.get("model_type")).create_project()

@celeryApp.task()
def import_data_task(params):
    ctx = create_context(params)        

    return A2ML(ctx).import_data()
