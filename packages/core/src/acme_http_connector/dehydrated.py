# Copyright 2026 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""Dehydrated HTTP-01 hook. Unknown lifecycle hooks deliberately do nothing."""
import os
import re
import sys
from collections.abc import Mapping

import requests
import yaml

from .connector import HTTPConnector
from .errors import ConfigurationError


_OPERATIONS = {'deploy_challenge': 'perform', 'clean_challenge': 'cleanup',
               'deploy_cert': 'deploy'}
_TOKEN = re.compile(r'[A-Za-z0-9_-]{1,256}\Z')
_DEFAULT_CONFIG = '/etc/acme-http-connector.yml'


def run_hook(operation, arguments, config_path):
    """Dispatch a hook, validating every argument group before any API request.

    Both single and HOOK_CHAIN challenge calls are supported. Certificate
    deployment uses the leaf and chain separately, in the core's file order.
    Unknown hooks must succeed: Dehydrated uses one to probe hook compatibility.
    """
    if operation not in _OPERATIONS:
        return
    if operation in ('deploy_challenge', 'clean_challenge'):
        if not arguments or len(arguments) % 3:
            raise ConfigurationError('Challenge hooks require domain/token/value triples')
        challenges = []
        for offset in range(0, len(arguments), 3):
            domain, token, value = arguments[offset:offset + 3]
            if not domain or not _TOKEN.fullmatch(token):
                raise ConfigurationError('Invalid HTTP-01 challenge arguments')
            # DNS-01 uses a digest, not token.thumbprint. Do not publish it as HTTP-01.
            if not value.startswith(token + '.') or not _TOKEN.fullmatch(value[len(token) + 1:]):
                raise ConfigurationError('Expected HTTP-01 key authorization')
            challenges.append(('/.well-known/acme-challenge/' + token, value))
    elif len(arguments) != 6 or not all(arguments[:5]):
        raise ConfigurationError('deploy_cert requires domain/key/cert/fullchain/chain/timestamp')

    with open(config_path, encoding='utf-8') as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, Mapping):
        raise ConfigurationError('The hook configuration must be a YAML mapping')
    phase = _OPERATIONS[operation]
    connector = HTTPConnector(config, phases=(phase,))
    if operation == 'deploy_cert':
        domain, key, cert, _fullchain, chain, _timestamp = arguments
        connector.deploy_files(domain, cert, key, chain)
    else:
        for path, value in challenges:
            if operation == 'deploy_challenge':
                connector.publish(path, value)
            else:
                connector.cleanup(path)


def main(argv=None):
    """Console entry point; never echo request URLs, credentials or PEM content."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        print('Usage: acme-http-dehydrated HOOK [ARGUMENTS...]', file=sys.stderr)
        return 2
    try:
        run_hook(arguments[0], arguments[1:],
                 os.getenv('ACME_HTTP_CONNECTOR_CONFIG') or _DEFAULT_CONFIG)
    except (ConfigurationError, OSError, yaml.YAMLError, requests.RequestException,
            TypeError, ValueError, AttributeError):
        # Exception strings can contain API credentials, URLs or YAML secrets.
        print('acme-http-dehydrated: hook failed; check arguments, configuration, files and API availability',
              file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
