# -*- coding: utf-8 -*-
# Copyright 2019-2026 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""HTTP Requests Let's Encrypt installer plugin."""

import os
import logging

from sonicprobe import helpers

from certbot import interfaces
from certbot.plugins import common

from acme_http_connector import HTTPConnector
from certbot_httpreq.config import set_option, plugin_errors

LOG = logging.getLogger("certbot-httpreq")


class Installer(common.Plugin, interfaces.Installer):
    description = "HTTP Requests Installer"

    @classmethod
    def add_parser_arguments(cls, add):
        add("config",
            default = os.getenv('CBT_HTTPREQ_INST_CONFIG') or '/etc/letsencrypt/certbot-httpreq.yml',
            help    = "Path to certbot-httpreq configuration file")

    def __init__(self, *args, **kwargs):
        super(Installer, self).__init__(*args, **kwargs)
        self._config = {}

    _set_option = staticmethod(set_option)

    def prepare(self):
        with plugin_errors():
            self._connector = HTTPConnector(helpers.load_conf_yaml_file(self.conf('config')),
                                            phases=('deploy',))
        self._config = self._connector.config

    def more_info(self):  # pylint: disable=missing-docstring,no-self-use
        return "Installer send certificates to a custom HTTP endpoint"

    def get_all_names(self):  # pylint: disable=missing-docstring,no-self-use
        return []  # pragma: no cover

    def deploy_cert(self, domain, cert_path, key_path, chain_path, fullchain_path):
        with plugin_errors():
            self._connector.deploy_files(domain, cert_path, key_path, chain_path)

    def enhance(self, domain, enhancement, options=None):  # pylint: disable=missing-docstring,no-self-use
        pass  # pragma: no cover

    def supported_enhancements(self):  # pylint: disable=missing-docstring,no-self-use
        return []  # pragma: no cover

    def get_all_certs_keys(self):  # pylint: disable=missing-docstring,no-self-use
        pass  # pragma: no cover

    def save(self, title=None, temporary=False):  # pylint: disable=no-self-use
        pass  # pragma: no cover

    def rollback_checkpoints(self, rollback=1):  # pylint: disable=missing-docstring,no-self-use
        pass  # pragma: no cover

    def recovery_routine(self):  # pylint: disable=missing-docstring,no-self-use
        pass  # pragma: no cover

    def view_config_changes(self):  # pylint: disable=missing-docstring,no-self-use
        pass  # pragma: no cover

    def config_test(self):  # pylint: disable=missing-docstring,no-self-use
        pass  # pragma: no cover

    def restart(self):  # pylint: disable=missing-docstring,no-self-use
        pass  # pragma: no cover

    def renew_deploy(self, lineage, *args, **kwargs): # pylint: disable=missing-docstring,no-self-use,unused-argument
        """
        Renew certificates when calling `certbot renew`
        """
        self.deploy_cert(lineage.names()[0], lineage.cert_path, lineage.key_path, lineage.chain_path, lineage.fullchain_path)


interfaces.RenewDeployer.register(Installer)
