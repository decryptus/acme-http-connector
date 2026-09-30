# Copyright 2019-2026 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from requests import HTTPError

from acme_http_connector import HTTPConnector, ConfigurationError


def test_configuration_and_query_are_not_mutated():
    config = {'perform': {'uri': 'https://api.example.com?existing=1',
                          'param_challenge': 'token', 'headers': {'X-Test': 'value'}}}
    before = deepcopy(config)
    connector = HTTPConnector(config)
    for token in ['one', 'two', 'one']:
        path = '/.well-known/acme-challenge/' + token
        assert parse_qs(urlsplit(connector.challenge_uri(path)).query) == {
            'existing': ['1'], 'token': [path]}
    assert config == before


@pytest.mark.parametrize('format,expected_json,expected_data', [
    ('json', {'value': 'authorization'}, None),
    ('form-urlencoded', None, {'value': 'authorization'}),
])
def test_publish_payload(monkeypatch, format, expected_json, expected_data):
    request = Mock()
    monkeypatch.setattr('acme_http_connector.connector.requests.put', request)
    connector = HTTPConnector({'perform': {'uri': 'https://api.example.com',
        'path': '/publish', 'format': format, 'param_validation': 'value'}})
    connector.publish('/.well-known/acme-challenge/token', 'authorization')
    assert request.call_args.args == ('https://api.example.com/publish/.well-known/acme-challenge/token',)
    assert request.call_args.kwargs['json'] == expected_json
    assert request.call_args.kwargs['data'] == expected_data
    request.return_value.raise_for_status.assert_called_once()


def test_cleanup_and_failure(monkeypatch):
    request = Mock()
    request.return_value.raise_for_status.side_effect = HTTPError('failure')
    monkeypatch.setattr('acme_http_connector.connector.requests.delete', request)
    connector = HTTPConnector({'cleanup': {'timeout': 2, 'verify': '/ca.pem'}})
    with pytest.raises(HTTPError):
        connector.cleanup('/.well-known/acme-challenge/token')
    assert request.call_args.kwargs['timeout'] == 2
    assert request.call_args.kwargs['verify'] == '/ca.pem'
    assert 'json' not in request.call_args.kwargs
    assert 'data' not in request.call_args.kwargs


def test_deploy_pem_strings(monkeypatch):
    request = Mock()
    monkeypatch.setattr('acme_http_connector.connector.requests.post', request)
    connector = HTTPConnector({'deploy': {'body_params': {'cert': 'certificate'}}})
    connector.deploy('example.com', 'CERT', 'KEY')
    assert request.call_args.kwargs['json'] == {
        'domain': 'example.com', 'certificate': 'CERT', 'key': 'KEY', 'chain': ''}


@pytest.mark.parametrize('phase,operation,args', [
    ('perform', 'publish', ('/challenge', 'authorization')),
    ('cleanup', 'cleanup', ('/challenge',)),
    ('deploy', 'deploy', ('example.com', 'CERT', 'KEY')),
])
def test_invalid_methods(phase, operation, args):
    connector = HTTPConnector({phase: {'method': 'GET'}})
    with pytest.raises(ConfigurationError, match='Invalid HTTP method'):
        getattr(connector, operation)(*args)


def test_verification_address():
    connector = HTTPConnector({'perform': {'uri': 'https://api.example.com:8443'}})
    assert connector.verification_address(5000) == ('api.example.com', 8443)
    assert HTTPConnector().verification_address(5000) == ('localhost', 5000)
