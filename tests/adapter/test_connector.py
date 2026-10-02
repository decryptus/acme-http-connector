# Copyright 2019-2026 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit
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

class CertbotTests(unittest.TestCase):

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

    def test_environment_verify_1(self):
        value = 'false'
        expected = False
        self.set_env('CBT_HTTPREQ_DEPLOY_VERIFY', value)
        config = {}
        set_option(config, 'deploy', 'verify')
        self.assertEqual(config['verify'], expected)

    def test_environment_verify_2(self):
        value = 'true'
        expected = True
        self.set_env('CBT_HTTPREQ_DEPLOY_VERIFY', value)
        config = {}
        set_option(config, 'deploy', 'verify')
        self.assertEqual(config['verify'], expected)

    def test_environment_verify_3(self):
        value = '0'
        expected = False
        self.set_env('CBT_HTTPREQ_DEPLOY_VERIFY', value)
        config = {}
        set_option(config, 'deploy', 'verify')
        self.assertEqual(config['verify'], expected)

    def test_environment_verify_4(self):
        value = '1'
        expected = True
        self.set_env('CBT_HTTPREQ_DEPLOY_VERIFY', value)
        config = {}
        set_option(config, 'deploy', 'verify')
        self.assertEqual(config['verify'], expected)

    def test_environment_verify_5(self):
        value = '/ca.pem'
        expected = '/ca.pem'
        self.set_env('CBT_HTTPREQ_DEPLOY_VERIFY', value)
        config = {}
        set_option(config, 'deploy', 'verify')
        self.assertEqual(config['verify'], expected)

    def test_explicit_false_and_defaults(self):
        self.set_env('CBT_HTTPREQ_DEPLOY_VERIFY', 'true')
        config = {'verify': False}
        set_option(config, 'deploy', 'verify')
        set_option(config, 'deploy', 'timeout')
        self.assertEqual(config, {'verify': False, 'timeout': 30.0})

    def test_environment_timeout(self):
        self.set_env('CBT_HTTPREQ_DEPLOY_TIMEOUT', '2.5')
        config = {}
        set_option(config, 'deploy', 'timeout')
        self.assertEqual(config['timeout'], 2.5)

    def test_invalid_timeout_1(self):
        value = 0
        with self.assertRaises(errors.PluginError):
            set_option({'timeout': value}, 'perform', 'timeout')

    def test_invalid_timeout_2(self):
        value = -1
        with self.assertRaises(errors.PluginError):
            set_option({'timeout': value}, 'perform', 'timeout')

    def test_invalid_timeout_3(self):
        value = 'nan'
        with self.assertRaises(errors.PluginError):
            set_option({'timeout': value}, 'perform', 'timeout')

    def test_invalid_timeout_4(self):
        value = 'inf'
        with self.assertRaises(errors.PluginError):
            set_option({'timeout': value}, 'perform', 'timeout')

    def test_invalid_timeout_5(self):
        value = 'oops'
        with self.assertRaises(errors.PluginError):
            set_option({'timeout': value}, 'perform', 'timeout')

    def test_invalid_timeout_6(self):
        value = False
        with self.assertRaises(errors.PluginError):
            set_option({'timeout': value}, 'perform', 'timeout')

    def test_multiple_challenges_do_not_leak_query_parameters(self):
        auth = plugin(Authenticator, self.tmp_path, 'perform:\n  uri: https://example.com?existing=1\n  param_challenge: token\n')
        for token in ['first', 'second', 'first']:
            challenge = SimpleNamespace(chall=SimpleNamespace(path='/.well-known/acme-challenge/' + token))
            query = parse_qs(urlsplit(auth._build_uri(challenge)).query)
            self.assertEqual(query, {'existing': ['1'], 'token': [challenge.chall.path]})

    def test_cleanup_uses_own_settings(self):
        auth = plugin(Authenticator, self.tmp_path, 'perform:\n  timeout: 10\n  verify: true\ncleanup:\n  timeout: 2\n  verify: false\n')
        request = Mock()
        request.return_value.status_code = 200
        self.replace('acme_http_connector.connector.requests.delete', request)
        auth.cleanup([SimpleNamespace(chall=SimpleNamespace(path='/challenge'))])
        self.assertEqual(request.call_args.kwargs['timeout'], 2)
        self.assertIs(request.call_args.kwargs['verify'], False)
        request.return_value.raise_for_status.assert_called_once()

    def test_perform_payload_and_no_header_mutation(self):
        auth = plugin(Authenticator, self.tmp_path, 'perform:\n  param_validation: value\n  headers:\n    X-Test: kept\n')
        response = Mock()
        response.simple_verify.return_value = True
        challenge = Mock()
        challenge.chall.path = '/.well-known/acme-challenge/token'
        challenge.response_and_validation.return_value = (response, 'validation')
        request = Mock()
        request.return_value.status_code = 200
        self.replace('acme_http_connector.connector.requests.put', request)
        self.assertEqual(auth.perform([challenge]), [response])
        self.assertEqual(request.call_args.kwargs['json'], {'value': 'validation'})
        self.assertEqual(auth._config['perform']['headers'], {'X-Test': 'kept'})

    def test_deploy_payload_and_optional_chain(self):
        installer = plugin(Installer, self.tmp_path, 'deploy:\n  body_params:\n    cert: certificate\n  headers:\n    X-Test: kept\n')
        cert = self.tmp_path / 'cert.pem'
        key = self.tmp_path / 'key.pem'
        cert.write_text('certificate')
        key.write_text('private-key')
        request = Mock()
        request.return_value.status_code = 200
        self.replace('acme_http_connector.connector.requests.post', request)
        installer.deploy_cert('example.com', str(cert), str(key), None, None)
        self.assertEqual(request.call_args.kwargs['json'], {'domain': 'example.com', 'certificate': 'certificate', 'key': 'private-key', 'chain': ''})
        self.assertIs(request.call_args.kwargs['verify'], True)
        self.assertEqual(installer._config['deploy']['headers'], {'X-Test': 'kept'})

    def test_invalid_deploy_method_fails(self):
        installer = plugin(Installer, self.tmp_path, 'deploy:\n  method: GET\n')
        with self.assertRaises(errors.PluginError):
            installer.deploy_cert('example.com', None, None, None, None)

    def test_http_failure_is_propagated(self):
        from requests import HTTPError
        auth = plugin(Authenticator, self.tmp_path, '{}')
        request = Mock()
        request.return_value.status_code = 200
        request.return_value.raise_for_status.side_effect = HTTPError('failure')
        self.replace('acme_http_connector.connector.requests.delete', request)
        with self.assertRaises(HTTPError):
            auth.cleanup([SimpleNamespace(chall=SimpleNamespace(path='/challenge'))])

    def test_renewal_deploys_lineage(self):
        installer = plugin(Installer, self.tmp_path, '{}')
        installer.deploy_cert = Mock()
        lineage = SimpleNamespace(names=lambda: ['example.com', 'www.example.com'], cert_path='cert', key_path='key', chain_path='chain', fullchain_path='fullchain')
        installer.renew_deploy(lineage)
        installer.deploy_cert.assert_called_once_with('example.com', 'cert', 'key', 'chain', 'fullchain')

    def test_legacy_plugin_names_are_discoverable(self):
        from certbot._internal.plugins.disco import PluginsRegistry
        plugins = PluginsRegistry.find_all()
        self.assertIn('certbot-httpreq:auth', plugins)
        self.assertIn('certbot-httpreq:installer', plugins)

    def test_authenticator_ignores_unused_deploy_settings(self):
        plugin(Authenticator, self.tmp_path, 'deploy:\n  timeout: invalid\n')

    def test_installer_ignores_unused_challenge_settings(self):
        plugin(Installer, self.tmp_path, 'perform:\n  timeout: invalid\n')

