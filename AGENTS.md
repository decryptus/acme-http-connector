# Working on ACME HTTP Connector

- Keep the core independent of Certbot and the ACME protocol implementation.
  Preserve existing Certbot plugin names and configuration compatibility.
- Use `unittest`. Before reporting results, verify discovery with
  `python .github/scripts/check-test-collection.py --runner unittest tests/core tests/certbot`.
  Run both suites explicitly; a passing empty or partially collected suite is not validation.
- Check the standalone core without Certbot. For client hook changes, run the
  disposable Pebble integration check documented in README.md. Do not disable
  ACME validation to make integration tests pass.
- Keep README.md, both package descriptions, ROADMAP.md and CHANGELOG consistent
  with the implemented behavior and the published/development versions.
- Give Adrien the review and test results before merging, publishing a release
  or deploying. Wait for his explicit approval after that review. Preparing a
  branch or pull request is allowed; it does not authorize publication.
- Do not use production domains, containers or credentials for tests. Never
  commit private keys, account state or sensitive operational logs.
