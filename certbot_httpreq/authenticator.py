# -*- coding: utf-8 -*-
# Copyright 2019-2026 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""HTTP Requests Let's Encrypt authenticator plugin."""
import os
import logging
import requests

from acme import challenges

from sonicprobe import helpers
from sonicprobe.libs import urisup

from certbot import interfaces, errors
from certbot.plugins import common

from certbot_httpreq.config import set_option


LOG = logging.getLogger("certbot-httpreq")

PERFORM_ALLOWED_HTTP_METHODS = ('put', 'post')
CLEANUP_ALLOWED_HTTP_METHODS = ('put', 'post', 'delete')


class Authenticator(common.Plugin, interfaces.Authenticator):
    description = "HTTP Server Authenticator"

    @classmethod
    def add_parser_arguments(cls, add):
        add("config",
            default = os.getenv('CBT_HTTPREQ_AUTH_CONFIG') or '/etc/letsencrypt/certbot-httpreq.yml',
            help    = "Path to certbot-httpreq configuration file")

    def __init__(self, *args, **kwargs):
        super(Authenticator, self).__init__(*args, **kwargs)
        self._config = {}
        self._uri    = {}

    @staticmethod
    def _init_uri(uri, path):
        uri    = list(urisup.uri_help_split(uri))
        uri[2] = path

        if uri[3]:
            uri[3] = list(uri[3])
        else:
            uri[3] = []

        return uri

    _set_option = staticmethod(set_option)

    def prepare(self):  # pylint: disable=missing-docstring,no-self-use
        self._config = helpers.load_conf_yaml_file(self.conf('config'))
        if not self._config.get('perform'):
            self._config['perform'] = {}

        if not self._config.get('cleanup'):
            self._config['cleanup'] = {}

        confperf  = self._config['perform']
        confclean = self._config['cleanup']

        self._set_option(confperf, 'perform', 'uri', 'http://localhost')
        self._set_option(confperf, 'perform', 'path')
        self._set_option(confperf, 'perform', 'method', 'PUT')
        self._set_option(confperf, 'perform', 'format', 'json')
        self._set_option(confperf, 'perform', 'param_challenge')
        self._set_option(confperf, 'perform', 'param_validation')
        self._set_option(confperf, 'perform', 'timeout')
        self._set_option(confperf, 'perform', 'verify')

        self._set_option(confclean, 'cleanup', 'uri', 'http://localhost')
        self._set_option(confclean, 'cleanup', 'path')
        self._set_option(confclean, 'cleanup', 'method', 'DELETE')
        self._set_option(confclean, 'cleanup', 'format', 'json')
        self._set_option(confclean, 'cleanup', 'param_challenge')
        self._set_option(confclean, 'cleanup', 'timeout')
        self._set_option(confclean, 'cleanup', 'verify')

        self._uri['perform'] = self._init_uri(confperf['uri'], confperf['path'])
        self._uri['cleanup'] = self._init_uri(confclean['uri'], confclean['path'])

    def more_info(self):  # pylint: disable=missing-docstring,no-self-use
        return ""

    def get_chall_pref(self, domain):
        # pylint: disable=missing-docstring,no-self-use,unused-argument
        return [challenges.HTTP01]

    def _build_uri(self, achall, xtype = 'perform'):   # pylint: disable=missing-docstring
        key = achall.chall.path
        uri = list(self._uri[xtype])
        uri[3] = list(uri[3])

        if self._config[xtype]['param_challenge']:
            uri[3] += [(self._config[xtype]['param_challenge'], key)]
        elif uri[2]:
            uri[2] = "/%s" % ("%s%s" % (uri[2].strip('/'), key)).lstrip('/')
        else:
            uri[2] = key

        return urisup.uri_help_unsplit(uri)

    def perform(self, achalls):  # pylint: disable=missing-docstring
        responses = []
        for achall in achalls:
            responses.append(self._perform_single(achall))
        return responses

    def _perform_single(self, achall):  # pylint: disable=missing-docstring
        response, validation = achall.response_and_validation()
        method  = self._config['perform']['method'].lower()
        headers = {}
        data    = None
        json    = None

        if method not in PERFORM_ALLOWED_HTTP_METHODS:
            raise errors.PluginError("Invalid HTTP method for perform: %s" % method)

        if self._config['perform']['param_validation']:
            data = {self._config['perform']['param_validation']: validation}
        else:
            data = validation

        if isinstance(self._config['perform'].get('headers'), dict):
            headers = dict(self._config['perform']['headers'])

        if self._config['perform']['format'] == 'json':
            headers['Content-Type'] = 'application/json'
            json = data
            data = None

        req = getattr(requests, method)(self._build_uri(achall, 'perform'),
                                        headers = headers,
                                        data    = data,
                                        json    = json,
                                        timeout = self._config['perform']['timeout'],
                                        verify  = self._config['perform']['verify'])

        req.raise_for_status()

        if response.simple_verify(
                achall.chall, self._uri['perform'][1][2],
                achall.account_key.public_key(), self._uri['perform'][1][3] or self.config.http01_port):
            return response

        LOG.error("Self-verify of challenge failed, authorization abandoned!")
        return None

    def cleanup(self, achalls):
        # pylint: disable=missing-docstring,no-self-use,unused-argument
        method  = self._config['cleanup']['method'].lower()
        headers = {}

        if method not in CLEANUP_ALLOWED_HTTP_METHODS:
            raise errors.PluginError("Invalid HTTP method for cleanup: %s" % method)

        if isinstance(self._config['cleanup'].get('headers'), dict):
            headers = dict(self._config['cleanup']['headers'])

        if self._config['cleanup']['format'] == 'json':
            headers['Content-Type'] = 'application/json'

        for achall in achalls:
            req = getattr(requests, method)(self._build_uri(achall, 'cleanup'),
                                            headers = headers,
                                            timeout = self._config['cleanup']['timeout'],
                                            verify  = self._config['cleanup']['verify'])

            req.raise_for_status()

        return None
