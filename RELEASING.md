# Releasing

Sproutwall is an early preview. This page says how preview releases are numbered, how one is made, and which versions get security fixes. The full release process (automated version bumps, a changelog, versioned image tags) comes later, and this page will change with it.

## Version numbers

- A preview version looks like `0.1.0-preview.0`. The number after `preview.` goes up with each new preview release.
- The version lives in `package.json`. The app returns it from `/api/health`, and the image carries it in its `org.opencontainers.image.version` label.
- The Git tag is the version with a `v` in front, for example `v0.1.0-preview.0`.

## What a preview release is

A preview release is a GitHub pre-release, made by hand by a maintainer. It ties three things together:

- **The source commit.** The tag points at the commit that the published image was built from.
- **The image.** The release notes give the image's multi-arch index digest. The `:preview` tag moves with every push to `main`, so the digest, not the tag, identifies the release.
- **The install guide.** [INSTALL-WITH-AI.md](INSTALL-WITH-AI.md) pins the same commit and digest, and so does the one-command install, [install.sh](install.sh).

The notes also give the `verify-image` command for that pair.

## Making a preview release

1. Pick a run of the **Preview image** workflow on `main`. Copy its source commit and image index digest from the run's Summary page.
2. Run the maintainer checks in [docs/install-cli.md](docs/install-cli.md) against that pair, including `scripts/sproutwall verify-image`.
3. If the version in `package.json` at that commit has already been released, bump it in a pull request first, wait for the new image, and start again from step 1.
4. Pin the pair in the install guide and in `install.sh` (its two `PINNED_` values at the top), together in one pull request. The maintainer note at the top of INSTALL-WITH-AI.md says how. `scripts/tests/test_install_sh.py` fails if the two disagree.
5. Create a draft pre-release: tag `v<version>`, the source commit as its target, marked as a pre-release. Write the notes as described above.
6. Publish the draft when the maintainers agree to.

## Security fixes

During the preview, only the newest preview release gets security fixes. A fix ships as a new preview release; older previews are not patched. To report a vulnerability, follow [SECURITY.md](SECURITY.md).
