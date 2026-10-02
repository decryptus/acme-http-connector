# Roadmap

Keep the project small: connect ACME clients to existing HTTP APIs.

## 0.0.20 — maintenance and new project identity

- Preserve the `certbot-httpreq` package, plugin entry points, configuration path and environment variables.
- Fix cleanup settings, challenge URL state, typed configuration and build dependencies.
- Use explicit TLS verification and finite HTTP timeouts by default.
- Add regression tests and Certbot plugin discovery checks.
- Refresh documentation and copyright years.

## 0.0.21 adapter / 0.1.0 core — shared HTTP connector

- Extract request configuration and transport into `acme-http-connector`.
- Build and publish the core before the dependent `certbot-httpreq` adapter.
- Keep Certbot as a thin adapter with the existing public names.
- Define one small contract for challenge publication, cleanup and certificate deployment.

## 0.0.22 adapter / 0.1.1 core — package documentation

- Improve both PyPI descriptions and link to the full configuration reference.

## 0.0.23 adapter / 0.2.0 core — Certbot and Dehydrated

- Add a Dehydrated 0.7.2 HTTP-01 hook with single and chained challenge support.
- Verify real issuance, renewal, deployment and validation failure with both clients against Pebble.
- Use unittest with explicit collection checks and a Certbot-free core suite.
- Rebuild HTML documentation during publication and validate both PyPI descriptions.

## Later — one integration at a time

- Evaluate acme.sh and Lego adapters against their actual extension interfaces.
- Add DNS-01 only if a concrete use case requires it.

The Certbot adapter and the core’s Dehydrated hook support HTTP-01. No new ACME protocol implementation, server,
dashboard or orchestration service is planned here.


## Unreleased hardening

- [x] Reject HTTP redirects in every connector phase; require the final API URL.
