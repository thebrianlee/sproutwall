<!--
MAINTAINER NOTE. Not part of the install. Assistants reading this file: skip this block.

1. The pinned pair. To move the guide to a newer preview build, open Actions, then
   "Preview image", then the run, then Summary. The job summary shows "Source commit" and
   "Image index digest". Run the maintainer checks in docs/install-cli.md against that build
   first. Then replace both values together everywhere in this file: the full 40-character
   source commit, and the multi-arch index digest with its sha256: prefix. They appear in the
   pinned-preview table, in step 3 and in step 4. Never mix values from two builds.
   Replace the same two values in install.sh too (PINNED_SOURCE_COMMIT and PINNED_IMAGE_DIGEST
   at its top), in the same pull request: scripts/tests/test_install_sh.py fails if install.sh
   and the table in this file differ.
   Leave the token published-index-digest-hex (in angle brackets, in step 4) as it is:
   it is the template token in docker-compose.preview.yml that the sed command in step 4
   replaces on the device. Never write a tag such as :preview in place of the digest.
   Each pinned pair also gets a GitHub pre-release at the same source commit. See RELEASING.md.

2. Open decisions:
   - Docker group. Spec 4.2 step 3 says the agent gets no membership in the docker group.
     In tiers A and B the person's account joins it and the agent runs as that account,
     so the agent can control Docker while it is installed. The guide states this as a
     known exception ("Known gap" under the install plan). Pending a maintainer decision.
   - Scope. The guided commands assume a Debian-family system (dpkg, apt, GitHub's Debian
     package repository). Supported: Raspberry Pi OS on Pi 4/5, and Debian or Ubuntu on
     amd64. Other 64-bit distributions are listed as should-work, with the tools installed
     from their own instructions.

3. Verified on 2026-11-19 against the pinned pair (run 44596530739, attempt 2):
   - On macOS with gh 2.86.0: anonymous GHCR access for verify-image (pull token,
     referrers, bundle download) and gh reading the image from the registry with no account;
     verify-image passes for the real pair; the attested subject is the index digest; a
     wrong source commit (exit 1) and a tampered digest (exit 4) fail; the committed
     template is refused (exit 2).
   - A VM trial of this guide (tier C, steps 2-6 and 8; household setup through the setup
     API rather than the screen) in a Debian 13 arm64 VM (Lima, no host mounts, loopback only): GitHub's apt repository installed arm64 gh 2.105.0;
     verify-image exit 0; the hub started healthy; setup finished; doctor passed every
     applicable check in all three phases except ssh_policy (the VM needs SSH) and the
     expected app_bind unknown; the household and the PIN lock survived a reboot.
   Not covered by the VM run: steps 1 and 7, a phone on the LAN, tiers A and B, and
   Raspberry Pi OS itself.

4. Not yet verified on real hardware or live services [미확인]:
   - A wrong signer workflow failing, live; the offline --trusted-root run; whether GHCR
     answers the bundle blob request with a redirect (the download worked, but this was not
     recorded).
   - GitHub's apt repository on Raspberry Pi OS (Bookworm and Trixie) itself.
   - Raspberry Pi Imager wording (customisation, key-only SSH) and that Imager keeps the
     public key's comment in authorized_keys. Step 8, tier B, removes the line by that
     comment; the fingerprint listing after it catches a miss.
   - Whether Raspberry Pi OS gives the first user sudo without a password. If it does,
     tier A relies on the assistant's rule never to run sudo.
   - sudo raspi-config nonint do_ssh 1 turns SSH fully off on current Raspberry Pi OS,
     including any socket activation, so doctor ssh_policy passes. On Debian and Ubuntu,
     the systemctl command in step 8 for ssh.socket and ssh.service does the same.
   - Tier A memory: the spec says an agent CLI on the device needs about 4 GB; confirm
     against the vendors' docs. Minimum RAM for the hub itself is not measured yet.
   - Agent removal (step 8, tier A) is not tested per CLI. The folder list comes from
     doctor's temporary_access check (scripts/sproutwall_lib/checks.py); the logout and
     uninstall commands are left to each vendor's own instructions.
   - The kiosk items in docs/install-cli.md, "Still to verify on real hardware".
   - Doctor's GET to the container address over Docker's bridge on the Pi.
   - The preview backup command in "Existing install / update" (stage 0.3 restore drill).
   - The supported-device list: Pi 4/5 are the intended path; the stage 1 hardware trials
     (T1, T2) have not run yet. Say "tested" only after they pass.
-->

# Install Sproutwall with an AI assistant

This guide puts Sproutwall on a Raspberry Pi, or on another 64-bit computer running Debian or Ubuntu, and ends with the hub on your kitchen screen. An AI assistant can walk you through it, or you can follow the same steps by hand.

> **AI assistants, read this first.** Whether the person is at the device's own Terminal (you are a chat-only AI, tier C, or you run on the device, tier A) or logged in from a laptop over SSH (tier B), the install is **one command**, not steps 3 to 7. Ask the [First](#first-is-sproutwall-already-on-this-device) safety question, get the system on the card (step 1), and open the Terminal and run the 64-bit check (step 2). Then have the person run the one command and explain its questions, as [For the AI reading this](#for-the-ai-reading-this) says. Walk through steps 3 to 7 one block at a time only when the person asks to go step by step, or when the one command can't be used. The README's three [install options](README.md#choose-how-to-install) map to the tiers: an AI agent doing it is tier A (on the device) or B (on the laptop, over SSH); the one command by yourself is tier B over SSH, or [Without AI](#without-ai) at the device; a free chat AI is tier B next to an SSH window, or tier C at the device.

The hub needs no cloud account and no subscription. The hub never signs in to anything, and the only GitHub tool used, `gh`, runs without an account. If the AI assistant runs on the device itself (tier A below), that assistant signs in to its own service, and step 8 removes it.

**The preview this guide pins.** The guide installs one preview build, named by two values. The maintainers checked this pair, and they change both values together when they move the guide to a newer build:

| | |
| --- | --- |
| Source commit | `beb3ec14dca7eb4060979f852ed5e1e87ed4317c` |
| Image index digest | `sha256:878dacdb06d58197313c3f992d42689b189dc86edad2c3c7f58eb8c63e741be0` |

Use exactly these two values. A newer `:preview` build may exist; this guide installs only the build named here.

## First: is Sproutwall already on this device?

Step 1 erases the card. Never erase a card or disk that may hold a hub's household.

Carry on to step 1 only in one of these two cases, and only once the device's owner has said so in their own words:

- **The card or disk is new or blank:** it was never used in this device, or the owner knows it holds nothing they want to keep.
- **The household is safely backed up off the device:** a backup made with the README's [Back up](README.md#back-up) steps has been copied to another computer or drive, and the owner confirms that the card may be erased.

In every other case, don't erase anything:

