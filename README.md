# ACME HTTP Connector

Connect ACME clients to your HTTP APIs.

**Current adapter: Certbot. Adapter 0.0.22, core 0.1.1.**
Previously named **certbot-httpreq**. The repository now builds two packages:
`acme-http-connector` is the client-independent core; `certbot-httpreq` is the
Certbot adapter and installs the core as a dependency. Certbot plugin names
remain unchanged for compatibility. Other clients are planned,
not implemented; see [ROADMAP.md](ROADMAP.md).

The authenticator publishes and removes **HTTP-01** challenges through a custom
HTTP endpoint. The installer sends a certificate, private key and chain to an
API on issuance and renewal. Certbot performs ACME issuance; this plugin does
not run an ACME server or HTTP challenge server.

## Installation

Python 3.10+ and Certbot 2.11–5.x are the supported target range. CI checks Certbot
2.11 and the latest available 5.x. Install the plugin in the **same Python
environment** as Certbot; a separate pip environment does not extend a snap.

```sh
python -m pip install certbot-httpreq
certbot plugins
```

PyPI installation uses the last published release. To install from a source checkout:

```sh
python -m pip install -e packages/core -e .
```

## Core API

The core can be installed independently of Certbot:

```sh
python -m pip install acme-http-connector
```

It exposes `HTTPConnector.publish`, `cleanup`, `deploy` and `deploy_files`.
See [the core API example](packages/core/README.md). Other ACME client adapters
remain planned; installing the core alone does not issue certificates.

## Usage

Copy [certbot-httpreq.yml](certbot-httpreq.yml) to
`/etc/letsencrypt/certbot-httpreq.yml` and configure your API endpoints.

```sh
certbot run \
  --agree-tos --text --email admin@example.com \
  -a certbot-httpreq:auth \
  -i certbot-httpreq:installer \
  -d example.com
```

A different config file can be selected with
`--certbot-httpreq:auth-config` and `--certbot-httpreq:installer-config`, or
`CBT_HTTPREQ_AUTH_CONFIG` and `CBT_HTTPREQ_INST_CONFIG`.

The receiving service must expose the published challenge at
`http://example.com/.well-known/acme-challenge/<token>` for ACME validation.
The plugin also checks the challenge against the configured `perform.uri`
host and its explicit port (otherwise Certbot's HTTP-01 port), so that route
must serve the challenge too. The API write route and challenge read route
need not be the same.

## Configuration

Each phase (`perform`, `cleanup`, `deploy`) has its own `uri`, `path`, `method`,
`headers`, `format`, `timeout` and `verify` options.

| Phase | Methods | Payload |
| --- | --- | --- |
| `perform` | PUT, POST | Challenge validation, optionally under `param_validation` |
| `cleanup` | DELETE, PUT, POST | Challenge path in URL; no request body |
| `deploy` | POST, PUT, PATCH | `domain`, `cert`, `key`, `chain` |

- `format`: `json` or `form-urlencoded`.
- `param_challenge`: optional query parameter name receiving the **full challenge path**, including `/.well-known/acme-challenge/`. Otherwise that path is appended to the configured API path.
- `param_validation`: optional body field name; without it JSON sends a string and form mode sends raw validation text.
- `body_params` in `deploy`: overrides the four deployment field names.
- `headers`: custom headers, including API authentication headers if needed.
- `timeout`: positive finite seconds, default **30**. This is Requests' socket timeout, not a total operation deadline.
- `verify`: default **true**; a CA bundle path is also supported. Explicit `false` disables TLS certificate verification.

Scalar settings can be supplied using `CBT_HTTPREQ_<PHASE>_<OPTION>`, for example
`CBT_HTTPREQ_DEPLOY_TIMEOUT=15`. Explicit nonempty YAML values take precedence;
missing/null values use environment values, then defaults. Environment timeout
values are parsed as numbers; verification accepts true/false, yes/no, on/off,
1/0 or a CA bundle path. Headers and body mappings are configured in YAML.

Use HTTPS for remote APIs, particularly deployment: the payload contains the
private key. Protect the YAML file if it contains authentication headers.

## Renewal

```sh
certbot renew --dry-run
certbot renew
```

Run dry runs against a test API first: challenge publication and cleanup are
real API calls. Deployment uses the first certificate name as `domain`, with
the complete certificate (including any SANs). HTTP errors propagate to Certbot.

## Compatibility changes in 0.0.20

Existing package/plugin names, paths, environment variables and deployment
fields are retained. Python 2 and old Certbot interfaces are retired. Unset
HTTP timeouts now default to 30 seconds; cleanup honors its own settings;
invalid HTTP methods raise an error. See [CHANGELOG](CHANGELOG).

## Development

```sh
python -m pip install -e packages/core -e . pytest build
python -m pytest
python -m build packages/core
python -m build
certbot plugins
```

Copyright © 2019–2026 Adrien Delle Cave. GPL-3.0-or-later.

## Publishing (maintainers)

GitHub Actions builds both distributions, publishes **acme-http-connector**
first, then publishes **certbot-httpreq** using PyPI Trusted Publishing.
Before the first core release, register a pending publisher on PyPI for the
new project `acme-http-connector`. Both projects use these exact values:

| Setting | Value |
| --- | --- |
| Owner | `decryptus` |
| Repository | `acme-http-connector` |
| Workflow | `publish.yml` |
| Environment | `pypi` |

The core version lives in `packages/core/pyproject.toml`. Release both packages
together when changing the core, and keep the adapter dependency range current.
The core version must be new on PyPI for this two-package release workflow.

For a release, first synchronize `VERSION`, `RELEASE` and `setup.yml`, finalize
the top `CHANGELOG` entry (replace `UNRELEASED` with `unstable`) and update the
README's development status. Merge those changes, then publish a non-prerelease
GitHub Release tagged `v<version>` at that commit. The workflow checks version
consistency, runs tests, builds and validates distributions, then uploads the
same artifacts in a separate OIDC-enabled job.

A manual **Run workflow** only builds and validates; it never publishes.
Pull requests changing the publishing workflow also validate without uploading
to PyPI.
