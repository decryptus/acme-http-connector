# Copyright 2026 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from requests import HTTPError

from acme_http_connector.dehydrated import main, run_hook
from acme_http_connector import ConfigurationError


class DehydratedTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = Path(temporary.name) / 'connector.yml'
        self.config.write_text('{}')
        patcher = patch('acme_http_connector.dehydrated.HTTPConnector')
        self.factory = patcher.start()
        self.addCleanup(patcher.stop)
        self.connector = self.factory.return_value

    def call(self, operation, *arguments):
        run_hook(operation, list(arguments), self.config)

    def test_publish_full_path_and_key_authorization(self):
        self.call('deploy_challenge', 'example.test', 'token', 'token.thumbprint')
        self.factory.assert_called_once_with({}, phases=('perform',))
        self.connector.publish.assert_called_once_with(
            '/.well-known/acme-challenge/token', 'token.thumbprint')

    def test_chained_challenges(self):
        self.call('deploy_challenge', 'one.test', 'one', 'one.thumb',
                  'two.test', 'two', 'two.thumb')
        self.assertEqual(self.connector.publish.call_count, 2)
        self.assertEqual(self.connector.publish.call_args.args,
                         ('/.well-known/acme-challenge/two', 'two.thumb'))

    def test_chained_cleanup(self):
        self.call('clean_challenge', 'one.test', 'one', 'one.thumb',
                  'two.test', 'two', 'two.thumb')
        self.factory.assert_called_once_with({}, phases=('cleanup',))
        self.assertEqual(self.connector.cleanup.call_count, 2)
        self.connector.cleanup.assert_called_with('/.well-known/acme-challenge/two')

    def test_deploy_file_order(self):
        self.call('deploy_cert', 'example.test', 'key', 'cert', 'fullchain', 'chain', '123')
        self.factory.assert_called_once_with({}, phases=('deploy',))
        self.connector.deploy_files.assert_called_once_with('example.test', 'cert', 'key', 'chain')

    def test_invalid_triple_count(self):
        for arguments in ([], ['example.test'], ['example.test', 'token']):
            with self.subTest(arguments=arguments), self.assertRaises(ConfigurationError):
                run_hook('deploy_challenge', arguments, self.config)
        self.factory.assert_not_called()

    def test_whole_batch_validated_before_publication(self):
        with self.assertRaises(ConfigurationError):
            self.call('deploy_challenge', 'one.test', 'one', 'one.thumb',
                      'two.test', '../two', 'two.thumb')
        self.factory.assert_not_called()

    def test_dns01_digest_rejected(self):
        with self.assertRaises(ConfigurationError):
            self.call('deploy_challenge', 'example.test', 'token', 'digest')
        self.factory.assert_not_called()

    def test_mismatched_token_rejected(self):
        with self.assertRaises(ConfigurationError):
            self.call('deploy_challenge', 'example.test', 'one', 'two.thumb')

    def test_token_cannot_change_path_or_query(self):
        for token in ('../token', 'token?q=1', 'a/b', 'a#b', 'a\nb', ''):
            with self.subTest(token=token), self.assertRaises(ConfigurationError):
                self.call('clean_challenge', 'example.test', token, token + '.thumb')
        self.factory.assert_not_called()

    def test_invalid_deploy_arguments(self):
        for arguments in ([], ['domain', 'key', 'cert'], ['domain', '', 'cert', 'full', 'chain', '0']):
            with self.subTest(arguments=arguments), self.assertRaises(ConfigurationError):
                run_hook('deploy_cert', arguments, self.config)
        self.factory.assert_not_called()

    def test_unknown_and_non_action_hooks_do_not_load_configuration(self):
        self.config.unlink()
        for operation in ('startup_hook', 'exit_hook', 'unchanged_cert', 'sync_cert',
                          'generate_csr', 'deploy_ocsp', 'invalid_challenge',
                          'request_failure', 'this_hookscript_is_broken__dehydrated_is_working_fine__please_ignore_unknown_hooks_in_your_script'):
            self.call(operation)
        self.factory.assert_not_called()

    def test_yaml_requires_mapping(self):
        for contents in ('', '- a\n- b', '42'):
            self.config.write_text(contents)
            with self.subTest(contents=contents), self.assertRaises(ConfigurationError):
                self.call('deploy_challenge', 'example.test', 'token', 'token.thumb')
        self.factory.assert_not_called()

    def test_request_failure_propagates_and_stops_batch(self):
        self.connector.publish.side_effect = HTTPError('private URL')
        with self.assertRaises(HTTPError):
            self.call('deploy_challenge', 'one.test', 'one', 'one.thumb',
                      'two.test', 'two', 'two.thumb')
        self.assertEqual(self.connector.publish.call_count, 1)

    def test_cli_config_environment_and_success_output(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {'ACME_HTTP_CONNECTOR_CONFIG': str(self.config)}), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(main(['deploy_challenge', 'example.test', 'token', 'token.thumb']), 0)
        self.assertEqual(stdout.getvalue(), '')
        self.assertEqual(stderr.getvalue(), '')
        self.connector.publish.assert_called_once()

    def test_cli_failure_is_nonzero_and_redacted(self):
        for error in (HTTPError('https://user:secret@example.test'),
                      OSError('PRIVATE KEY secret'), ConfigurationError('secret')):
            self.connector.deploy_files.side_effect = error
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.dict(os.environ, {'ACME_HTTP_CONNECTOR_CONFIG': str(self.config)}), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(main(['deploy_cert', 'domain', 'key', 'cert', 'full', 'chain', '0']), 1)
            self.assertEqual(stdout.getvalue(), '')
            self.assertNotIn('secret', stderr.getvalue())
            self.assertIn('hook failed', stderr.getvalue())

    def test_cli_missing_configuration_fails(self):
        with patch.dict(os.environ, {'ACME_HTTP_CONNECTOR_CONFIG': str(self.config) + '.missing'}), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['deploy_challenge', 'example.test', 'token', 'token.thumb']), 1)

    def test_cli_missing_operation(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([]), 2)

    def test_unused_invalid_phase_is_ignored(self):
        self.config.write_text('deploy:\n  timeout: invalid\n')
        self.call('deploy_challenge', 'example.test', 'token', 'token.thumb')
        self.factory.assert_called_once_with({'deploy': {'timeout': 'invalid'}}, phases=('perform',))
