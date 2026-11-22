# Repository setup before going public

A checklist for the maintainer. Do these in GitHub's settings before you make the repository public. Each step says where to click and what to choose.

The files mentioned are already in the repository:

- The issue forms and the pull request template work as soon as they are on `main`.
- `.github/dependabot.yml` starts weekly update pull requests once it is on `main`.
- `.github/CODEOWNERS` asks the owner for reviews automatically. It does not block merges: the ruleset in section 2 requires no approval.
- `.github/workflows/image.yml` publishes a preview image after each push to `main`, once the one-time owner steps in section 9 are done.

GitHub moves settings around from time to time. If a name below does not match your screen exactly, look for the closest match on the same page.

## 1. Pull request merge options

Open **Settings → General → Pull Requests**.

- [ ] Turn **off** "Allow merge commits".
- [ ] Turn **on** "Allow squash merging".
- [ ] Turn **off** "Allow rebase merging".
- [ ] Turn **on** "Always suggest updating pull request branches".
- [ ] Turn **on** "Automatically delete head branches".

Squash-only keeps `main` as one commit per pull request, which matches the "Require linear history" rule below.

## 2. Ruleset for `main`

Open **Settings → Rules → Rulesets → New ruleset → New branch ruleset**.

- [ ] **Ruleset name:** `protect-main`
- [ ] **Enforcement status:** Active
- [ ] **Bypass list:** **Repository admin**, set to **For pull requests only**. The admin can then merge a pull request without its required check, but can never push straight to `main`. The admin uses it only for [Break-glass](#break-glass).
- [ ] **Target branches:** Add target → **Include default branch**

Turn on these rules:

- [ ] **Restrict deletions**
- [ ] **Require linear history**
- [ ] **Require a pull request before merging**, with:
  - [ ] Required approvals: **0** (see [Approvals](#approvals))
  - [ ] "Dismiss stale pull request approvals", "Require review from Code Owners" and "Require approval of the most recent reviewable push": **off**
  - [ ] **Require conversation resolution before merging**
  - [ ] Allowed merge methods: **Squash** only
- [ ] **Require status checks to pass**, with:
  - [ ] **Require branches to be up to date before merging**
  - [ ] Add the check **`check`** (source: GitHub Actions). That is the only job in `.github/workflows/ci.yml`. It runs lint, typecheck, tests, build, the PII check and the gitleaks secret scan.
- [ ] **Block force pushes**

Leave "Restrict updates" off. It would block merges too.

The `check` status shows up in the search box only after CI has run at least once. If you can't find it, open a test pull request first, then come back.

### Approvals

The ruleset requires no approval. GitHub never lets the author of a pull request approve it, and the project has one maintainer, so a required approval would block every pull request he opens. Instead, @hjunk reviews pull requests from contributors and Dependabot before he merges them ([GOVERNANCE.md](../../GOVERNANCE.md)). That is a project rule; GitHub enforces only a pull request for every change to `main`, the `check` status, squash merging, linear history, resolved conversations, and no force push or deletion.

When a second maintainer joins, consider Required approvals **1** with **Require review from Code Owners**, and add them to `.github/CODEOWNERS`.

### Break-glass

The repository owner (the only admin) merges with the bypass only in a real emergency, such as a security fix while the `check` job cannot run:

1. Open an issue titled "Break-glass: YYYY-MM-DD" (today's date) and write down why.
2. Merge the fix: `gh pr merge <N> --squash --admin --match-head-commit <SHA>`.
3. Add the merged commit to the issue and close it.

## 3. Security features

Open **Settings → Advanced Security** (on some accounts: "Code security and analysis").

- [ ] **Private vulnerability reporting:** Enable. `SECURITY.md` and the issue form point people here.
- [ ] **Dependency graph:** on.
- [ ] **Dependabot alerts:** Enable.
- [ ] **Dependabot security updates:** Enable.
- [ ] **Secret scanning** (may be called Secret Protection): Enable.
- [ ] **Push protection:** Enable. It blocks pushes that contain known secret formats.

Dependabot version updates are configured by `.github/dependabot.yml`: npm, GitHub Actions and Docker, weekly, with minor and patch updates grouped into one pull request per ecosystem.

## 4. GitHub Actions

Open **Settings → Actions → General**.

- [ ] **Actions permissions:** allow actions created by GitHub, plus `docker/*` actions. CI uses only `actions/checkout` and `actions/setup-node`. The image workflow (section 9) also uses `actions/attest-build-provenance` and four `docker/*` actions; section 9, step (a) says where to enter `docker/*`. If the page offers "Require actions to be pinned to a full-length commit SHA", turn it on.
- [ ] **Approval for running fork pull request workflows:** "Require approval for all external contributors".
- [ ] **Workflow permissions:** "Read repository contents and packages permissions" (read-only token). Keep it read-only: the image workflow asks for its write permissions in its own `permissions:` block (section 9, step (c)).
- [ ] Turn **off** "Allow GitHub Actions to create and approve pull requests".

Rules for future workflows:

- Declare the smallest `permissions:` block in every workflow, like `ci.yml` does. `image.yml` sets `permissions: {}` at the top and gives write access to its one job only.
- Pin third-party actions to a full commit SHA, with the version in a comment.
- Never use `pull_request_target` to run code from a fork.
- CI needs no repository secrets. Don't add personal access tokens as secrets.

## 5. Code owners

`.github/CODEOWNERS` makes the maintainer the owner of everything, and lists the sensitive paths again on their own lines: the access policy and auth code, `src/app/api/`, `bridge/`, Docker files, `scripts/`, `.github/` and `GOVERNANCE.md`. GitHub then asks him for a review on every pull request. With "Require review from Code Owners" off (section 2), the file requests reviews but does not block merges.

- [x] **Owners set.** Every path is owned by `@hjunk`, the maintainer. The PII check passes with this handle.
- [ ] Open `.github/CODEOWNERS` on GitHub. If GitHub shows an error at the top of the file (for example, an owner without write access), fix it.
- [ ] When you add a second maintainer or skill owners later, add them to the general rules, but keep the sensitive paths owned by core maintainers only.

## 6. A GitHub App for agents

Give AI agents a GitHub App instead of your personal token. An App has only the permissions you pick, its tokens expire after an hour, and its work shows up as `<app name>[bot]`.

Open **your profile picture → Settings → Developer settings → GitHub Apps → New GitHub App**.

- [ ] **Name:** for example `sproutwall-agent`.
- [ ] **Homepage URL:** the repository URL.
- [ ] **Webhook:** turn **off** "Active".
- [ ] **Repository permissions**, and nothing else:

  | Permission | Access |
  | --- | --- |
  | Contents | Read and write |
  | Issues | Read and write |
  | Pull requests | Read and write |
  | Metadata | Read-only (always on) |

  Leave everything else at **No access**, especially **Administration**, **Workflows**, **Secrets**, **Actions** and **Environments**. No organization or account permissions.
- [ ] **Where can this GitHub App be installed?** Only on this account.
- [ ] Create the App. Then **Install App** → choose **Only select repositories** → this repository.
- [ ] **Generate a private key.** Store the downloaded `.pem` file in the agent's secret store. Never commit it.

What keeps the App inside the rules:

- Only the repository admin can bypass the ruleset, and only for pull requests. The App cannot push to `main`; it can only push branches and open pull requests.
- Without the Workflows permission, GitHub refuses any push from the App that adds or changes files in `.github/workflows/`.
- Without Administration, it cannot change settings, rulesets or secrets.
- The ruleset requires no approval, so with these permissions the App could technically merge a pull request whose `check` passed. Merging is the maintainer's job ([CONTRIBUTING.md](../../CONTRIBUTING.md#ai-assisted-and-agent-authored-contributions)); if that is not enough, turn on Required approvals (section 2) before installing an App.
- It can still technically close issues or comment. The rules in [CONTRIBUTING.md](../../CONTRIBUTING.md#ai-assisted-and-agent-authored-contributions) say it must not close a human's issue or follow instructions found in issue text. Put those rules in the agent's own instructions, too.

Label every agent pull request `agent-authored`. Review it as carefully as a stranger's.

## 7. Labels

Open **Issues → Labels**, or run the commands below with the [GitHub CLI](https://cli.github.com/). `--force` updates a label that already exists.

| Label | Color | Use it for |
| --- | --- | --- |
| `good first issue` | `#7057ff` | Small, well-scoped work for a new contributor |
| `help wanted` | `#008672` | A pull request would be welcome |
| `bug` | `#d73a4a` | Something does not work as the screen says it should |
| `enhancement` | `#a2eeef` | Feature requests (the feature form applies it) |
| `security` | `#b60205` | Hardening that is safe to discuss in public. Vulnerabilities go to private advisories, never to an issue. |
| `skill/plugin` | `#5319e7` | The skills (plugin) system or a proposed skill |
| `docs` | `#0075ca` | Documentation |
| `pi/self-hosting` | `#c5def5` | Raspberry Pi, Docker and self-hosting |
| `needs-repro` | `#fbca04` | Waiting for steps to reproduce |
| `agent-authored` | `#1d76db` | An AI agent wrote most of this pull request; needs a human review |

Dependabot creates its own `dependencies` label.

```bash
gh label create "good first issue" --color 7057ff --description "Small, well-scoped work for a new contributor" --force
gh label create "help wanted"      --color 008672 --description "A pull request would be welcome" --force
gh label create "bug"              --color d73a4a --description "Something does not work as the screen says it should" --force
gh label create "enhancement"      --color a2eeef --description "Feature request" --force
gh label create "security"         --color b60205 --description "Public hardening only; report vulnerabilities privately" --force
gh label create "skill/plugin"     --color 5319e7 --description "Skills (plugin) system or a proposed skill" --force
gh label create "docs"             --color 0075ca --description "Documentation" --force
gh label create "pi/self-hosting"  --color c5def5 --description "Raspberry Pi, Docker and self-hosting" --force
gh label create "needs-repro"      --color fbca04 --description "Waiting for steps to reproduce" --force
gh label create "agent-authored"   --color 1d76db --description "Written mostly by an AI agent; needs human review" --force
```

## 8. Seed good first issues

File these before going public, each with the labels shown. They are real gaps found in the code, checked again after the pre-launch branches merged.

### 1. Weather: add a Celsius option

Labels: `good first issue`, `enhancement`

The forecast request always asks Open-Meteo for Fahrenheit.

- **Files:** `src/lib/weather.ts` (`temperature_unit=fahrenheit`), `src/app/api/settings/route.ts` (`PUBLIC_KEYS`), `src/app/today/page.tsx`, `src/components/Ambient.tsx`.
- **Done when:**
  - a `temperature_unit` setting (`fahrenheit` or `celsius`) controls the request, and Fahrenheit stays the default for existing installs;
  - changing the unit does not show a cached value in the old unit;
  - a test covers the URL for both units.

### 2. Clock: add a 24-hour option

Labels: `good first issue`, `enhancement`

Both clocks format with `toLocaleTimeString("en-US", { hour: "numeric" ... })`, so they always show 12-hour time.

- **Files:** `src/app/today/page.tsx` (the clock), `src/components/Ambient.tsx` (the screensaver clock), `src/app/api/settings/route.ts`.
- **Done when:**
  - a `clock_24h` setting (`0` default) switches both clocks;
  - the README mentions it.

### 3. Keep the reset-pin rules in sync with the app

Labels: `good first issue`, `security`

`scripts/reset-pin.mjs` has its own copy of the PIN rules and blocked list. It matches `src/lib/weak-pin.ts` today, but nothing checks that it stays that way.

- **Files:** `scripts/reset-pin.mjs`, `src/lib/weak-pin.ts`, a new test in `tests/`.
- **Done when:**
  - the script's rule moves into a small module it imports (for example `scripts/pin-rules.mjs`) without changing its behavior;
  - a test runs at least 20 PINs (good, blocked, repeated, ascending, descending, too short, too long, non-digits) through both rules and expects the same answer.
- Touches PIN code, so it needs a maintainer review.

### 4. `GOOGLE_BOOKS_API_KEY` is documented but never read

Labels: `good first issue`, `bug`

`.env.example` and `docker-compose.yml` mention `GOOGLE_BOOKS_API_KEY`, but `src/lib/books.ts` calls Google Books without a key.

- **Files:** `src/lib/books.ts` (`searchGoogleBooks`), `.env.example`, `docker-compose.yml`.
- **Done when:** either the key is sent when set (and never logged), or the variable is removed from both files.

### 5. Balance page: keep it readable with many kids

Labels: `good first issue`

Setup allows up to 8 kids. Today and Ask switch to up to 4 columns, but the Balance page still stacks one card per kid in a single column, so with 5 or more kids the cards get cramped and the jar chart is hard to read on the wall screen.

- **Files:** `src/app/balance/page.tsx`, `src/components/KidRewards.tsx`.
- **Done when:**
  - with 1 to 3 kids the page looks the same as today;
  - with 4 to 8 kids every kid's balance and jar is readable on a 1920x1080 screen without scrolling sideways;
  - try it with "Set up my family" and 8 kids, and attach a screenshot to the PR.

### 6. Photos: say which files are skipped

Labels: `good first issue`, `bug`

The hub only shows `.jpg`, `.jpeg`, `.png` and `.webp` files whose names use letters, numbers, dots, dashes and underscores. Anything else in the photo folder, such as `Beach day.jpg` or a `.heic` file from a phone, is skipped without any message, so parents don't know why a photo is missing.

- **Files:** `src/app/api/ambient/route.ts` (`listImages`), `src/app/api/photos/[file]/route.ts`.
- **Done when:**
  - the server logs once, without file names, how many files it skipped and why;
  - a test in `tests/paths-and-covers.test.ts` covers a skipped name.

### 7. Night mode never dims on a fresh install

Labels: `good first issue`, `bug`

The sleep window (21:30 to 06:00, seeded in `src/lib/db.ts`) is supposed to darken the screen at night. But `src/app/api/ambient/route.ts` defaults `hardware_sleep` to `1`, which assumes a display power script that is not in this repository. So on a new install the app never shows its night overlay.

- **Files:** `src/app/api/ambient/route.ts`, `src/components/Ambient.tsx`, `src/lib/db.ts`.
- **Done when:**
  - new installs default to the app's own overlay (`hardware_sleep` = `0`), and installs that set `1` keep their behavior;
  - the comment about the power script is updated;
  - the pull request says how you tested it, for example by setting the sleep window to the next few minutes.

### 8. Test that the health check reveals nothing

Labels: `good first issue`, `security`

`/api/health` is open on a locked hub, for Docker's health check and the install helper (`scripts/sproutwall doctor`). On success (200) it must only ever say `ok`, the app `version`, the database `schema` number and `setup` (whether first-run setup is finished). On failure (503) it says `ok: false`, and when the database is blocked (`DbBlockedError` in `src/lib/db.ts`) also the block's `code` and its numeric details, nothing else. No test guards that.

- **Files:** `src/app/api/health/route.ts`, a new `tests/health.test.ts`.
- **Done when:**
  - a test calls the handler and expects status 200, a body with exactly the keys `ok` (`true`), `version`, `schema` and `setup`, and `cache-control: no-store`;
  - a test makes the database query fail and expects status 503 with a body of exactly `{ "ok": false }`;
  - a test makes the database blocked and expects status 503 with only `ok` (`false`), `code` and numeric fields.
- `tests/auth.test.ts` already checks that the proxy lets `/api/health` through, so this issue is only about the response body.

## 9. Preview image

Building Next.js on a Raspberry Pi is slow and needs a lot of memory. `.github/workflows/image.yml` builds the image once on GitHub, for both `amd64` and `arm64`, and publishes it to GitHub Container Registry (GHCR).

**What it publishes.** Preview images only:

- Two tags: `ghcr.io/thebrianlee/sproutwall:preview`, which moves to the newest build, and `ghcr.io/thebrianlee/sproutwall:preview-<short commit>` (the first 7 characters of the commit), which stays. No `latest` and no version tags.
- An SBOM and full build provenance (`provenance: mode=max`), stored in the image index.
- A GitHub build-provenance attestation (`actions/attest-build-provenance`). It is signed with this workflow's identity, stored on GitHub, and also pushed to GHCR next to the image, so a verifier can fetch it from the registry instead of from GitHub.
- OCI labels: `org.opencontainers.image.source` (this repository), `org.opencontainers.image.version` (from `package.json`) and `org.opencontainers.image.revision` (the commit).

It uses no repository secrets (only the built-in `GITHUB_TOKEN`) and no build arguments.

**When it runs.** On every push to `main` (each merged pull request), and by hand from **Actions → Preview image → Run workflow** on the `main` branch. It never runs for pull requests, and it publishes nothing from other branches or from forks. Only one run publishes at a time, and a running publish is never cancelled. If several pushes land during a build, only the newest waiting one runs next, so the commits in between get no `preview-<short commit>` tag.

**What to copy.** Each run's summary page (**Actions →** the run **→ Summary**) shows the image index digest and the source commit. Copy that pair into the install guide. Install files pin the image by that digest (`ghcr.io/thebrianlee/sproutwall:preview@sha256:...`), never by the moving `:preview` tag, and the verification checks the attestation against that commit. The verification names `.github/workflows/image.yml` as the signer workflow, so don't rename or move that file.

**Releases.** Previews are released as hand-made GitHub pre-releases. [RELEASING.md](../../RELEASING.md) says how they are numbered and made. The image itself still gets no version tags and no `latest`; those come with the full release process. The install guide pins one published preview by digest. The README's manual install and the Raspberry Pi guide still build locally with `docker compose up -d --build`.

### One-time owner steps

The repository owner does these once. Do step (a) **before the first run**: merging the pull request that adds `image.yml` is a push to `main`, so it starts the first run.

- [ ] **(a) Allow the `docker/*` actions, before the first run.** Open **Settings → Actions → General → Actions permissions** and choose "Allow thebrianlee, and select non-thebrianlee, actions and reusable workflows". Keep **Allow actions created by GitHub** checked, leave "Allow actions by Marketplace verified creators" unchecked, enter `docker/*` in **Allow or block specified actions and reusable workflows**, and save. If a run started before this, it failed at the start and published nothing: change the setting, then start the workflow by hand (**Actions → Preview image → Run workflow**).
- [ ] **(b) Make the package public, after the first successful run.** New GHCR packages start private, so only signed-in accounts with access can pull them. Open your profile → **Packages → sproutwall → Package settings**. Under **Danger Zone**, choose **Change visibility → Public**. If the package page does not show this repository as its source, use **Connect repository** on that page.
- [ ] **(c) Check that the workflow gets its permissions with the read-only default token.** Leave **Workflow permissions** read-only (section 4). In the first run, open the `image` job, expand **Set up job → GITHUB_TOKEN Permissions**, and check that it lists `Attestations: write`, `Contents: read`, `Metadata: read` and `Packages: write`, and nothing else. `id-token: write` does not appear in that list (checked on run 44596530739, attempt 2). The workflow still gets it: the **Attest build provenance** step can only sign with it, so that step succeeding is the check. If the push to GHCR fails with `denied`, a package named `sproutwall` may already exist without access for this repository: in that package's **Package settings → Manage Actions access**, add this repository with the **Write** role, then run the workflow again. Don't switch the default token to read and write.

Notes:

- The `arm64` half builds under emulation (QEMU), which is slow, and the job stops after 90 minutes. If that is too slow, GitHub's native `ubuntu-24.04-arm` runners are the alternative, at the cost of a matrix and a merge step.
- The `node:22-alpine` base image is not pinned by digest yet; see the comment at the top of the `Dockerfile`. Dependabot (Docker and GitHub Actions) keeps the base image and the pinned action SHAs current.
- `actions/attest-build-provenance` runs `actions/attest`, which it also pins to a full commit SHA, so "Require actions to be pinned to a full-length commit SHA" (section 4) does not block it.

## 10. Last checks before "Make public"

- [ ] CI is green on `main`.
- [ ] The secret scan has covered the whole history once. Old commits become public too. CI scans everything only when there is no earlier commit to compare against, for example on the first push of a branch. If unsure, run `gitleaks git --redact .` once in a local clone.
- [ ] Your private word list for the PII check is a repository secret named `PII_HASHES` (one sha256 hex digest per line), **not** a file in the repo. `scripts/pii-hashes.txt` is git-ignored: keep your local copy there or anywhere and point `PII_HASHES_FILE` at it. Unsalted hashes of short words such as names can be reversed, so the list must never be public.
- [ ] `node scripts/check-pii.mjs` passes on `main` with the list loaded.
- [ ] The labels from section 7 exist and the issues from section 8 are filed.
- [ ] Private vulnerability reporting is on: the **Security** tab shows **Report a vulnerability**. The "Report a security problem" link on the new-issue page explains how to use it.
- [ ] `.github/CODEOWNERS` names real owners (now `@hjunk`) and the PII check still passes (section 5).
- [ ] The ruleset shows **Active**, and a test pull request cannot be merged without the `check` status.
- [ ] **Backup and restore round trip.** The commands in the README's "Back up and update" section were written without a running Docker engine. On a test install, run the backup, change something (add a list item), run the restore, and check that the hub opens with the original family, data and PIN, and that `docker compose ps` says `healthy`.
- [ ] **Preview image** (section 9): the one-time owner steps are done, a run on `main` succeeded, and the GHCR package is public. The install guide pins a published, verified preview by digest. The README and the Raspberry Pi guide still build locally with `docker compose up -d --build`.
