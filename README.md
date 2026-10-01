# ACME HTTP Connector

Connect ACME clients to your HTTP APIs.

**Core 0.2.0 · Certbot adapter 0.0.23 · Certbot and Dehydrated support.**
Previously named **certbot-httpreq**. The repository builds two packages:
`acme-http-connector` is the client-independent core; `certbot-httpreq` is the
Certbot adapter and installs the core as a dependency. Certbot plugin names
remain unchanged. The core includes the Dehydrated HTTP-01 hook and can be
installed without Certbot. See [ROADMAP.md](https://github.com/decryptus/acme-http-connector/blob/master/ROADMAP.md).

The authenticator publishes and removes **HTTP-01** challenges through a custom
HTTP endpoint. The installer sends a certificate, private key and chain to an
API on issuance and renewal. Certbot or Dehydrated performs ACME issuance;
this connector does not run an ACME server or HTTP challenge server.

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
See [the core API example](https://github.com/decryptus/acme-http-connector/blob/master/packages/core/README.md). The core also installs
`acme-http-dehydrated`, a hook for Dehydrated; Certbot is not required for it.
Installing the core alone does not issue certificates.

## Certbot usage

Copy [certbot-httpreq.yml](https://github.com/decryptus/acme-http-connector/blob/master/certbot-httpreq.yml) to
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

## Dehydrated usage

The installed `acme-http-dehydrated` command supports Dehydrated **0.7.2** with
**HTTP-01**. It publishes and cleans challenges, including `HOOK_CHAIN=yes`
batches, and sends the issued leaf certificate, private key and chain to the
same deployment API. It does not implement DNS-01 or TLS-ALPN-01.

Install the core in its own environment (no Certbot dependency):

```sh
python3 -m venv /opt/acme-connector
/opt/acme-connector/bin/python -m pip install acme-http-connector
```

Install Dehydrated separately. Copy [certbot-httpreq.yml](https://github.com/decryptus/acme-http-connector/blob/master/certbot-httpreq.yml)
to `/etc/acme-http-connector.yml` and configure your API endpoints. Restrict
access to configuration and certificate files to the account running the client.
The API must expose each challenge on the requested domain's HTTP-01 URL.

Add these settings to your Dehydrated configuration:

```sh
CHALLENGETYPE="http-01"
HOOK="/opt/acme-connector/bin/acme-http-dehydrated"
HOOK_CHAIN="yes"
WELLKNOWN="/var/lib/dehydrated/challenges"
```

Create `WELLKNOWN` as a directory writable by the Dehydrated account: the client
still writes its local token files even though the hook publishes them remotely.
Keep your usual `BASEDIR`, `DOMAINS_TXT`, account and CA settings. Put the desired
certificate names in Dehydrated's `domains.txt`, then register and issue:

```sh
dehydrated --register --accept-terms
dehydrated --cron
```

Subsequent `--cron` runs renew certificates when due. Test with a staging CA
and test API before production: staging certificates are also sent to the API.
A custom YAML path can be selected with `ACME_HTTP_CONNECTOR_CONFIG`; include
that environment variable in cron/service configuration too. The default is
`/etc/acme-http-connector.yml`. Existing `CBT_HTTPREQ_<PHASE>_<OPTION>` scalar
overrides also apply.

`deploy_cert` maps Dehydrated's key/cert/fullchain/chain arguments to the core's
cert/key/chain order. `unchanged_cert` does not deploy again. Unknown lifecycle
hooks succeed without action, as required by Dehydrated. Action hooks return
nonzero on invalid arguments, configuration, file or HTTP failures. Diagnostics
omit exception details because they can contain credentials. Check the affected
API and local configuration when a hook fails. A failed batch stops at the first
HTTP error; there is no automatic retry or rollback. An interrupted client or
partial API failure can leave published tokens requiring cleanup.

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
invalid HTTP methods raise an error. See [CHANGELOG](https://github.com/decryptus/acme-http-connector/blob/master/CHANGELOG).

## Development

```sh
python -m pip install -e packages/core -e . build twine
python .github/scripts/check-test-collection.py --runner unittest tests
python -m unittest discover -s tests -v
python -m build packages/core
python -m build
python -m pip install -r docs/requirements.txt
python -m sphinx -W --keep-going -b html docs docs/_build/html
certbot plugins
```

Tests use `unittest`. The collection guard checks that every declared test is
actually discovered, including the independent core suite without Certbot.

The CI matrix also tests installed wheels against **Pebble 2.10.1** and
**Dehydrated 0.7.2**, with real HTTP-01 validation. Each client issues and renews
a two-name certificate, cleans its tokens, deploys a matching certificate/key
and chain, and fails without deployment when HTTP-01 is unavailable. ACME TLS
verification remains enabled using an ephemeral local CA. These are local
integration tests, not evidence of compatibility with every production API or CA.

To reproduce on Linux x86-64 with the packages installed in the active environment:

```sh
bash .github/scripts/install-acme-test-tools.sh /tmp/acme-test-tools
python scripts/check_acme_clients.py \
  --pebble /tmp/acme-test-tools/pebble \
  --challtestsrv /tmp/acme-test-tools/pebble-challtestsrv \
  --dehydrated /tmp/acme-test-tools/dehydrated/dehydrated
```

Choose a new fixture directory for each installation. Fixture versions and binary
checksums are pinned. All network listeners bind to loopback; test domains use a
private test DNS resolver and all accounts/keys are disposable.

Copyright © 2019–2026 Adrien Delle Cave. GPL-3.0-or-later.
