# Copyright 2019-2026 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from copy import deepcopy
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit
from requests import HTTPError
from acme_http_connector import HTTPConnector, ConfigurationError

class CoreTests(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp_path = Path(temporary.name)

    def set_env(self, name, value):
        patcher = patch.dict(os.environ, {name: value})
        patcher.start()
        self.addCleanup(patcher.stop)

    def replace(self, name, value):
        patcher = patch(name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_configuration_and_query_are_not_mutated(self):
        config = {'perform': {'uri': 'https://api.example.com?existing=1', 'param_challenge': 'token', 'headers': {'X-Test': 'value'}}}
        before = deepcopy(config)
        connector = HTTPConnector(config)
        for token in ['one', 'two', 'one']:
            path = '/.well-known/acme-challenge/' + token
            assert parse_qs(urlsplit(connector.challenge_uri(path)).query) == {'existing': ['1'], 'token': [path]}
        assert config == before

    def test_publish_payload_1(self):
        format = 'json'
        expected_json = {'value': 'authorization'}
        expected_data = None
        request = Mock()
        self.replace('acme_http_connector.connector.requests.put', request)
        connector = HTTPConnector({'perform': {'uri': 'https://api.example.com', 'path': '/publish', 'format': format, 'param_validation': 'value'}})
        connector.publish('/.well-known/acme-challenge/token', 'authorization')
        assert request.call_args.args == ('https://api.example.com/publish/.well-known/acme-challenge/token',)
        assert request.call_args.kwargs['json'] == expected_json
        assert request.call_args.kwargs['data'] == expected_data
        request.return_value.raise_for_status.assert_called_once()

    def test_publish_payload_2(self):
        format = 'form-urlencoded'
        expected_json = None
        expected_data = {'value': 'authorization'}
        request = Mock()
        self.replace('acme_http_connector.connector.requests.put', request)
        connector = HTTPConnector({'perform': {'uri': 'https://api.example.com', 'path': '/publish', 'format': format, 'param_validation': 'value'}})
        connector.publish('/.well-known/acme-challenge/token', 'authorization')
        assert request.call_args.args == ('https://api.example.com/publish/.well-known/acme-challenge/token',)
        assert request.call_args.kwargs['json'] == expected_json
        assert request.call_args.kwargs['data'] == expected_data
        request.return_value.raise_for_status.assert_called_once()

    def test_cleanup_and_failure(self):
        request = Mock()
        request.return_value.raise_for_status.side_effect = HTTPError('failure')
        self.replace('acme_http_connector.connector.requests.delete', request)
        connector = HTTPConnector({'cleanup': {'timeout': 2, 'verify': '/ca.pem'}})
        with self.assertRaises(HTTPError):
            connector.cleanup('/.well-known/acme-challenge/token')
        assert request.call_args.kwargs['timeout'] == 2
        assert request.call_args.kwargs['verify'] == '/ca.pem'
        assert 'json' not in request.call_args.kwargs
        assert 'data' not in request.call_args.kwargs

    def test_deploy_pem_strings(self):
        request = Mock()
        self.replace('acme_http_connector.connector.requests.post', request)
        connector = HTTPConnector({'deploy': {'body_params': {'cert': 'certificate'}}})
        connector.deploy('example.com', 'CERT', 'KEY')
        assert request.call_args.kwargs['json'] == {'domain': 'example.com', 'certificate': 'CERT', 'key': 'KEY', 'chain': ''}

    def test_invalid_methods_1(self):
        phase = 'perform'
        operation = 'publish'
        args = ('/challenge', 'authorization')
        connector = HTTPConnector({phase: {'method': 'GET'}})
        with self.assertRaisesRegex(ConfigurationError, 'Invalid HTTP method'):
            getattr(connector, operation)(*args)

    def test_invalid_methods_2(self):
        phase = 'cleanup'
        operation = 'cleanup'
        args = ('/challenge',)
        connector = HTTPConnector({phase: {'method': 'GET'}})
        with self.assertRaisesRegex(ConfigurationError, 'Invalid HTTP method'):
            getattr(connector, operation)(*args)

    def test_invalid_methods_3(self):
        phase = 'deploy'
        operation = 'deploy'
        args = ('example.com', 'CERT', 'KEY')
        connector = HTTPConnector({phase: {'method': 'GET'}})
        with self.assertRaisesRegex(ConfigurationError, 'Invalid HTTP method'):
            getattr(connector, operation)(*args)

    def test_verification_address(self):
        connector = HTTPConnector({'perform': {'uri': 'https://api.example.com:8443'}})
        assert connector.verification_address(5000) == ('api.example.com', 8443)
        assert HTTPConnector().verification_address(5000) == ('localhost', 5000)
