from .celery_app import celeryApp
import copy

from a2ml.api.model_review.model_review import ModelReview
from a2ml.api.model_review.model_helper import ModelHelper
from a2ml.api.utils.context import Context
from a2ml.api.a2ml import A2ML

def _exception_message_with_all_causes(e):
    if isinstance(e, Exception) and e.__cause__:
        return str(e) + ' caused by ' + __exception_message_with_all_causes(e.__cause__)
    else:
        return str(e)

def process_task_result(status, retval, task_id, args, kwargs, einfo):
    #logging.info("process_task_result exception: %s"%(einfo))
    if args:
        params = args[0]

        if params and params.get('augerInfo', {}).get('cluster_task_id'):
            if isinstance(retval, Exception):
                retval = _exception_message_with_all_causes(retval)
                # newrelic.agent.record_exception(
                #     exc=retval,
                #     params={'status': status, 'task_id': task_id, 'args': args, 'kwargs': kwargs}
                # )

            #TODO: update cluster_task    
            # AugerMessenger(params).set_cluster_task_result(params['augerInfo']['cluster_task_id'],
            #     status, retval, str(einfo))

def _get_hub_experiment_session(experiment_session_id):
    from a2ml.api.auger.experiment import AugerExperiment
    from a2ml.api.auger.impl.cloud.experiment_session import AugerExperimentSessionApi

    ctx = Context(debug=True)
    #ctx.credentials = params.get('provider_info', {}).get('auger', {}).get('credentials')
    experiment = AugerExperiment(ctx)
    session_api = AugerExperimentSessionApi(ctx, session_id=experiment_session_id)
    return session_api.properties(), ctx

def _get_hub_project_file(project_file_id):
    from a2ml.api.auger.project import AugerProject
    from a2ml.api.auger.impl.cloud.project_file import AugerProjectFileApi

    ctx = Context(debug=True)
    project = AugerProject(ctx)
    project_file_api = AugerProjectFileApi(ctx, project_file_id=project_file_id)
    return project_file_api.properties(), ctx

def _make_hub_objects_update(ctx, provider):
    #project, project_file, experiment, experiment_session
    project_name = ctx.config.get("name", parts=ctx.config.parts_changes)
    project_file_dataset = ctx.config.get("dataset", parts=ctx.config.parts_changes)
    # project_file_validation_dataset = ctx.config.get("experiment/validation_dataset", parts=ctx.config.parts_changes)

    experiment_name = ctx.config.get('experiment/name', parts=ctx.config.parts_changes)
    experiment_session_id = ctx.config.get('experiment/run_id', parts=ctx.config.parts_changes)
    
    updates = {}
    if project_name:
        updates['project'] = {
            'provider_info': {provider: {'name': project_name}}
        }
    if project_file_dataset:
        updates['project_file'] = {
            'provider_info': {provider: {'url': project_file_dataset}}
        }
    # if project_file_validation_dataset:
    #     if updates.get('project_file'):
    #         updates['project_file']['provider_info'][provider] = {'validation_dataset': project_file_validation_dataset}
    #     else:    
    #         updates['project_file'] = {
    #             'provider_info': {provider: {'validation_dataset': project_file_validation_dataset}}
    #         }
    if experiment_name:
        updates['experiment'] = {
            'provider_info': {provider: {'name': experiment_name}}
        }
    if experiment_session_id:
        updates['experiment_session'] = {
            'provider_info': {provider: {'id': experiment_session_id}}
        }
                
    return updates

def _update_hub_objects(ctx, provider, ctx_hub, params):
    hub_objects_update = _make_hub_objects_update(ctx, params.get('provider'))
    print(hub_objects_update)
    for name, data in hub_objects_update.items():
        data['id'] = params.get("augerInfo", {}).get(name+"_id")
        print(name, data)
        ctx_hub.rest_api.call('update_%s'%name, data)

def _get_options_from_dataset_statistic(config, stat_data):
    excluded_features = []
    target_feature = None

    categoricals = []
    label_encoded = []
    time_series = []
    date_time = []

    for item in stat_data:
        if item.get('isTarget'):
            target_feature = item['column_name']

        if not item.get('use') and not item.get('isTarget'):
            excluded_features.append(item['column_name'])

        if item.get('use') or item.get('isTarget'):
            if item['datatype'] == 'categorical':
                categoricals.append(item['column_name'])
            if item['datatype'] == 'hashing':
                categoricals.append(item['column_name'])
                label_encoded.append(item['column_name'])
            if item['datatype'] == 'timeseries':
                time_series.append(item['column_name'])
            if item['datatype'] == 'datetime':
                date_time.append(item['column_name'])

    if target_feature:
        config.set('target', target_feature)
    if excluded_features:
        config.set('exclude', excluded_features)

    if label_encoded:
        config.set('experiment/label_encoded', label_encoded)
    if categoricals:
        config.set('experiment/categoricals', categoricals)
    if date_time:    
        config.set('experiment/date_time', date_time)
    if time_series:
        config.set('experiment/time_series', time_series)

