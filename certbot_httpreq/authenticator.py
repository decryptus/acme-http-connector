# -*- coding: utf-8 -*-
# Copyright 2019-2026 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""HTTP Requests Let's Encrypt authenticator plugin."""
import os
import logging

from acme import challenges

from sonicprobe import helpers

from certbot import interfaces
from certbot.plugins import common

from acme_http_connector import HTTPConnector
from certbot_httpreq.config import set_option, plugin_errors


LOG = logging.getLogger("certbot-httpreq")


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

    _set_option = staticmethod(set_option)

    def prepare(self):
        with plugin_errors():
            self._connector = HTTPConnector(helpers.load_conf_yaml_file(self.conf('config')),
                                            phases=('perform', 'cleanup'))
        self._config = self._connector.config

    def more_info(self):  # pylint: disable=missing-docstring,no-self-use
        return ""

    def get_chall_pref(self, domain):
        # pylint: disable=missing-docstring,no-self-use,unused-argument
        return [challenges.HTTP01]

    def _build_uri(self, achall, xtype='perform'):
        return self._connector.challenge_uri(achall.chall.path, xtype)

    def perform(self, achalls):  # pylint: disable=missing-docstring
        responses = []
        for achall in achalls:
            responses.append(self._perform_single(achall))
        return responses

    def _perform_single(self, achall):  # pylint: disable=missing-docstring
        response, validation = achall.response_and_validation()
        with plugin_errors():
            self._connector.publish(achall.chall.path, validation)
        host, port = self._connector.verification_address(self.config.http01_port)

        if response.simple_verify(
                achall.chall, host, achall.account_key.public_key(), port):
            return response

        LOG.error("Self-verify of challenge failed, authorization abandoned!")
        return None

    def cleanup(self, achalls):
        with plugin_errors():
            for achall in achalls:
                self._connector.cleanup(achall.chall.path)
