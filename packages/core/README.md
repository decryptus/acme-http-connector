# ACME HTTP Connector

**Publish ACME challenges and deploy certificates through your HTTP APIs.**

[![PyPI](https://img.shields.io/pypi/v/acme-http-connector.svg)](https://pypi.org/project/acme-http-connector/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://pypi.org/project/acme-http-connector/)
[![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)](https://github.com/decryptus/acme-http-connector/blob/master/LICENSE)

[Documentation](https://github.com/decryptus/acme-http-connector#configuration) · [Source code](https://github.com/decryptus/acme-http-connector) · [Issues](https://github.com/decryptus/acme-http-connector/issues) · [Certbot adapter](https://pypi.org/project/certbot-httpreq/)

## What it does

ACME HTTP Connector connects your certificate automation to an existing HTTP API.
Use it to publish an **HTTP-01 challenge**, remove it after validation, and send
issued certificates to the service that needs them.

| Operation | What your API receives |
| --- | --- |
| Publish a challenge | The challenge path and key authorization text |
| Clean up a challenge | The challenge path to remove |
| Deploy a certificate | The domain, certificate, private key and optional chain |

The library works independently of Certbot. Your ACME client remains responsible
for requesting certificates and completing validation; your HTTP service exposes
the challenge to the certificate authority.

## Installation

Requires **Python 3.10 or newer**.

```bash
python -m pip install acme-http-connector
```

**Using Certbot?** Install [`certbot-httpreq`](https://pypi.org/project/certbot-httpreq/)
instead. It includes this library and provides the Certbot plugins.

## Dehydrated hook (prepared for 0.2.0)

The package installs `acme-http-dehydrated`, a Dehydrated **0.7.2** HTTP-01 hook
that publishes and cleans single or chained challenges and deploys issued
certificates. No Certbot installation is required. This feature is not in the
published core 0.1.1; install `./packages/core` from this branch to try it.

Set Dehydrated `HOOK` to the command's absolute path and
`CHALLENGETYPE="http-01"`. Configure API endpoints in
`/etc/acme-http-connector.yml`, or set `ACME_HTTP_CONNECTOR_CONFIG` to another YAML
path. See [Dehydrated setup](https://github.com/decryptus/acme-http-connector#dehydrated-usage-prepared-for-core-020)
for directory setup, issuance and renewal.

Unknown lifecycle hooks succeed without action. Action hooks return nonzero on
argument, configuration, file or HTTP errors; messages omit sensitive exception
details. Failed batches stop at the first HTTP error without automatic retry or
rollback. DNS-01 and TLS-ALPN-01 are not supported.

## Quick start

### 1. Connect your API

```python
from acme_http_connector import HTTPConnector

connector = HTTPConnector({
    "perform": {
        "uri": "https://api.example.com",
        "path": "/challenges",
        "param_validation": "value",
    },
    "cleanup": {
        "uri": "https://api.example.com",
        "path": "/challenges",
    },
    "deploy": {
        "uri": "https://api.example.com",
        "path": "/certificates",
    },
})
```

Replace the example endpoints with your own API. By default, publication uses
`PUT`, cleanup uses `DELETE`, and deployment uses `POST` with JSON payloads.

### 2. Publish and remove a challenge

Pass the **full challenge path** and key authorization supplied by your ACME client:

```python
challenge_path = "/.well-known/acme-challenge/TOKEN"
connector.publish(challenge_path, "TOKEN.ACCOUNT_THUMBPRINT")

# Run your ACME client's validation here, then remove the challenge.
connector.cleanup(challenge_path)
```

With the configuration above, the API receives a request at
`/challenges/.well-known/acme-challenge/TOKEN` with `{"value": "TOKEN.ACCOUNT_THUMBPRINT"}`.
Your service must make that value available at the domain's public HTTP-01 URL.

### 3. Deploy the issued certificate

```python
connector.deploy_files(
    domain="example.com",
    cert_path="cert.pem",
    key_path="privkey.pem",
    chain_path="chain.pem",
)
```

Already have the PEM contents in memory? Use
`connector.deploy(domain, cert, key, chain="")` instead. The chain is optional
in both methods.

## Configuration at a glance

Each operation has its own settings, so challenge publication and certificate
deployment can use different endpoints and credentials.

| Setting | Purpose | Default |
| --- | --- | --- |
| `uri`, `path` | API origin and request path | `http://localhost`; phase-specific path |
| `method` | HTTP method | `PUT` / `DELETE` / `POST` |
| `format` | JSON or form body | `json` |
| `headers` | Authentication and custom HTTP headers | None |
| `timeout` | Positive socket timeout in seconds | `30` |
| `verify` | TLS verification or CA bundle path | `true` |
| `param_challenge` | Send the full challenge path in a query parameter | Append to API path |
| `param_validation` | Wrap key authorization in a named body field | Send the text directly |
| `body_params` | Rename certificate deployment fields | `domain`, `cert`, `key`, `chain` |

See the [complete configuration reference](https://github.com/decryptus/acme-http-connector#configuration)
for allowed methods, environment variables and payload formats.

## Integration notes

- **No Certbot dependency.** Import `HTTPConnector` directly from Python or use
  the Dehydrated HTTP-01 hook. Other client adapters remain on the
  [roadmap](https://github.com/decryptus/acme-http-connector/blob/master/ROADMAP.md).
- **Explicit errors.** Invalid settings raise `ConfigurationError`. HTTP, network
  and file errors propagate to your application. Successful operations return `None`.
- **Configuration stays yours.** The library copies the supplied mapping. Use the
  `phases` argument to initialize only the operations your integration needs.
- **Protected transport by default.** TLS verification is enabled and requests have
  a 30-second socket timeout. Use HTTPS for remote deployment: it sends the private key.

## Project

[Report an issue](https://github.com/decryptus/acme-http-connector/issues) · [Release history](https://github.com/decryptus/acme-http-connector/releases) · [Roadmap](https://github.com/decryptus/acme-http-connector/blob/master/ROADMAP.md)

Copyright © 2019–2026 Adrien Delle Cave. Licensed under **GPL-3.0-or-later**.