def execute_task(task, params, wait_for_result=False, delay=0):
    if wait_for_result:
        task.apply(args=[params], countdown = delay)
    else:    
        task.apply_async(args=[params], countdown = delay)

def _format_leaderboard_for_hub(leaderboard):
    formatted_leaderboard_list = []

    for item in leaderboard:
        obj = {}
        uid = item['uid']
        obj[uid] = item
        formatted_leaderboard_list.append(obj)

    return formatted_leaderboard_list

def _update_hub_trials(params, trials):
    from a2ml.api.auger.experiment import AugerExperiment

    ctx = Context(debug=True)
    experiment = AugerExperiment(ctx)

    ctx.rest_api.call("update_trials", {
        'experiment_session_id': params['augerInfo']['experiment_session_id'],
        #'dataset_manifest_id': status['evaluation_options']['augerInfo']['dataset_manifest_id'],
        'trials': _format_leaderboard_for_hub(trials)
    })

def _get_leaderboad_trials(params):
    ctx = Context(
        name=params.get('provider'),
        #path=params.get('project_path'),
        debug=params.get('debug_log', True)
    )
    ctx.set_runs_on_server(True)
    ctx.config.set('providers', [params.get('provider')])

    provider_info = params.get('provider_info', {}).get(params.get('provider'), {})

    ctx.config.set('name', provider_info.get('project').get('name'), params.get('provider'))
    #ctx.config.set('dataset', provider_info.get('project_file').get('url'), params.get('provider'))
    ctx.config.set('experiment/name', provider_info.get('experiment').get('name'), params.get('provider'))
    ctx.config.set('experiment/run_id', provider_info.get('experiment_session').get('id'), params.get('provider'))

    res = A2ML(ctx).evaluate()
    leaderboard = []
    if res.get(params.get('provider'), {}).get('result'):
        leaderboard = res[params.get('provider')]['data']['leaderboard']

    trials = []
    if not leaderboard:
        return trials

    for item in leaderboard:
        trials.append({
            "uid": item['model id'],
            "score": item['all_scores'][item['primary_metric']],
            "scoring": item['primary_metric'],
            "ensemble": 'Ensemble' in item['algorithm'],
            "task_type": item['task_type'],
            "all_scores": item['all_scores'],
            "score_name": item['primary_metric'],
            "algorithm_name": item['algorithm_name'],
            "optimizer_name": "Azure",
            "evaluation_time": item["fit_time"],
            "algorithm_params": item['algorithm_params'],
            "experiment_session_id": ctx.config.get('experiment/run_id'),            
            "preprocessor": item["preprocessor"],
            "algorithm_params_hash": None, #TODO : make_algorithm_params_hash in auger-ml

            "error": None,
            "ratio": 1.0,
            "budget": None,
            "create_trial_time": None,
            "estimated_time": 0,
            "estimated_timeout": False,
            "trialClass": None,
            "fold_scores": [],
            "fold_times": [],
            "metrics_time": 0,
            "dataset_ncols": 0,
            "dataset_nrows": 0,
            "dataset_manifest_id": None,
        })
    return trials

@celeryApp.task(ignore_result=True, acks_late=True,
    acks_on_failure_or_timeout=False, reject_on_worker_lost=True,
    autoretry_for=(Exception,), retry_kwargs={'max_retries': None, 'countdown': 20})
def monitor_evaluate_task(params):

    _update_hub_trials(params, _get_leaderboad_trials(params))
    execute_task( monitor_evaluate_task, params, wait_for_result=False, 
        delay=params.get("monitor_evaluate_interval", 20))

