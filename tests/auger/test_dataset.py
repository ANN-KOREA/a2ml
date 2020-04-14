# from auger.cli.cli import cli
# from auger.api.utils.config import Config
# from auger.api.cloud.project import AugerProjectApi

import pytest
import copy

from a2ml.api.auger.dataset import AugerDataset
from a2ml.api.auger.impl.cloud.project_api import AugerProjectApi
from .utils import interceptor, PAYLOAD_DEFAULT, object_status_chain


class TestDataSet():
    def test_list(self, log, project, ctx, authenticated, monkeypatch):
        PAYLOAD = PAYLOAD_DEFAULT
        interceptor(PAYLOAD, monkeypatch)

        result = AugerDataset(ctx).list()
        assert result.get('datasets')
        assert len(result['datasets']) == 2
        assert result['datasets'][0]['name'] == 'test_dataset1'
        assert result['datasets'][1]['name'] == 'test_dataset2'

    def test_create(self, log, project, ctx, authenticated, monkeypatch):
        PAYLOAD = copy.deepcopy(PAYLOAD_DEFAULT)
        PAYLOAD['get_project_files'] = {
            'data': [{
                'project_id': 1,
                'url': 's3://iris.csv',
                'name': 'iris-2.csv',
            }],
            'meta': {'pagination': {'offset': 0, 'total': 1, 'count': 1, 'limit': 100}, 'status': 200},
        }
        PAYLOAD['get_project_file'] = {'data': {}},
        PAYLOAD['create_project_file'] = {'data': {}}

        interceptor(PAYLOAD, monkeypatch)
        object_status_chain(['processing', 'processed'], monkeypatch)
        monkeypatch.setattr(AugerProjectApi, 'is_running', lambda x: True)
        monkeypatch.setattr('a2ml.api.auger.impl.cloud.dataset_api.AugerDataSetApi._upload_to_cloud', lambda *args: 's3://iris.csv')

        result = AugerDataset(ctx).create(source='iris.csv')
        assert result.get('created') == 'iris-1.csv'

    def test_delete(self, log, project, ctx, authenticated, monkeypatch):
        PAYLOAD = copy.deepcopy(PAYLOAD_DEFAULT)
        PAYLOAD['delete_project_file'] = {'data': {}}

        interceptor(PAYLOAD, monkeypatch)

        result = AugerDataset(ctx).delete(name='test_dataset1')
        assert result.get('deleted') == 'test_dataset1'

    def test_select(self, log, project, ctx, authenticated):
        result = AugerDataset(ctx).select(name='iris.csv')
        assert result.get('selected') == 'iris.csv'
        print(result)
