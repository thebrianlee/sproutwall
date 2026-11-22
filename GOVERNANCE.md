# Governance

Sproutwall is a small open-source project. This page says who decides what, and how a change gets into `main`.

## People and accounts

| Who | Role |
| --- | --- |
| [@thebrianlee](https://github.com/thebrianlee) | Founder and repository owner. Product direction and repository settings. |
| [@hjunk](https://github.com/hjunk) | Maintainer. Writes and reviews code, merges pull requests and cuts releases. |

## How a change gets into `main`

Every change is a pull request. `main` is protected:

- the `check` CI job must pass, on a branch that is up to date with `main`;
- pull requests are squash-merged, so history stays linear;
- every review conversation must be resolved before merging;
- nobody can force-push to `main` or delete it.

GitHub does not require an approval. @hjunk reviews pull requests from contributors and Dependabot before he merges them; that is a project rule, not something GitHub enforces.

## Decisions

- **Code, reviews and merges:** @hjunk.
- **Product direction, naming, licensing and repository settings:** @thebrianlee and @hjunk together.
- **Changes to this file:** both of them. @hjunk makes the change; @thebrianlee's agreement is a project rule.

## Releases

@hjunk cuts releases. [RELEASING.md](RELEASING.md) describes how versions are numbered, how a release is made and which versions get security fixes.

## Becoming a maintainer

Contribute for a while and review other people's pull requests carefully. The maintainers may then invite you. A new maintainer gets write access and is added to `.github/CODEOWNERS`.
