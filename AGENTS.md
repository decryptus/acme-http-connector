# Working on ACME HTTP Connector

- Keep the core independent of Certbot and the ACME protocol implementation.
  Preserve existing Certbot plugin names and configuration compatibility.
- Use `unittest`. Before reporting results, verify discovery with
  `python .github/scripts/check-test-collection.py --runner unittest tests`.
  Run `python -m unittest discover -s tests -v`; a passing empty or partially collected suite is not validation.
- Check the standalone core without Certbot. For client hook changes, run the
  disposable Pebble integration check documented in docs/contributing.md. Do not disable
  ACME validation to make integration tests pass.
- Keep README.md, both package descriptions, ROADMAP.md and CHANGELOG consistent
  with the implemented behavior and the published/development versions.
- Build HTML documentation with warnings treated as errors before publication.
  The publishing workflow must rebuild docs and preserve the HTML artifact.
- Give Adrien the review and test results before merging, publishing a release
  or deploying. Wait for his explicit approval after that review. Preparing a
  branch or pull request is allowed; it does not authorize publication.
- Do not use production domains, containers or credentials for tests. Never
  commit private keys, account state or sensitive operational logs.

## Release maintenance

- Keep publication procedures and publisher configuration out of README.md and
  PyPI descriptions. These documents explain installation, configuration and use.
- Core version: `packages/core/pyproject.toml`. Adapter version: synchronize
  `VERSION`, `RELEASE` and `setup.yml`; keep its core dependency range current.
- Finalize the top CHANGELOG entry and release documentation before publication.
  Publish a non-prerelease GitHub Release tagged `v<adapter-version>` at the
  reviewed, approved merge commit. Both package versions must be new on PyPI.
- `publish.yml` rebuilds HTML documentation, validates distributions, publishes
  the core first, then the Certbot adapter. Manual dispatch only validates.

## Separate user and contributor documentation

- Maintain two distinct entry points and tables of contents: user documentation
  for installation, configuration, operation, public APIs and troubleshooting;
  contributor documentation for architecture, internals, tests, benchmarks,
  release engineering and development plans.
- Keep README and package descriptions focused on users. Link to the contributor
  guide instead of embedding maintainer procedures. Library API examples belong
  in the user guide when they are needed to integrate the library.
- Keep registry publishing, CI setup, repository secrets and maintainer account
  configuration out of user guides, website manuals and package descriptions.
  Never include credential values or private infrastructure evidence in either guide.
- Put implementation reviews and acceptance records under the contributor
  navigation. Preserve user-facing compatibility limits, migration instructions,
  security requirements and failure semantics in the user documentation.
- Apply this separation to generated documentation and FR/EN website content.
  Update source content and generators together; do not patch only generated HTML.
- Before delivery, inspect both entry points, check links and build documentation
  with warnings treated as errors where supported. Review README/package text and
  the deployed manual for accidental maintainer content. Preserve private-project
  visibility and existing review/publication approval requirements.

## Complete delivery and release synchronization

- Treat every delivery as a consistency check across the roadmap, PyPI packages,
  Docker Hub images and registry descriptions, repository/user/contributor
  documentation, demos, and existing product websites. Update every affected
  surface; a merged PR alone does not establish a completed delivery.
- Reconcile roadmap items with actual implementation and verified delivery.
  Distinguish planned, implemented, validated and published/deployed work; keep
  remaining limits and next steps explicit. Do not leave completed releases
  listed as pending or mark unverified work complete.
- For a release, publish the validated packages and images through the existing
  release gates, verify their versions/artifacts in the registries, and align
  installation commands, Compose examples, release notes and supported versions.
  Never overwrite an immutable published version to update its contents.
- Update affected documentation in every maintained language, including README,
  guides, examples, screenshots and diagrams. Keep user and contributor material
  separate and regenerate derived assets from the accepted source.
- Update existing demos and websites when affected, including source/image pins,
  visible versions, shared captures and release metadata. Validate the deployed
  result, links and relevant desktop/mobile flows; preserve private/public
  boundaries, credentials, data and the existing approval scope.
- Inspect applicability on every change. A documentation-only change does not
  require an artificial package/image release; a project without a registry,
  demo or website does not require inventing one. Record why a surface is
  unchanged, not applicable, blocked or explicitly deferred.
- Complete the authorized delivery work before reporting success. In the final
  handoff, distinguish merged code from registry publication and deployment,
  report checks performed, and list any required surface still not updated with
  its concrete blocker. Never imply that a planned publication already happened.
