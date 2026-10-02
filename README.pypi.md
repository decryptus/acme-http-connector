# ACME HTTP Connector · Certbot adapter

**Publish HTTP-01 challenges and deploy your Certbot certificates through an HTTP API.**

[![PyPI](https://img.shields.io/pypi/v/certbot-httpreq.svg)](https://pypi.org/project/certbot-httpreq/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://pypi.org/project/certbot-httpreq/)
[![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)](https://github.com/decryptus/acme-http-connector/blob/master/LICENSE)

[Documentation](https://github.com/decryptus/acme-http-connector#configuration) · [Source code](https://github.com/decryptus/acme-http-connector) · [Issues](https://github.com/decryptus/acme-http-connector/issues) · [Independent core](https://pypi.org/project/acme-http-connector/)

## What it does

`certbot-httpreq` adds two plugins to Certbot. Together they connect certificate
issuance and renewal to your existing HTTP services.

| Plugin | Role |
| --- | --- |
| `certbot-httpreq:auth` | Publish and clean up HTTP-01 challenges through your API |
| `certbot-httpreq:installer` | Send the certificate, private key and chain to your deployment API |

The project is now called **ACME HTTP Connector**. The package name, plugin names
and configuration options are preserved for existing Certbot installations.

## Installation

Requires **Python 3.10+** and **Certbot 2.11–5.x**. Install in the same Python
environment as Certbot; a separate pip environment does not extend a snap installation.

```bash
python -m pip install certbot-httpreq
certbot plugins
```

The independent [`acme-http-connector`](https://pypi.org/project/acme-http-connector/)
core is installed automatically. Adapter **0.0.24** uses core **0.2.x**.

**Using Dehydrated?** Install only `acme-http-connector` and use its
`acme-http-dehydrated` HTTP-01 hook; Certbot is not required. See the
[Dehydrated guide](https://github.com/decryptus/acme-http-connector#dehydrated-usage).

## Quick start

### 1. Configure your endpoints

Save the following as `/etc/letsencrypt/certbot-httpreq.yml`, replacing the
example URLs with your own services:

```yaml
perform:
  uri: https://api.example.com
  path: /challenges
  method: PUT
  format: json
  param_validation: value

cleanup:
  uri: https://api.example.com
  path: /challenges
  method: DELETE

deploy:
  uri: https://api.example.com
  path: /certificates
  method: POST
  format: json
```

TLS verification is enabled and the socket timeout is 30 seconds by default.
Each section can override `headers`, `timeout` and `verify` independently.

### 2. Request a certificate

```bash
certbot run \
  --agree-tos --text --email admin@example.com \
  -a certbot-httpreq:auth \
  -i certbot-httpreq:installer \
  -d example.com
```

Your API must publish the challenge at
`http://example.com/.well-known/acme-challenge/<token>`.
The adapter also verifies it against the host in `perform.uri` and its explicit
port, or Certbot's HTTP-01 port. That host must serve the challenge too.

### 3. Renew

```bash
certbot renew
```

Certbot invokes the configured plugins for challenge handling and certificate
deployment. Deployment sends the first certificate name as `domain` and includes
the complete certificate, including its additional names.

Use `certbot renew --dry-run` with a test API first: challenge publication and
cleanup still make real HTTP requests.

## Configuration

| Need | Setting |
| --- | --- |
| Custom config file | `--certbot-httpreq:auth-config` and `--certbot-httpreq:installer-config` |
| API authentication | `headers` in each phase |
| Challenge path as a query parameter | `param_challenge` |
| Named key authorization field | `param_validation` |
| Custom deployment field names | `body_params` under `deploy` |
| Custom TLS trust store | CA bundle path in `verify` |
| Environment overrides | `CBT_HTTPREQ_<PHASE>_<OPTION>` |

See the [full configuration reference](https://github.com/decryptus/acme-http-connector#configuration)
and [complete example file](https://github.com/decryptus/acme-http-connector/blob/master/certbot-httpreq.yml).
Use HTTPS for remote deployment and protect API credentials: certificate payloads
include the private key.

## Compatibility

Existing commands, plugin names, YAML settings and environment variables continue
to work. Since version 0.0.21, the shared HTTP transport lives in the independent
core package. Certbot handles ACME issuance; the connector handles your HTTP APIs.

## Project

[Report an issue](https://github.com/decryptus/acme-http-connector/issues) · [Release history](https://github.com/decryptus/acme-http-connector/releases) · [Roadmap](https://github.com/decryptus/acme-http-connector/blob/master/ROADMAP.md)

Copyright © 2019–2026 Adrien Delle Cave. Licensed under **GPL-3.0-or-later**.


HTTP redirects are refused for publish, cleanup and deployment. Configure the final
API URL directly; redirects do not trigger another request or count as success.
