# Contributor documentation

This guide is for people changing or maintaining acme-http-connector. For installation, configuration and everyday use, start with the [user documentation](https://github.com/decryptus/acme-http-connector/blob/master/README.md).

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


## Documentation rules

Keep user instructions and contributor material separate. The repository [engineering requirements](https://github.com/decryptus/acme-http-connector/blob/master/AGENTS.md) define the review and validation rules. Preserve user-facing compatibility, security and recovery guidance when moving internal explanations.
