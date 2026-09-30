# Copyright 2019-2026 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""Translate core configuration errors to Certbot plugin errors."""
from contextlib import contextmanager
from certbot import errors
from acme_http_connector import ConfigurationError
from acme_http_connector.config import DEFAULT_TIMEOUT, set_option as core_set_option


@contextmanager
def plugin_errors():
    try:
        yield
    except ConfigurationError as exc:
        raise errors.PluginError(str(exc)) from exc


def set_option(conf, xtype, name, default=None):
    with plugin_errors():
        core_set_option(conf, xtype, name, default)
