# Roadmap

Keep the project small: connect ACME clients to existing HTTP APIs.

## 0.0.20 — maintenance and new project identity

- Preserve the `certbot-httpreq` package, plugin entry points, configuration path and environment variables.
- Fix cleanup settings, challenge URL state, typed configuration and build dependencies.
- Use explicit TLS verification and finite HTTP timeouts by default.
- Add regression tests and Certbot plugin discovery checks.
- Refresh documentation and copyright years.

## 0.0.21 adapter / 0.1.0 core — prepared, not published

- Extract request configuration and transport into `acme-http-connector`.
- Build and publish the core before the dependent `certbot-httpreq` adapter.
- Keep Certbot as a thin adapter with the existing public names.
- Define one small contract for challenge publication, cleanup and certificate deployment.

## Later — one integration at a time

- Add and document a Dehydrated hook adapter, with integration tests.
- Evaluate acme.sh and Lego adapters against their actual extension interfaces.
- Add DNS-01 only if a concrete use case requires it.

Only Certbot is supported today. No new ACME protocol implementation, server,
dashboard or orchestration service is planned here.
