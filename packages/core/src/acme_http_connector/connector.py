# Copyright 2019-2026 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""HTTP API transport; ACME issuance and validation belong to the caller."""
from copy import deepcopy
from pathlib import Path

import requests
from sonicprobe import helpers
from sonicprobe.libs import urisup

from .config import set_option
from .errors import ConfigurationError


class HTTPConnector:
    """Publish full challenge paths and deploy PEM strings to configured APIs.

    Configuration uses the existing perform/cleanup/deploy YAML mapping.
    The input mapping is copied; callers retain ownership of their settings.
    HTTP and filesystem errors propagate to the caller.
    """

    def __init__(self, config=None, *, phases=('perform', 'cleanup', 'deploy')):
        self.config = deepcopy(config or {})
        self._uris = {}
        methods = {'perform': 'PUT', 'cleanup': 'DELETE', 'deploy': 'POST'}
        for phase in phases:
            if phase not in methods:
                raise ConfigurationError('Unknown phase: %s' % phase)
            method = methods[phase]
            conf = self.config.get(phase) or {}
            self.config[phase] = conf
            defaults = dict(uri='http://localhost', path='/' if phase == 'deploy' else None,
                            method=method, format='json', timeout=None, verify=None)
            if phase != 'deploy':
                defaults['param_challenge'] = None
            if phase == 'perform':
                defaults['param_validation'] = None
            for name, default in defaults.items():
                set_option(conf, phase, name, default)
            uri = list(urisup.uri_help_split(conf['uri']))
            uri[2] = conf['path']
            uri[3] = list(uri[3] or [])
            self._uris[phase] = uri

    def challenge_uri(self, challenge_path, phase='perform'):
        """Build an API URL from the full /.well-known/acme-challenge/... path."""
        if phase not in ('perform', 'cleanup'):
            raise ConfigurationError('Challenge phase must be perform or cleanup')
        uri = list(self._uris[phase])
        uri[3] = list(uri[3])
        param = self.config[phase]['param_challenge']
        if param:
            uri[3].append((param, challenge_path))
        elif uri[2]:
            uri[2] = '/' + (uri[2].strip('/') + challenge_path).lstrip('/')
        else:
            uri[2] = challenge_path
        return urisup.uri_help_unsplit(uri)

    def verification_address(self, default_port=80):
        """Return the configured challenge read host and port for adapter checks."""
        authority = self._uris['perform'][1]
        return authority[2], int(authority[3]) if authority[3] else default_port

    def _request(self, phase, uri, payload=None, body=True):
        conf = self.config[phase]
        method = conf['method'].lower()
        allowed = {'perform': ('put', 'post'), 'cleanup': ('put', 'post', 'delete'),
                   'deploy': ('put', 'post', 'patch')}
        if method not in allowed[phase]:
            raise ConfigurationError('Invalid HTTP method for %s: %s' % (phase, method))
        headers = dict(conf['headers']) if isinstance(conf.get('headers'), dict) else {}
        options = dict(headers=headers, timeout=conf['timeout'], verify=conf['verify'],
                       allow_redirects=False)
        if conf['format'] == 'json':
            headers['Content-Type'] = 'application/json'
        if body:
            options.update(data=None if conf['format'] == 'json' else payload,
                           json=payload if conf['format'] == 'json' else None)
        response = getattr(requests, method)(uri, **options)
        try:
            # A redirect could forward private keys or custom credentials.
            # raise_for_status() alone accepts 3xx responses.
            if 300 <= response.status_code < 400:
                raise requests.HTTPError('HTTP redirect refused; configure the final API URL')
            response.raise_for_status()
        finally:
            response.close()

    def publish(self, challenge_path, validation):
        """Publish key authorization text; does not perform ACME validation."""
        param = self.config['perform']['param_validation']
        payload = {param: validation} if param else validation
        self._request('perform', self.challenge_uri(challenge_path), payload)

    def cleanup(self, challenge_path):
        """Remove one published challenge."""
        self._request('cleanup', self.challenge_uri(challenge_path, 'cleanup'), body=False)

    def deploy(self, domain, cert, key, chain=''):
        """Deploy a domain and PEM strings, including the private key."""
        params = self.config['deploy'].get('body_params')
        params = params if isinstance(params, dict) else {}
        payload = {}
        for name, value in dict(domain=domain, cert=cert, key=key, chain=chain).items():
            field = params.get(name)
            payload[str(field) if helpers.has_len(field) else name] = value
        self._request('deploy', urisup.uri_help_unsplit(self._uris['deploy']), payload)

    def deploy_files(self, domain, cert_path, key_path, chain_path=None):
        """Read PEM files and deploy them; an absent chain becomes an empty string."""
        if self.config['deploy']['method'].lower() not in ('put', 'post', 'patch'):
            raise ConfigurationError('Invalid HTTP method for deploy: %s' % self.config['deploy']['method'])
        self.deploy(domain, Path(cert_path).read_text(), Path(key_path).read_text(),
                    Path(chain_path).read_text() if chain_path else '')
