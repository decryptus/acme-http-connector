# Copyright 2019-2026 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from certbot import errors

from certbot_httpreq.authenticator import Authenticator
from certbot_httpreq.installer import Installer
from certbot_httpreq.config import set_option


def plugin(cls, tmp_path, contents):
    config = tmp_path / 'config.yml'
    config.write_text(contents)
    instance = cls(SimpleNamespace(test_config=str(config), http01_port=80), 'test')
    instance.prepare()
    return instance


@pytest.mark.parametrize('value,expected', [('false', False), ('true', True), ('0', False), ('1', True), ('/ca.pem', '/ca.pem')])
def test_environment_verify(monkeypatch, value, expected):
    monkeypatch.setenv('CBT_HTTPREQ_DEPLOY_VERIFY', value)
    config = {}
    set_option(config, 'deploy', 'verify')
    assert config['verify'] == expected


def test_explicit_false_and_defaults(monkeypatch):
    monkeypatch.setenv('CBT_HTTPREQ_DEPLOY_VERIFY', 'true')
    config = {'verify': False}
    set_option(config, 'deploy', 'verify')
    set_option(config, 'deploy', 'timeout')
    assert config == {'verify': False, 'timeout': 30.0}


def test_environment_timeout(monkeypatch):
    monkeypatch.setenv('CBT_HTTPREQ_DEPLOY_TIMEOUT', '2.5')
    config = {}
    set_option(config, 'deploy', 'timeout')
    assert config['timeout'] == 2.5


@pytest.mark.parametrize('value', [0, -1, 'nan', 'inf', 'oops', False])
def test_invalid_timeout(value):
    with pytest.raises(errors.PluginError):
        set_option({'timeout': value}, 'perform', 'timeout')


def test_multiple_challenges_do_not_leak_query_parameters(tmp_path):
    auth = plugin(Authenticator, tmp_path, 'perform:\n  uri: https://example.com?existing=1\n  param_challenge: token\n')
    for token in ['first', 'second', 'first']:
        challenge = SimpleNamespace(chall=SimpleNamespace(path='/.well-known/acme-challenge/' + token))
        query = parse_qs(urlsplit(auth._build_uri(challenge)).query)
        assert query == {'existing': ['1'], 'token': [challenge.chall.path]}


def test_cleanup_uses_own_settings(tmp_path, monkeypatch):
    auth = plugin(Authenticator, tmp_path, 'perform:\n  timeout: 10\n  verify: true\ncleanup:\n  timeout: 2\n  verify: false\n')
    request = Mock()
    monkeypatch.setattr('certbot_httpreq.authenticator.requests.delete', request)
    auth.cleanup([SimpleNamespace(chall=SimpleNamespace(path='/challenge'))])
    assert request.call_args.kwargs['timeout'] == 2
    assert request.call_args.kwargs['verify'] is False
    request.return_value.raise_for_status.assert_called_once()


def test_perform_payload_and_no_header_mutation(tmp_path, monkeypatch):
    auth = plugin(Authenticator, tmp_path, 'perform:\n  param_validation: value\n  headers:\n    X-Test: kept\n')
    response = Mock()
    response.simple_verify.return_value = True
    challenge = Mock()
    challenge.chall.path = '/.well-known/acme-challenge/token'
    challenge.response_and_validation.return_value = (response, 'validation')
    request = Mock()
    monkeypatch.setattr('certbot_httpreq.authenticator.requests.put', request)
    assert auth.perform([challenge]) == [response]
    assert request.call_args.kwargs['json'] == {'value': 'validation'}
    assert auth._config['perform']['headers'] == {'X-Test': 'kept'}


def test_deploy_payload_and_optional_chain(tmp_path, monkeypatch):
    installer = plugin(Installer, tmp_path, 'deploy:\n  body_params:\n    cert: certificate\n  headers:\n    X-Test: kept\n')
    cert = tmp_path / 'cert.pem'
    key = tmp_path / 'key.pem'
    cert.write_text('certificate')
    key.write_text('private-key')
    request = Mock()
    monkeypatch.setattr('certbot_httpreq.installer.requests.post', request)
    installer.deploy_cert('example.com', str(cert), str(key), None, None)
    assert request.call_args.kwargs['json'] == {'domain': 'example.com', 'certificate': 'certificate', 'key': 'private-key', 'chain': ''}
    assert request.call_args.kwargs['verify'] is True
    assert installer._config['deploy']['headers'] == {'X-Test': 'kept'}


def test_invalid_deploy_method_fails(tmp_path):
    installer = plugin(Installer, tmp_path, 'deploy:\n  method: GET\n')
    with pytest.raises(errors.PluginError):
        installer.deploy_cert('example.com', None, None, None, None)


def test_http_failure_is_propagated(tmp_path, monkeypatch):
    from requests import HTTPError
    auth = plugin(Authenticator, tmp_path, '{}')
    request = Mock()
    request.return_value.raise_for_status.side_effect = HTTPError('failure')
    monkeypatch.setattr('certbot_httpreq.authenticator.requests.delete', request)
    with pytest.raises(HTTPError):
        auth.cleanup([SimpleNamespace(chall=SimpleNamespace(path='/challenge'))])


def test_renewal_deploys_lineage(tmp_path):
    installer = plugin(Installer, tmp_path, '{}')
    installer.deploy_cert = Mock()
    lineage = SimpleNamespace(names=lambda: ['example.com', 'www.example.com'], cert_path='cert', key_path='key', chain_path='chain', fullchain_path='fullchain')
    installer.renew_deploy(lineage)
    installer.deploy_cert.assert_called_once_with('example.com', 'cert', 'key', 'chain', 'fullchain')


def test_legacy_plugin_names_are_discoverable():
    from certbot._internal.plugins.disco import PluginsRegistry
    plugins = PluginsRegistry.find_all()
    assert 'certbot-httpreq:auth' in plugins
    assert 'certbot-httpreq:installer' in plugins
