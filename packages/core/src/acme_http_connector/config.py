# Copyright 2019-2026 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared configuration normalization for HTTP API connectors."""
import math
import os

from .errors import ConfigurationError

DEFAULT_TIMEOUT = 30.0


def set_option(conf, xtype, name, default=None):
    """Preserve explicit YAML values; normalize environment/network options."""
    value = conf.get(name)
    if value is None or value == '':
        value = os.getenv("CBT_HTTPREQ_%s_%s" % (xtype.upper(), name.upper()))
        if value is None or value == '':
            value = default
    if name == 'timeout':
        try:
            if isinstance(value, bool):
                raise ValueError()
            value = DEFAULT_TIMEOUT if value is None else float(value)
            if not math.isfinite(value) or value <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise ConfigurationError("%s.timeout must be a positive finite number" % xtype)
    elif name == 'verify':
        if value is None:
            value = True
        elif isinstance(value, str):
            normalized = value.lower()
            if normalized in ('true', '1', 'yes', 'on'):
                value = True
            elif normalized in ('false', '0', 'no', 'off'):
                value = False
            # Other strings are requests-compatible CA bundle paths.
        elif not isinstance(value, bool):
            raise ConfigurationError("%s.verify must be a boolean or CA bundle path" % xtype)
    conf[name] = value
