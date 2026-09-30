# ACME HTTP Connector

A Python library for publishing HTTP-01 challenges and deploying certificates
through existing HTTP APIs. Python 3.10+. No Certbot or ACME protocol dependency.
This library does not issue certificates or serve challenges itself.

```python
from acme_http_connector import HTTPConnector

connector = HTTPConnector({
    "perform": {"uri": "https://api.example.com", "path": "/challenges"},
    "cleanup": {"uri": "https://api.example.com", "path": "/challenges"},
    "deploy": {"uri": "https://api.example.com", "path": "/certificates"},
})
challenge_path = "/.well-known/acme-challenge/TOKEN"
connector.publish(challenge_path, "TOKEN.ACCOUNT_THUMBPRINT")
# The ACME client validates the challenge before cleanup.
connector.cleanup(challenge_path)
connector.deploy_files("example.com", "cert.pem", "key.pem", "chain.pem")
```

`publish(path, validation)` and `cleanup(path)` accept the full challenge path.
`deploy(domain, cert, key, chain="")` accepts PEM strings; `deploy_files` reads
files and accepts an optional chain path. Successful operations return `None`.
Configuration errors raise `ConfigurationError`; Requests HTTP/network errors
and filesystem errors propagate. The caller handles ACME issuance, challenge
validation, retries and cleanup timing.

`HTTPConnector(config, phases=("perform", "cleanup", "deploy"))` can initialize
only selected phases; the Certbot adapters each initialize their own phases.

Configuration is copied and uses the existing `perform`, `cleanup`, `deploy`
sections and `CBT_HTTPREQ_<PHASE>_<OPTION>` environment variables. Timeout defaults
to 30 seconds and TLS verification is enabled by default. Use HTTPS and protect
credentials: deployment sends the private key.

See the [repository documentation](https://github.com/decryptus/acme-http-connector)
for all configuration options and the `certbot-httpreq` adapter.

Copyright © 2019–2026 Adrien Delle Cave. GPL-3.0-or-later.