@celeryApp.task(ignore_result=False)
def evaluate_start_task(params):
    if not params.get('augerInfo', {}).get('experiment_session_id'):
        raise Exception("evaluate_start_task missed experiment_session_id parameter.")

    experiment_session, ctx_hub = _get_hub_experiment_session(params['augerInfo']['experiment_session_id'])    

    ctx = Context(
        name=params.get('provider'),
        #path=params.get('project_path'),
        debug=params.get('debug_log', True)
    )
    ctx.set_runs_on_server(True)
    ctx.config.set('providers', [params.get('provider')])

    provider_info = params.get('provider_info', {}).get(params.get('provider'), {})

    ctx.config.set('name', provider_info.get('project').get('name'), params.get('provider'))
    ctx.config.set('dataset', provider_info.get('project_file').get('url'), params.get('provider'))
    ctx.config.set('experiment/name', provider_info.get('experiment').get('name'), params.get('provider'))

    ctx.config.set('cluster/name', provider_info.get('cluster').get('name'), params.get('provider'))
    ctx.config.set('cluster/min_nodes', provider_info.get('cluster').get('min_nodes'), params.get('provider'))
    ctx.config.set('cluster/max_nodes', provider_info.get('cluster').get('max_nodes'), params.get('provider'))
    ctx.config.set('cluster/type', provider_info.get('cluster').get('type'), params.get('provider'))

    evaluation_options = experiment_session.get('model_settings', {}).get('evaluation_options')
    dataset_statistics = experiment_session.get('dataset_statistics', {}).get('stat_data', [])

    ctx.config.set('model_type', 
        "classification" if evaluation_options.get('classification', True) else "regression")
    _get_options_from_dataset_statistic(ctx.config, dataset_statistics)

    ctx.config.set('experiment/validation_source', evaluation_options.get('test_data_path'))

    ctx.config.set('experiment/cross_validation_folds', 
        evaluation_options.get('crossValidationFolds', 5))
    ctx.config.set('experiment/max_total_time', 
        evaluation_options.get('max_total_time_mins', 60))
    ctx.config.set('experiment/max_eval_time', 
        evaluation_options.get('max_eval_time_mins', 6))
    ctx.config.set('experiment/max_n_trials', 
        evaluation_options.get('max_n_trials', 100))
    ctx.config.set('experiment/use_ensemble', 
        evaluation_options.get('use_ensemble', True))
    if evaluation_options.get('scoring') == "f1":
        ctx.config.set('experiment/metric',
            "accuracy", params.get('provider'))
    else:    
        ctx.config.set('experiment/metric',
            evaluation_options.get('scoring'), params.get('provider'))

    ctx.config.clean_changes()    
    res = A2ML(ctx).train()

    _update_hub_objects(ctx, params.get('provider'), ctx_hub, params)

    execute_task( monitor_evaluate_task, params, wait_for_result=False, 
        delay=params.get("monitor_evaluate_interval", 20))

    return res

@celeryApp.task(ignore_result=False)
def import_data_task(params):
    if not params.get("augerInfo").get('project_file_id'):
        raise Exception("import_data_task missed project_file_id parameter.")

    project_file, ctx_hub = _get_hub_project_file(params["augerInfo"]['project_file_id'])

    data_path = params.get('url')    
    if not data_path:    
        data_path = project_file.get('url')

    ctx = Context(
        name=params.get('provider'),
        debug=params.get('debug_log', True)
    )
    ctx.set_runs_on_server(True)
    ctx.config.set('providers', [params.get('provider')])

    provider_info = params.get('provider_info', {}).get(params.get('provider'), {})
    ctx.config.set('name', provider_info.get('project').get('name'), params.get('provider'))

    ctx.config.clean_changes()    
    res = A2ML(ctx).import_data(source=data_path)
    _update_hub_objects(ctx, params.get('provider'), ctx_hub, params)

    return res

@celeryApp.task(ignore_result=False, after_return=process_task_result)
def score_actuals_by_model_task(params):
    return ModelReview(params).score_actuals(
        actuals_path = params.get('actuals_path'),
        actual_records=params.get('actual_records'),
        prediction_group_id=params.get('prediction_group_id', None),
        primary_prediction_group_id=params.get('primary_prediction_group_id', None),
        primary_model_path=ModelHelper.get_model_path(params.get('primary_pipeline_id', None),
            params.get('augerInfo', {}).get('projectPath')),
        actual_date=params.get('actual_date'),
        actuals_id=params.get('actuals_id')
    )

@celeryApp.task(ignore_result=False, after_return=process_task_result)
def count_actuals_by_prediction_id_task(params):
    return ModelReview(params).count_actuals_by_prediction_id()

@celeryApp.task(ignore_result=False, after_return=process_task_result)
def score_model_performance_daily_task(params):
    return ModelReview(params).score_model_performance_daily(
        date_from=params.get('date_from'),
        date_to=params.get('date_to')
    )

@celeryApp.task(ignore_result=False, after_return=process_task_result)
def set_support_review_model_flag_task(params):
    return ModelReview(params).set_support_review_model_flag(
        flag_value=params.get('support_review_model')
    )

@celeryApp.task(ignore_result=False, after_return=process_task_result)
def remove_model_task(params):
    return ModelReview(params).remove_model()

@celeryApp.task(ignore_result=False, after_return=process_task_result)
def distribution_chart_stats_task(params):
    return ModelReview(params).distribution_chart_stats(
        date_from=params.get('date_from'),
        date_to=params.get('date_to')
    )

@celeryApp.task(ignore_result=False, after_return=process_task_result)
def clear_model_results_and_actuals(params):
    return ModelReview(params).clear_model_results_and_actuals()

@celeryApp.task(ignore_result=False, after_return=process_task_result)
def build_review_data_task(params):
    return ModelReview(params).build_review_data(
        data_path=params.get('data_path')
    )