- **This device already runs Sproutwall or Family Hub:** don't put a new system on it, and don't use this guide on it. Back up, then update in place, as [Existing install / update](#existing-install--update) says. Keep the data volume.
- **Not sure:** treat it as holding a hub. You can look for one without erasing anything. Start the device as it is, open a terminal and run:

  ```bash
  ls -d ~/sproutwall ~/family-hub 2>/dev/null; docker ps -a --format '{{.Names}}'; docker volume ls -q
  ```

  If any line mentions `sproutwall`, `family-hub` or `familyhub-data`, a hub is there: follow the existing-install path. **Finding nothing does not prove there is no hub.** The household can sit in a Docker volume, under another account or in another folder, and this check cannot see those when Docker is missing, refuses permission or belongs to another account. So an empty or failed check still means "not sure": back up first, or confirm with the owner that the card is new or may be erased.

The AI may not decide this itself. It asks the owner, and an empty result from the check above never counts as a yes.

## Start here: what to tell your AI

New to Raspberry Pi, the Terminal or GitHub? Start with [the step-by-step guide for beginners](docs/INSTALL-BEGINNERS.md): it gets the Pi ready and then brings you back here.

Over SSH from a laptop (tier B), give your assistant the README's SSH prompt ([The prompts](README.md#the-prompts)). At the device's own Terminal, give it this prompt:

```text
Help me install Sproutwall on my Raspberry Pi, set up for our family. I'm at the Pi's own Terminal and will run this one command myself:

curl -fsSL https://raw.githubusercontent.com/thebrianlee/sproutwall/main/install.sh | bash

The guide is https://github.com/thebrianlee/sproutwall/blob/main/INSTALL-WITH-AI.md. Explain each question the command asks me, and help me if it stops. Ask me whatever you need.
```

A chat-only AI cannot open your Pi, so open it in the Pi's own web browser: you then copy each command straight into the Pi's Terminal. Over SSH, open it on your laptop next to your SSH window instead, and copy each command into that window. The prompt gives it the one command and this guide's address; it names the command itself because a chat assistant may not read the whole guide. If it cannot open web pages, paste this guide into the chat instead.

The assistant then explains each question [the one command](README.md#with-one-command) asks. If you'd rather go step by step, say so, for example: *Read https://github.com/thebrianlee/sproutwall/blob/main/INSTALL-WITH-AI.md and walk me through it step by step.*

## For the AI reading this

You are helping a parent install a home appliance. Follow these rules for the whole install.

**Default path in every tier: the one command.** Every install command runs on the device, never on the person's laptop: the laptop only writes the card (and, in tier B, holds the person's SSH session). In tiers A and C the person is at the device's own Terminal; in tier B they are logged in from the laptop over SSH (step 2). Once the [First](#first-is-sproutwall-already-on-this-device) question is answered and the system is on the card (step 1), have the person run the one command from the README's [With one command](README.md#with-one-command), in the device's own Terminal or, in tier B, in their own SSH session, as themselves and not with `sudo`:

```bash
curl -fsSL https://raw.githubusercontent.com/thebrianlee/sproutwall/main/install.sh | bash
```

The person runs it, never you, because it runs `sudo` (rule 2); in tier A, in a second Terminal window; in tier B, in their own SSH session, typing the `sudo` password there. It checks the device first (64-bit, supported, not root, no hub already there) and changes nothing if something is wrong. It never touches an existing hub or its data: if it finds one before installing anything, nothing is changed; if it only finds one after installing the tools, it stops there and says so. Then it runs steps 3 to 5 and 7 for the person, waits during step 6, and runs doctor itself. Explain its questions, in the order it asks them:

1. **How the screen hangs** (decision 2), on Raspberry Pi OS only; Debian and Ubuntu skip it. Enter means portrait. Choosing no kiosk skips the screen setup (step 7).
2. **The install plan** (decision 3). The script prints every command it runs with `sudo`, including the exact Docker and GitHub CLI commands, with why and how to undo each. That is the plan of rule 2: the person reads it and types `y` to approve it.
3. **Possibly the device's password, right after the approval** (over SSH: only after the SSH risk below is accepted). Only when Docker is already installed but the person's account cannot reach it, or Docker's data folder from an earlier install is left: a read-only `sudo` look for an existing hub, before anything changes.
4. **The home-network rule.** The person types `y` only if it is true.
5. **Over SSH only (tier B): the SSH risk.** The script says that while SSH is on, and especially if it accepts passwords, anyone on the home network who knows or guesses the device's password can log in, and that keeping the device, its password and the network safe is the person's own responsibility. The person answers this themselves: you must not answer it or urge them to accept it. As for the plan and the home-network rule, the script accepts exactly `y`, `yes`, `Y`, `Yes` and `YES` (spaces and tabs around the answer are ignored). Anything else, or Enter alone, cancels: it ends with a plain message that nothing was changed, and prints no `Stopped:` line. The notice also always says that if the network gives the device an internet (IPv6) address and the router allows incoming connections, SSH could be reachable from the internet.
6. **Over SSH only: the device's password for a read-only look at the SSH settings** (`sudo sshd -T -C …` for this session as root and as the person's account, and one `sudo sh -c 'cat …'` that reads `sshd_config` and every `sshd_config.d/*.conf` as root; any read error stops the script). The script stops, with nothing changed, if SSH allows root login with a password or empty passwords, or has a `Match` rule or an `Include` outside `/etc/ssh/sshd_config.d` (written either as `Keyword value` or `Keyword=value`).
7. **The device's password when the installs start**, and again later if `sudo` asks.
8. **Over SSH only, at the very end: turn SSH off?** Turning it off is the safe choice; the person decides. A no leaves SSH on, as their own responsibility; the final check then reports `ssh_policy` and `temporary_access` as expected for that choice ([step 8](#step-8-remove-the-assistant-and-check-once-more)). If a temporary key was used, have the person remove it ([step 8](#step-8-remove-the-assistant-and-check-once-more)) in the open session before restarting.

The password always goes only into `sudo`'s own prompt. For the plan, the home-network rule and the SSH risk, the script accepts exactly `y`, `yes`, `Y`, `Yes` and `YES`, after ignoring spaces and tabs before or after the answer (so ` yes ` also approves). Anything else, or Enter alone, cancels: the script ends successfully with a plain message that nothing was changed, and prints no `Stopped:` line. That is not an error to fix: end the session, or ask the person whether they want to continue.

**Tier B uses the same command.** The person logs in from the laptop (step 2) and runs it in that SSH session. The script notices the SSH session and refuses one that does not come from the home network (a private, link-local or unique-local address, or a global IPv6 address in the device's own on-link prefix). It also stops, with nothing changed, if the device has no IPv4 home-network address that the laptop reaches (the address the SSH session came in on, or otherwise an IPv4 address on the network interface the SSH session uses, never a Docker or bridge address), because the laptop's browser reaches the hub over IPv4 only. It checks as tier B: SSH may stay on until the final check, password logins included, but never on a public address or with root login or empty passwords. Before any change it checks SSH itself, read-only with `sudo`: no root login with a password, no empty passwords, no `Match` rule and no `Include` outside `/etc/ssh/sshd_config.d`. It does this because the doctor in the pinned build may be older and still report password SSH as `ssh_policy` fail. The device's IPv4 addresses must be home-network only, checked again each time a doctor `ssh_policy` result is passed, so SSH can't listen on a public IPv4 address; the notice the person accepts always covers an internet IPv6 address. Only after these checks does it continue past `ssh_policy` fail or unknown during the install. The household is set up in the laptop's browser, at the address the script prints. At the end it offers to turn SSH off. You never run the command or `sudo` for the person, even though your own shell reaches the device.

When it says "Set up your household now", pause as rule 3 says; the person sets up the household on the device's own screen (tier B: in the laptop's browser) and then presses Enter in the Terminal. At the end it prints a summary with the phone check, and tells the person to restart and run the final check (step 8). If it stops, it prints one line that starts with `Stopped:` and says why and what to do. Ask for that line and `doctor --json` output only (rule 6), look both up in [If something goes wrong](#if-something-goes-wrong), and continue by hand from the step the line names. Steps 3 to 7 below stay the fallback when the person prefers to go step by step, or when the one command can't be used. Over SSH (tier B), going step by step needs key-only SSH in this preview ([step 1](#step-1-put-the-system-on-the-card)): only the one command runs its own SSH checks, so with password SSH the step-by-step doctor reports `ssh_policy` fail. With password SSH, use the one command. The rules below apply on both paths.

1. **Questions.** Before step 1, follow [First](#first-is-sproutwall-already-on-this-device). Erasing the card needs the owner's own confirmation that it is new or blank, or that the household is backed up off the device. Your own check can only find a hub; it can never clear one. This safety question is a stated exception to the five-decision limit: ask it even if the five are used up. The one command's own questions, including its SSH-risk question over SSH, belong to the person: never answer them for the person or urge them to say yes. Then ask at most the [five decisions](#the-five-decisions), each once. Don't ask for model numbers, addresses or anything you can find out yourself. Work out the tier (decision 1) yourself when it is obvious: you run in a terminal on the device (A), you run on another computer with a shell (B), or you can only chat (C at the device's own Terminal; B when the person runs your commands in their own SSH session from a laptop).
2. **Privileged commands.** Before the first `sudo`, show the [install plan](#the-install-plan-decision-3): every privileged command, why it is needed, what it changes and how to undo it. One approval covers that plan only. The person types every `sudo` command themselves, in the device's own Terminal or, in tier B, in their own SSH session. You never run `sudo`, even where it would work without a password. If anything needs a privileged change that is not in the plan, stop, explain it and note it. Don't fold it into the earlier approval. Never edit sudoers, and never add any account other than the person's own to the `docker` group. In tiers A and B you run as that account, so you can control Docker while you are installed: say so when you show the plan ([Known gap](#known-gap-the-ai-and-the-docker-group)).
3. **Secrets.** Never ask for, read, log or repeat a PIN, password, calendar link, token, API key or Wi-Fi password. The person types these only into the hub's own screen, into `sudo`'s prompt or into a tool's own sign-in page. While the person sets up the household and the PIN (step 6), pause: run nothing, read nothing and take no screenshots until they say they are done.
4. **Home network only.** Never expose the hub beyond the home network: no port forwarding, no tunnel, no public server. Never set `REQUIRE_AUTH_FOR_READS` to `0`. Never publish the Ask bridge port `8787`. Don't change the port binding.
5. **The image.** Start only the image that `verify-image` verified, and only after it exits 0. Never skip verification. Never pull or run the `:preview` tag. Never sign in to `gh` and never set a GitHub token. In this install, always run `docker compose` with `-f docker-compose.preview.yml`. The only change to the checkout is the one image line in step 4.
6. **What you see.** Ask for, and share, only `doctor --json` output (safe by design) and, as the one stated exception, the short status each step names, such as an exit code, `healthy` or `Result: ok`, or the one command's single `Stopped:` line. Never paste raw logs, config files, `docker inspect` output or screenshots of the hub.
7. **When to stop.** Stop on any doctor `fail`. Stop on any doctor `unknown`, with one exception: you may continue on exit 2 when the only unknown is `app_bind` with action `confirm_trusted_lan`, and the person confirmed the home-network rule in decision 3. Write that down as a known gap; it is not a clean pass. In this preview there are more, at the final check after an install over SSH only ([step 8](#step-8-remove-the-assistant-and-check-once-more)). With SSH off, `ssh_policy` unknown (`review_ssh`) and `temporary_access` unknown (`retry_local`) may appear when an SSH settings file that only root can read is on the device (Raspberry Pi Imager can write one), even though SSH is off: continue on those two only if `systemctl is-active ssh.service ssh.socket` prints `inactive` for both; otherwise stop. If the person chose to keep SSH on, `ssh_policy` (fail or unknown) and `temporary_access` (fail `remove_agent` because of the SSH session, or unknown `retry_local`) are expected for that choice. No other `ssh_policy` or `temporary_access` result is an exception. Also stop when `verify-image` exits non-zero or the health check is not `"ok":true`. Never work around a stop: no new volume, no other port, no disabled check.
8. **Data.** Never run `docker compose down -v` or `docker volume rm`, and never delete the `sproutwall` folder. The household lives in the Docker volume.
9. **Leave, also on an early stop.** At the end, and also whenever you stop on a doctor `fail` or an unexpected `unknown`, or the person ends the session early, the cleanup from [step 8](#step-8-remove-the-assistant-and-check-once-more) applies for your tier. Tier A: the AI tool and its sign-in are removed. Tier B: SSH is turned off unless the owner chose to keep it on ([question 8](#for-the-ai-reading-this)), and, if one was made, the temporary key is removed at both ends. Tier C: nothing to remove. Show the person how, and say when it is done.

When a chat-only AI (tier C) goes step by step, which is only when the person asks for it or the one command can't be used, give one block at a time and wait for its short result before the next.

## Supported devices

The guided steps cover 64-bit Debian-family systems: Raspberry Pi OS, Debian and Ubuntu.

**Supported (the intended path; its hardware trials have not run yet):**

- Raspberry Pi 5 and Raspberry Pi 4, running Raspberry Pi OS (64-bit) with desktop. This is the path this guide describes, including the screen setup tool.
- amd64 mini PCs and laptops running 64-bit Debian or Ubuntu, with Docker. The hub only: set the screen up by hand ([Kiosk on other devices](docs/raspberry-pi.md#kiosk-on-other-devices)).

**Should work, not tested yet:**

- Raspberry Pi 400 and 500, and screens built on Compute Module 4 or 5, with Raspberry Pi OS (64-bit).
- Other arm64 boards with 64-bit Debian or Ubuntu.
- Other 64-bit Linux distributions, arm64 or amd64. The hub image runs there, but this guide's install commands do not. Install Git, Docker Engine with Compose, and `gh` 2.68.0 or newer with your distribution's own instructions and each vendor's official docs. Then continue at [Get the code at the pinned commit](#get-the-code-at-the-pinned-commit).

**Not supported:**

- Raspberry Pi 3 and older, any Raspberry Pi Zero, and any 32-bit operating system.

**Memory.** The minimum memory for the hub is not measured yet. Tier A runs the AI tool on the device itself, which needs more memory: plan for about 4 GB or more.

The hub itself runs on any 64-bit Linux with Docker. Only `setup kiosk` (step 7) is specific to Raspberry Pi OS with its standard desktop (labwc). On other devices, set the screen up by hand.

## The five decisions

These are the only questions the install asks.

1. **Who runs the commands?**
   - **A:** an AI tool runs in the device's own Terminal. SSH stays off.
   - **B:** you log in to the device from your laptop over SSH, on your home network, with the device's password (or a temporary key); an AI tool on the laptop may help. The commands still run on the device. Step 1 turns SSH on in Raspberry Pi Imager; on a Debian or Ubuntu mini PC, tier B works only if SSH is already on.
   - **C:** a chat-only AI. You paste one block at a time into the device's Terminal and tell it only the short result. Nothing is installed for the AI, and no AI runs as your account on the device.
2. **How does the screen hang?** Raspberry Pi OS only: on Debian or Ubuntu, skip this decision (the one command doesn't ask it, and step 7 doesn't apply; set the screen up [by hand](docs/raspberry-pi.md#kiosk-on-other-devices)). Portrait is the default and the usual choice for a kitchen wall. You can also pick portrait turned the other way (`portrait-flipped`), `landscape`, `landscape-flipped`, or no kiosk (the hub then serves phones and tablets only). You don't need the screen's model number: the setup tool finds the one connected screen.
3. **Do you approve the install plan?** The AI shows the [whole plan](#the-install-plan-decision-3) once before anything needs your password. It also asks you to confirm the home-network rule below. Your yes covers that plan only.
4. **Your household.** On the hub's own screen, try it with the sample family (the Calders, a made-up family) or set up your own. You accept the device's time zone and choose the parent PIN yourself, privately. If you test a calendar, use a made-up one. The AI looks away during this step.
5. **Which features show?** One screen during setup. **Skip, use recommended** keeps everything except Ask the Hub. Ask the Hub stays off unless you turn it on, because it sends the questions kids type to the AI service you connect. You can change this later in Settings → Modules.

**The home-network rule.** You control this network (it is your own router), it is not a guest or public network, no router port is forwarded to this device, and no tunnel or remote-access service exposes it. Sproutwall is built for a trusted home network ([Keep it safe](README.md#keep-it-safe)).

### The install plan (decision 3)

These are all the `sudo` commands this guide can lead to. You type each one yourself in the device's Terminal; `sudo` asks for your password there. The steps show them in place.

Three rows below are bundles taken from a vendor's own page: Docker's install, the GitHub CLI block, and the AI tool's uninstall. **Before asking for approval, the AI copies the exact commands it will use for each bundle that applies into the plan, one line each, with the row's purpose and undo.** An approval that did not see those lines does not cover them.

| Command | Step | Why | Undo |
| --- | --- | --- | --- |
| `sudo apt update && sudo apt full-upgrade -y` | 3 | The normal system update. | Not reversible: updated packages are not rolled back. |
| `sudo apt install -y git` | 3 | Download the code. | `sudo apt remove git` |
| Docker's own apt commands, copied from Docker's install page: add Docker's signing key and package source, then install Docker Engine and the Compose plugin | 3 | Runs the hub. | The Uninstall section of the same Docker page. Deleting Docker's data folders, as that section shows, also deletes the household. |
| `sudo usermod -aG docker $USER` | 3 | Lets your account run Docker and the checks without `sudo`. This group is equal to administrator rights (see the known gap below). | `sudo gpasswd -d $USER docker` |
| The GitHub CLI block: installs `wget` if it is missing, adds GitHub's signing key `/etc/apt/keyrings/githubcli-archive-keyring.gpg` and package source `/etc/apt/sources.list.d/github-cli.list`, then installs `gh` | 3 | Checks the image's signature, with no sign-in. | `sudo apt remove gh`, then `sudo rm /etc/apt/sources.list.d/github-cli.list /etc/apt/keyrings/githubcli-archive-keyring.gpg` |
| `sudo reboot` | 3, 7, 8 | After step 3, so the `docker` group takes effect; later, to check that everything starts by itself. | Nothing to undo. |
| `sudo raspi-config nonint do_boot_behaviour B4` | 7, only if `setup kiosk` prints it | The desktop logs in by itself, so the screen comes back after a power cut. | `sudo raspi-config nonint do_boot_behaviour B3` (`setup kiosk --undo` prints it). |
| `sudo raspi-config` menus for screen blanking and desktop autologin | 7, only if you set the screen up [by hand](docs/raspberry-pi.md#set-it-up-by-hand) | Keeps the screen lit and logs in by itself. | The same menus. |
| `sudo raspi-config nonint do_ssh 1` | Raspberry Pi OS: tier B at the end of the one command (it asks first), at step 8 or on an early stop; tiers A and C only if doctor reports SSH on (`ssh_policy`) | Turns SSH off. | `sudo raspi-config nonint do_ssh 0` |
| `sudo systemctl disable --now ssh.socket ssh.service` | Debian or Ubuntu: tier B at the end of the one command (it asks first), or only if doctor reports SSH on (`ssh_policy`) | Turns SSH off; tiers A and C expect it off. | `sudo systemctl enable --now ssh.service` (or `ssh.socket` on a system that used it) |
| The AI tool's own uninstall command, only if its maker's instructions use `sudo` | Tier A: 8, or on an early stop | Removes the install-only AI tool. | Nothing to undo. |

Installing the AI tool itself (tier A, step 2) comes before this plan, because the AI has to exist before it can show one. The person installs it from its maker's official instructions and reads them first. If they use `sudo`, the person types those commands, and step 8 removes the tool (the last row above).

Other changes, without `sudo`:

- The `sproutwall` folder in your home folder, and the household's Docker volume. Keep both.
- The screen setup (step 7) writes a few files in your home folder. `./scripts/sproutwall setup kiosk --undo` puts them back ([Undo the kiosk](#undo-the-kiosk)).
- Temporary access, removed in step 8 or on an early stop: tier A, the AI tool and its settings folders; tier B, SSH itself and, if you made one, the temporary SSH key at both ends; tier C, nothing on the device.

#### Known gap: the AI and the docker group

This is a known exception to the install spec, pending a decision by the maintainers. The spec says the assistant gets no membership in the `docker` group. But `doctor` needs your own account to reach Docker, so step 3 adds your account to that group, and anyone who can use that group can control Docker, which is the same as administrator rights. In tiers A and B the AI runs as your account, so it has that power too for as long as it is installed, also after a reboot. Tier C avoids this: no AI runs on the device. Removing the AI in step 8, or whenever the install stops, ends it.

## Step 1: Put the system on the card

Do this only once the owner has confirmed the card is new or blank, or that the household is backed up off the device ([First](#first-is-sproutwall-already-on-this-device)).

1. On another computer, install [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. **Tier B, optional:** with the one command, you can log in with the Pi's password (the simplest choice) and skip this. Going step by step over SSH (steps 3 to 7) needs this key and key-only SSH in this preview, because only the one command runs its own SSH checks: the step-by-step doctor reports password SSH as `ssh_policy` fail. For a temporary key, make it on your laptop. It asks for a passphrase; you may leave it empty, because the key is deleted at the end.

   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/sproutwall-install -C sproutwall-install
   cat ~/.ssh/sproutwall-install.pub
   ```

3. In Imager, choose your Pi model, then **Raspberry Pi OS (64-bit)** with the desktop, then the card. Check that it is the card and not another drive: everything on it is erased.
4. When Imager offers to customise the system, set:
   - **Hostname:** `hub`
   - **Username and password.** Keep the password to yourself.
   - **Time zone** and **keyboard layout**
   - **Wi-Fi** country, name and password, unless you use a network cable
   - **SSH:** off for tiers A and C. Tier B: on, with password authentication (the simplest, for the one command), or with public-key authentication only and the one line that `cat` printed above (needed to go step by step over SSH).
5. Let Imager write and verify the card, then eject it.
6. With the Pi switched off, connect the screen and its touch connection following the screen's own instructions. Insert the card and switch on. The first start takes a few minutes.

**An amd64 mini PC or laptop:** install 64-bit Debian or Ubuntu with its own installer, only on a disk the owner has confirmed is new, blank or backed up ([First](#first-is-sproutwall-already-on-this-device)), with SSH off. On this path use tier A or C, or tier B only if the system's own installer already turned SSH on.

## Step 2: Open the session

**Tier A.** On the Pi's desktop, open **Terminal**. Install the AI tool with its maker's official instructions and sign in on its own sign-in page. This tool is for the install only; step 8 removes it. Then give it the prompt from [Start here](#start-here-what-to-tell-your-ai).

**Tier B.** On your laptop, open a terminal and connect. Use your username in place of `<user>`:

```bash
ssh <user>@hub.local
```

With a temporary key from step 1, use `ssh -i ~/.ssh/sproutwall-install -o IdentitiesOnly=yes -o ForwardAgent=no <user>@hub.local` instead. The first time, `ssh` shows the Pi's `ED25519 key fingerprint` and asks whether to continue. On your own home network, typing `yes` is fine. To be thorough, first compare it with what the Pi's own desktop Terminal prints for `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` (optional; it needs the Pi's keyboard). Then run the one command in this session. An AI on your laptop uses the same `ssh` options for every command, with no agent forwarding.

**Tier C.** On the Pi's desktop, open **Terminal**. Open your chat AI in the Pi's web browser, so you can copy each block into the Terminal. In tiers A and C, after the 64-bit check below, the next thing to run is the one command ([For the AI reading this](#for-the-ai-reading-this)). It runs steps 3 to 5 and 7 itself, and waits while the person sets up the household (step 6).

**All tiers: check that this is a 64-bit system.** On a Raspberry Pi:

```bash
test "$(dpkg --print-architecture)" = arm64 && test "$(uname -m)" = aarch64 && echo "64-bit OK"
tr -d '\0' </proc/device-tree/model; echo
```

It must print `64-bit OK` and a model that starts with `Raspberry Pi 4` or `Raspberry Pi 5`. A Pi 400, 500 or Compute Module is untested.

On an amd64 computer with Debian or Ubuntu:

```bash
test "$(dpkg --print-architecture)" = amd64 && test "$(uname -m)" = x86_64 && echo "64-bit OK"
```

On another arm64 board or computer with Debian or Ubuntu (not a Raspberry Pi):

```bash
test "$(dpkg --print-architecture)" = arm64 && test "$(uname -m)" = aarch64 && echo "64-bit OK"
```

On a Linux without `dpkg` (another distribution), check the same two things that `doctor` checks there:

```bash
uname -m
python3 -c 'import platform; print(platform.architecture()[0])'
```

The first line must be `aarch64` or `x86_64`, and the second `64bit`.

## Step 3: Install the tools and get the code

**Skip steps 3 to 7 when the one command finished (every tier).** It runs steps 3 to 5 and 7 itself, and waits while the person sets up the household (step 6). Go on to [step 8](#step-8-remove-the-assistant-and-check-once-more) only after it prints its `== Sproutwall is installed ==` summary and the person has restarted the device. Over SSH, if a temporary key from step 1 was used, remove it first, in the still-open session, before the restart (step 8, the temporary key, its steps 1 to 3); then restart. If the person declined the install plan or the home-network rule, nothing was changed (see [For the AI reading this](#for-the-ai-reading-this)). A "no" to a later question (turning on desktop autologin, or trying the screen setup again) leaves the hub installed and running: the run goes on to its summary, which says what is left to do. If it printed a `Stopped:` line, follow that line and [If something goes wrong](#if-something-goes-wrong). Steps 3 to 7 are for a person who asked to go step by step, and for when the one command can't be used. Over SSH with password SSH, don't go step by step: in this preview the doctor in step 5 reports password SSH as `ssh_policy` fail, because only the one command runs its own SSH checks. Use the one command instead, before anything from step 3 is on the device.

### Install the tools

You run these `sudo` commands yourself, as approved in decision 3. Tier A: open a second Terminal window for them.

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git
```

**Docker.** Install Docker Engine and Compose from Docker's own apt repository, as described in [Step 3 of the Pi guide](docs/raspberry-pi.md#step-3-install-docker). 64-bit Raspberry Pi OS and Debian use Docker's [Debian instructions](https://docs.docker.com/engine/install/debian/), "Install using the `apt` repository". On Ubuntu, use Docker's page for Ubuntu, linked from [Docker's install overview](https://docs.docker.com/get-docker/). Don't use Docker's convenience script. Then:

```bash
sudo usermod -aG docker $USER
```

**GitHub CLI (`gh`).** The image check needs `gh` 2.68.0 or newer. The `gh` packages that Debian, Ubuntu and Raspberry Pi OS ship are too old, so install it from GitHub's own apt repository. GitHub's Linux install page is linked from <https://cli.github.com>, and the steps are in [install_linux.md](https://github.com/cli/cli/blob/trunk/docs/install_linux.md), section Debian, which covers Debian, Ubuntu and Raspberry Pi OS. Check the current instructions there. At the time of writing they are:

```bash
(type -p wget >/dev/null || (sudo apt update && sudo apt install wget -y)) \
  && sudo mkdir -p -m 755 /etc/apt/keyrings \
  && out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  && cat $out | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
  && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  && sudo mkdir -p -m 755 /etc/apt/sources.list.d \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
  && sudo apt update \
  && sudo apt install gh -y
```

Don't run `gh auth login`. The check needs no account.

Restart so the `docker` group takes effect:

```bash
sudo reboot
```

After the restart, open the Terminal again. Tier A: start the AI tool again and say "Continue the Sproutwall install at step 3, the checks." Tier B: connect with the same `ssh` command.

### Check the tools

```bash
python3 --version
docker compose version
docker info >/dev/null && echo "Docker OK"
gh --version
gh attestation verify --help >/dev/null && echo "gh attestation OK"
```

You need Python 3.11 or newer, Docker Compose v2 or newer, `Docker OK`, `gh` 2.68.0 or newer and `gh attestation OK`.

**Check again for an existing hub,** now that Docker is installed. This must print nothing. Empty output is the good result:

```bash
ls -d ~/sproutwall ~/family-hub 2>/dev/null; docker volume ls -q --filter name=familyhub-data
```

If it prints anything, this device already has a hub. Stop and read [Existing install / update](#existing-install--update).

### Get the code at the pinned commit

```bash
cd ~
git clone https://github.com/thebrianlee/sproutwall.git sproutwall
cd ~/sproutwall
git checkout --detach beb3ec14dca7eb4060979f852ed5e1e87ed4317c
test "$(git remote get-url origin)" = "https://github.com/thebrianlee/sproutwall.git" && test "$(git rev-parse HEAD)" = "beb3ec14dca7eb4060979f852ed5e1e87ed4317c" && echo "Source OK"
```

It must print `Source OK`. Don't run anything from the checkout until it does.

## Step 4: Check the image before starting it

The code at this commit holds a template in place of the image digest, because a commit cannot contain the digest of the image built from it. This writes the pinned digest into that one line:

```bash
cd ~/sproutwall
sed -i 's|@sha256:<published-index-digest-hex>"|@sha256:878dacdb06d58197313c3f992d42689b189dc86edad2c3c7f58eb8c63e741be0"|' docker-compose.preview.yml
git status --short
git diff --numstat
grep -c '@sha256:878dacdb06d58197313c3f992d42689b189dc86edad2c3c7f58eb8c63e741be0"' docker-compose.preview.yml
```

All three must match exactly. `git status --short` prints this one line only. It starts with a space, because the change is not staged:

```text
 M docker-compose.preview.yml
```

`git diff --numstat` prints one line only: `1`, `1` and `docker-compose.preview.yml` (one line removed, one added, in that file only). `grep -c` prints `1`.

Now check the image. Run it from this folder, the checkout's top folder:

```bash
./scripts/sproutwall verify-image --source-sha beb3ec14dca7eb4060979f852ed5e1e87ed4317c --digest sha256:878dacdb06d58197313c3f992d42689b189dc86edad2c3c7f58eb8c63e741be0
echo "exit $?"
```

It reads the image that `docker-compose.preview.yml` would start, confirms it is the pinned digest, downloads the image's signed build record (attestation) without an account, and has `gh` check that GitHub built it from the pinned commit with this repository's workflow. It starts nothing.

| Exit | Meaning | What to do |
| --- | --- | --- |
| 0 | Verified. It prints the digest, the workflow, the commit and the start command. | Go to step 5. |
| 1 | Not verified: the signature check failed or timed out. | Stop. Don't start the hub. |
| 2 | Refused before checking: wrong folder, a mistyped value, or the compose file does not match the pinned digest. | Check that you are in `~/sproutwall` and copied both values exactly. |
| 3 | `gh` is missing or older than 2.68.0. | Install `gh` from GitHub's repository (step 3). |
| 4 | The signed build record could not be downloaded, or failed its own checks. | Check the internet connection, wait, run it again. |
| 5 | Its temporary files could not be removed. The image counts as not verified. | Delete the `sproutwall-verify-*` folders in the system's temporary folder (usually `/tmp`), then run it again. |

**Nothing may start unless this exits 0.**

## Step 5: Start the hub and claim it right away

Until first-run setup is done, anyone on your network who opens the hub could choose the PIN. So do step 6 straight after this one.

First, check the home-network rule once more on the device:

```bash
hostname -I
```

Every address with dots must start with `192.168.`, `10.`, `172.16.` to `172.31.`, or `169.254.` (link-local, for example a network cable straight to a laptop). If any other address shows, stop: the device may be reachable from outside your home.

Start the verified image and check it:

```bash
cd ~/sproutwall
docker compose -f docker-compose.preview.yml up -d --wait
docker compose -f docker-compose.preview.yml ps
curl -fsS --max-time 3 http://127.0.0.1:3847/api/health
```

- `ps` must show the hub as `healthy`.
- The health check must print one line with `"ok":true`. It also shows `version` and `schema`, and `"setup":false` until step 6.
- If `curl` reports error `503` instead, the database is blocked. Stop. Don't start over with a new volume. The hub's own message is in `docker compose -f docker-compose.preview.yml logs`: read it yourself, don't paste it into a chat.

Then run the first check. Put your tier letter after `--tier` (A, B or C). Without an AI, use C on the device's own Terminal, and B when you work over SSH from a laptop:

```bash
./scripts/sproutwall doctor --json --phase running --tier A
```

On a home network the expected result is `"result":"unknown"` (exit 2) with one unknown check, `app_bind` with the action `confirm_trusted_lan`: the device cannot see your router, so it asks you to confirm the home-network rule. Continue only if that is the only unknown and you confirmed the rule in decision 3. Anything else: see [If something goes wrong](#if-something-goes-wrong). Tier B by hand with password SSH: `ssh_policy` fail here is a stop in this preview (rule 7), because this path can't check SSH the way the one command does. Don't continue by hand, and don't run the one command over this install (it stops when it finds the hub's folder): get help, as [If something goes wrong](#if-something-goes-wrong) says.

## Step 6: Set up the household, then check

**The AI pauses now.** On the Pi's own screen, open the web browser at `http://localhost:3847`. You see **Set up the house**:

1. **Your family** (decision 4): **Try it with the sample family**, or **Set up my family**.
2. **What should your wall show?** (decision 5): choose, or tap **Skip, use recommended**.
3. **The house:** names, the time zone (filled in from this device; keep it), the location for the weather, and the **Parent PIN**, typed twice.
4. Tap **Open the wall**.

The [README](README.md#first-run-setup) explains each field and the PIN rules. When you are done, tell the AI only "done".

Check it, with your tier letter as before:

```bash
cd ~/sproutwall
./scripts/sproutwall doctor --json --phase configured --tier A
```

Same rule as before: exit 0, or exit 2 with only `app_bind` / `confirm_trusted_lan`.

**Phone check.** On the device, run `ip -o -4 addr show scope global` and use the address on the line for your Wi-Fi or network cable (often `wlan0` or `eth0`), for example `192.168.1.50` from `inet 192.168.1.50/24`. Never use an address on a `docker0`, `br-` or `veth` line (Docker's own network, for example `172.17.0.1`): no phone can reach it. Never use one that starts with `169.254.` either (a cable straight to a laptop). On a phone on the same Wi-Fi, open `http://192.168.1.50:3847` (with your address). It must show **Unlock this screen** and ask for the PIN. It must not show the family. If it shows the family without asking, stop. If the phone cannot reach it, see [A phone or tablet can't reach the hub](docs/raspberry-pi.md#a-phone-or-tablet-cant-reach-the-hub). Never forward a port, publish the bridge or turn the lock off to make the phone work.

## Step 7: Set up the screen

Skip this step if you chose no kiosk in decision 2, or on a device other than a Raspberry Pi with Raspberry Pi OS (set the screen up [by hand](docs/raspberry-pi.md#kiosk-on-other-devices) instead).

Run it as yourself, without `sudo`, while you are logged in to the Pi's desktop:

```bash
cd ~/sproutwall
./scripts/sproutwall setup kiosk
```

That turns the screen to portrait. For decision 2's other choices, add one of `--orientation portrait-flipped`, `--orientation landscape` or `--orientation landscape-flipped`.

1. **Tap the four corners and the centre of the screen.** Each tap must land under your finger. A turned picture alone does not prove that touch is right.
2. If it printed an autologin command, run it yourself (it is in the approved plan):

   ```bash
   sudo raspi-config nonint do_boot_behaviour B4
   ```

3. Check the result. The last line must be `Result: ok (exit 0)`:

   ```bash
   ./scripts/sproutwall setup kiosk --check
   ```

4. Restart with `sudo reboot`, then check by hand:
   - One full-screen hub opens by itself, the right way up. It asks once for the parent PIN to unlock this screen: type it yourself.
   - Tap the four corners and the centre again.
   - Leave it untouched for longer than the desktop's old screen-blanking time (15 minutes if you don't know it). The screen stays lit. The hub's own screensaver, with photos or quotes, is fine.
   - The phone still reaches the locked hub.

If `setup kiosk` stops, it prints one line saying why. Exit 1 after setup means the settings apply at the next login: restart, then run `--check`. Exit 4 usually means the screen or its touch connection was not found, or several were: reconnect the one screen, unplug any other, wait ten seconds and run it again. For any other stop, nothing was changed unless the message says so. Set the screen up [by hand](docs/raspberry-pi.md#set-it-up-by-hand), or choose no kiosk. The hub keeps working either way. [docs/install-cli.md](docs/install-cli.md#setup-kiosk-the-pis-own-touch-screen) lists every exit code.

## Step 8: Remove the assistant and check once more

The AI's last job is to show you this step for your tier. Then it ends its session, and you run the rest yourself. The same removal applies whenever the install stops early: on a doctor `fail`, on an unexpected `unknown`, or when you end the session.

**Tier A.** In the Pi's Terminal:

1. In the AI tool, use its own logout command, then quit it.
2. Uninstall it the way its maker's instructions say (the same way it was installed).
3. Delete its settings folders, which also hold its sign-in. Run only the one for the tool you used:
   - Claude Code: `rm -rf ~/.claude ~/.claude.json`
   - Codex CLI: `rm -rf ~/.codex`
   - Gemini CLI: `rm -rf ~/.gemini`

The final check below looks for these tools, their folders and any autostart entry for them, and fails if one is left.

**Tier B.** Turning SSH off is the safe choice. The one command's last question turns it off; if it printed `SSH is off`, it is off. If you went step by step, turn it off now, in your SSH session (it stays open) or in the Pi's own Terminal: `sudo raspi-config nonint do_ssh 1` (Debian or Ubuntu: `sudo systemctl disable --now ssh.socket ssh.service`), then run `systemctl is-active ssh.service ssh.socket` in the same place: it is off only when that prints `inactive` for both. If you answered no because you want to keep SSH on, leave it on: that is your choice and your own responsibility, and the final check below says what it reports then. To turn it off later, use the same command. Close the AI session on the laptop.

Only if you used a temporary key from step 1, also remove it while an SSH session is still open: with the one command, after its last question and before you restart (its session stays open even with SSH off); going step by step, before you turn SSH off; with SSH kept on, any time, but only if you can still log in another way: a password login (from the laptop, `ssh -o PubkeyAuthentication=no <user>@hub.local true` asks for the password and returns without an error) or another key in the list from `ssh-keygen -lf ~/.ssh/authorized_keys`. If the temporary key is your only way in and you keep SSH on, keep it: it is now your login key, not a temporary one, so keep the laptop's copy safe and skip the steps below. If SSH is already off and the session is closed, do step 2 below in the Pi's own Terminal; without a keyboard, step 4 on the laptop still deletes the only copy of the key:

1. On the laptop, show the temporary key's fingerprint, and keep it on screen:

   ```bash
   ssh-keygen -lf ~/.ssh/sproutwall-install.pub
   ```

2. On the Pi, remove the temporary key and list the keys still allowed:

   ```bash
   sed -i '/ sproutwall-install$/d' ~/.ssh/authorized_keys
   ssh-keygen -lf ~/.ssh/authorized_keys
   ```

   The laptop's fingerprint must not be in the list. If no keys are left, `ssh-keygen` says the file is not a public key file; that is fine. If the fingerprint is still listed, open the file with `nano ~/.ssh/authorized_keys` and delete that key's line. Other keys stay. This does not turn SSH off: that is the separate choice above.
3. On the laptop, confirm the old key no longer gets in. This must fail:

   ```bash
   ssh -o BatchMode=yes -o ConnectTimeout=5 -i ~/.ssh/sproutwall-install -o IdentitiesOnly=yes <user>@hub.local true
   ```

4. Then delete the key on the laptop:

   ```bash
   rm ~/.ssh/sproutwall-install ~/.ssh/sproutwall-install.pub
   ```

**Tier C.** Nothing was installed for the AI. You may paste the final check's output into the chat, then close the chat.

**The final check, all tiers.** In the device's own Terminal, with your tier letter. Use `--kiosk off` instead of `--kiosk on` if you chose no kiosk or set the screen up by hand:

```bash
cd ~/sproutwall
./scripts/sproutwall doctor --json --phase final --tier A --kiosk on
```

It passes with `"result":"pass"` (exit 0), or with `"result":"unknown"` (exit 2) when the only unknown is `app_bind` / `confirm_trusted_lan`. Without `--json` it prints the same result as readable text, ending with `Result:`.

After an install over SSH (tier B), in this preview:

- **SSH off:** run the final check in the device's own Terminal: it fails while any SSH session into the device is open, so it can't run over SSH. It may also show `ssh_policy` unknown (`review_ssh`) and `temporary_access` unknown (`retry_local`) when an SSH settings file that only root can read is on the device (Raspberry Pi Imager writes one for password SSH), even though SSH is off. Those two unknowns are acceptable only if this prints `inactive` for both:

  ```bash
  systemctl is-active ssh.service ssh.socket
  ```

  If it prints anything else, SSH is not off: turn it off as tier B above says and run the final check again, or follow *SSH kept on* below.
- **No keyboard for the device:** you can't type the final check there. What stands in for it: the confirmation that SSH is off, meaning `systemctl is-active ssh.service ssh.socket` printed `inactive` for both (the one command prints it in its line `SSH is off: ...`; going step by step, you ran it in your SSH session right after turning SSH off, tier B above), plus the checks after the restart below that need no Terminal (the phone check, and with the kiosk the hub back on the screen). If SSH was not confirmed off that way, SSH is still on: follow *SSH kept on*.
- **SSH kept on (your choice):** you may run the final check over SSH. Then `ssh_policy` (fail or unknown) and `temporary_access` (fail `remove_agent`, because of your SSH session, or unknown `retry_local`) are expected for that choice. Every other check must pass, or be the `app_bind` / `confirm_trusted_lan` unknown.

Any other unknown, and any other fail, is still a stop.

Finally, restart with `sudo reboot` (skip this only if you already restarted after the one command finished; going step by step over SSH, run it now: in the still-open SSH session, also when SSH is off and there is no keyboard, or in the device's own Terminal if you have a keyboard and already closed that session), then check once more, with no assistant:

- **With the kiosk:** the hub comes back on the screen by itself.
- **Without the kiosk** (no kiosk, or a screen set up by hand): in the device's own Terminal, or over SSH if you kept SSH on, run the two checks below. With no keyboard and SSH off you can't run them: then the phone check below is the check. `ps` must show `healthy`, and the health check must print `"ok":true`. Right after the restart, `ps` can show `health: starting` for up to a minute: wait 30 seconds and run both checks again before you treat it as a problem. A phone on the home Wi-Fi must still show **Unlock this screen** at `http://<lan-ip>:3847`. A screen you set up by hand must open the hub by itself.

  ```bash
  cd ~/sproutwall
  docker compose -f docker-compose.preview.yml ps
  curl -fsS --max-time 3 http://127.0.0.1:3847/api/health
  ```

You are done. Keep the `sproutwall` folder: it is the hub's folder.

## If something goes wrong

Each doctor check that is not `pass` names one action. The same action can come from different checks, so read both the check `id` and its `action` in the output:

| Check | Action | What it means | What to do |
| --- | --- | --- | --- |
| `platform` | `use_supported_os` | The system or CPU is not 64-bit Linux (for example a 32-bit system). | Put a 64-bit system on the card ([Supported devices](#supported-devices)), but only after the owner explicitly confirms the card may be erased: it holds no household data, or a [backup](README.md#back-up) has been copied off the device. |
| `docker` | `use_supported_os` | Docker Compose is missing or older than v2. | Install or upgrade Docker Engine and Compose (step 3). Never put a new system on the card for this. |
| `docker` | `retry_local` | Docker is not running, or your account cannot reach it yet. | Check `docker info`. If you just joined the `docker` group, restart first (step 3). Then run the check again. |
| `image_identity` | `verify_release` | The running image, or the compose file, is not the verified preview. | `docker compose -f docker-compose.preview.yml stop`, repeat step 4, and start again only after exit 0. |
| `storage` | `restore_storage` | The data volume, photos folder or database is not as expected. | Stop and get help. Don't start a new volume, don't delete anything, and don't run the README's restore command in this install: it uses the default Compose file, which builds the image locally instead of using the verified one. A restore procedure for preview installs is not written yet. |
| `health` | `restore_storage` | The database is blocked (the hub answers 503 with a reason). | Stop. Don't start a new volume. Read `docker compose -f docker-compose.preview.yml logs` yourself, then get help. |
| `health` | `retry_local` | The hub is not healthy yet, or answered in an unexpected way. | Wait a minute and run it again. If it repeats, stop and get help. |
| `app_bind` | `restrict_ports` | Port 3847 is reachable beyond the home network. | Stop the hub now with `docker compose -f docker-compose.preview.yml stop`. Check the router for port forwards and tunnels. Get help. Don't change the port or turn the check off. |
| `app_bind` | `confirm_trusted_lan` | The hub is on your home network, and the device cannot prove the router forwards nothing. | Expected. Continue only if it is the only unknown and you confirmed the home-network rule in decision 3. |
| `bridge_bind` | `restrict_ports` | The Ask bridge port 8787 is published or listens beyond the container. | Stop the hub now. `git status --short` and `git diff --numstat` must still match step 4: only the one image line changed. Get help. |
| `ssh_policy` | `review_ssh` | SSH is on where it must be off (tiers A and C, and every final check), it listens on a public address, it allows root login or empty passwords, or its settings could not be read. | Tiers A and C and every final check expect SSH off: turn it off with the install plan's line for your system, `sudo raspi-config nonint do_ssh 1` on Raspberry Pi OS, `sudo systemctl disable --now ssh.socket ssh.service` on Debian or Ubuntu. Tier B allows SSH until the final check, password logins included, but never on a public address or with root login or empty passwords: stop, fix that or get help. Settings that could not be read, or password SSH reported as fail by the pinned build's older doctor: over SSH, the one command checks SSH itself (read-only, with `sudo`) and continues during the install; otherwise stop and get help. At the final check after an install over SSH, in this preview: with SSH off, an unknown because a settings file only root can read is on the device is acceptable only if `systemctl is-active ssh.service ssh.socket` prints `inactive` for both; with SSH kept on by the owner's choice, a fail or unknown here is expected ([step 8](#step-8-remove-the-assistant-and-check-once-more)). Anything else is a stop. |
| `setup` | `open_hub` | First-run setup is not finished. | Open the hub on the device and finish setup (step 6). |
| `read_guard` | `open_hub` | Setup is not finished, so the hub still answers without a PIN. | Finish setup now (step 6). |
| `read_guard` | `verify_release` | Setup is finished, but the hub answers without a PIN: the screen lock is off. | Stop the hub. `git status --short` and `git diff --numstat` must still match step 4: only the one image line changed. Repeat step 4. Never set `REQUIRE_AUTH_FOR_READS` to `0`. |
| `kiosk` | `repair_kiosk` | The screen launcher is not in the state you chose. | `./scripts/sproutwall setup kiosk --check`, then `setup kiosk` (on) or `setup kiosk --off`. Check that `--kiosk` matches your choice. |
| `temporary_access` | `remove_agent` | The AI tool, its folders or autostart entry, or an SSH session is still there. | Repeat step 8 for your tier, and close every SSH session. If you kept SSH on by choice and ran the final check over SSH, this result is expected ([step 8](#step-8-remove-the-assistant-and-check-once-more)). |
| any check | `retry_local` | The check could not finish. | Wait a minute and run it again in the device's own Terminal, as your user. If it repeats, stop and get help. Don't work around it. One exception in this preview: `temporary_access` at the final check after an install over SSH, when an SSH settings file only root can read is on the device and `systemctl is-active ssh.service ssh.socket` prints `inactive` for both, or when you kept SSH on by choice ([step 8](#step-8-remove-the-assistant-and-check-once-more)). |

When the install stops here, the AI still removes itself as step 8 shows.

To get help, open an issue in the repository with the `doctor --json` output only: no logs, names or links. Report security problems privately as [SECURITY.md](SECURITY.md) says.

## Existing install / update

**This device already runs Sproutwall (or Family Hub).** Don't use this guide on it, and never start a second, fresh Compose project next to it: a new project starts with an empty household. Keep the existing folder and its data volume. Back up, then update in place, as the README's [Back up and update](README.md#back-up-and-update) and [Installed before the rename](README.md#installed-before-the-rename) describe.

**Updating a hub installed with this guide.** A step-by-step update to a newer preview is not written yet. Don't run the README's update command in this folder: it builds locally from a different compose file. Keep the folder and the volume, and back up regularly. The README's backup, with this install's compose file:

```bash
cd ~/sproutwall
docker compose -f docker-compose.preview.yml stop
docker compose -f docker-compose.preview.yml run --rm -T --entrypoint tar family-hub czf - -C / data photos > sproutwall-backup.tgz
docker compose -f docker-compose.preview.yml start
```

Copy `sproutwall-backup.tgz` off the device, for example to a USB stick, and keep it private: it holds the household and the hub's secret keys.

## Undo the kiosk

In `~/sproutwall`, on the Pi's desktop:

- **Pause it:** `./scripts/sproutwall setup kiosk --off` closes the kiosk browser and stops it starting at login. The hub keeps running and phones still reach it. Turn it back on with `./scripts/sproutwall setup kiosk`.
- **Remove it:** `./scripts/sproutwall setup kiosk --undo` puts back every file as it was before setup. If autologin was off before, it prints the command that turns it off again: `sudo raspi-config nonint do_boot_behaviour B3`.

If `--undo` refuses because a file was changed after setup (for example in Control Centre), follow [Remove the kiosk by hand](docs/raspberry-pi.md#remove-the-kiosk-by-hand). The hub and its data are not touched either way.

## Without AI

The easiest way without AI is the one-command install in the README, [With one command](README.md#with-one-command): on the device, it shows the install plan, asks you, and then runs steps 3 to 5 and 7 for you.

Everything above works by hand. Make the five decisions yourself, skip the tier A and B parts, and run each block in order in the device's own Terminal. Use `--tier C` in the doctor commands. Over SSH from a laptop, use the one command instead; going step by step over SSH needs key-only SSH in this preview, follows the tier B parts, and uses `--tier B`. The rules in [For the AI reading this](#for-the-ai-reading-this) are good rules for you too: stop where they say stop.

For a hub that builds on the device instead of using the prebuilt image, see the [Raspberry Pi guide](docs/raspberry-pi.md).
