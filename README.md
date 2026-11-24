# Sproutwall

Sproutwall (formerly Family Hub) is a family dashboard for a screen in your kitchen. It runs on a Raspberry Pi in your home, with no cloud account and no subscription.

## Install

**Sproutwall runs on the Raspberry Pi itself, not on your laptop.** You need a Raspberry Pi 4 or 5 running Raspberry Pi OS (64-bit), with its screen attached. A 64-bit computer with Debian or Ubuntu works too. Your laptop writes the SD card and, if you like, logs in to the Pi over SSH, so the Pi needs no keyboard.

New to Raspberry Pi? Two step-by-step guides go from a blank SD card to the hub on your kitchen screen: [from your laptop over SSH](docs/INSTALL-OVER-SSH.md), with no keyboard on the Pi, or [with a keyboard on the Pi](docs/INSTALL-BEGINNERS.md).

### Before you start: put the system on the card

On your laptop, write the card with [Raspberry Pi Imager](https://www.raspberrypi.com/software/):

1. **Device:** your Pi model. **OS:** Raspberry Pi OS (64-bit), the version with the desktop. **Storage:** the microSD card. Writing erases everything on it, so use a new card, or one whose contents are backed up somewhere else.
2. **Customisation:**
   - **Hostname:** `hub`, the Pi's name on your home network.
   - **User:** a username and a password. Keep the password to yourself: you type it only into the Pi's own password prompts.
   - **Localisation:** your time zone, keyboard layout and Wi-Fi country. The hub takes its time zone from the Pi.
   - **Wi-Fi:** your home network, not a guest network. A network cable works too.
   - **Remote access:** turn **SSH** on, with password authentication, if you will install from your laptop. Leave it off if you will type on the Pi with a keyboard.
3. **Write.** Then put the card in the Pi, connect the screen and switch it on.

If Imager says "Error reading from storage", see [If Imager can't read the card](docs/INSTALL-BEGINNERS.md#if-imager-cant-read-the-card).

**To log in from your laptop (SSH):** once the Pi has started, open Terminal on a Mac or Linux laptop, or PowerShell on Windows, on the same home network. Type `ssh <user>@hub.local`, where `<user>` is the username you set in Imager (if you chose another hostname, use it in place of `hub`). The first time, ssh asks you to confirm the Pi's fingerprint: on your own home network, type `yes`. Then type the Pi's password. Everything you type in that window now runs on the Pi.

### Choose how to install

| Option | Who it's for | You need |
|---|---|---|
| [1. Have your AI do it](#1-have-your-ai-do-it) | You use an AI agent that can run commands, such as Claude Code or Codex CLI | That agent; on a laptop, SSH on in Imager |
| [2. One command, by yourself](#2-one-command-by-yourself) | You're fine typing one command | SSH from your laptop, or a keyboard on the Pi |
| [3. Free AI chat, no app](#3-free-ai-chat-no-app) | You've never done this, and have no paid AI and no app | A free chat AI in your web browser, and SSH from your laptop |

All three run the same [one command](#with-one-command). It shows its plan and asks before it changes anything. Your passwords and the parent PIN never go to an AI.

### 1. Have your AI do it

Give an AI agent that can run commands, such as Claude Code or Codex CLI, the first of [the prompts](#the-prompts) below. On your laptop it works over SSH (tier B in the [install guide](INSTALL-WITH-AI.md)): with a temporary key from the guide's [step 1](INSTALL-WITH-AI.md#step-1-put-the-system-on-the-card), the agent can log in to the Pi itself; with only the Pi's password, you log in and run the commands it gives you. It can also run on the Pi itself, if you have a keyboard there (tier A; give it the second prompt, and the guide removes it at the end). It follows the guide: it asks the safety questions first, checks the Pi, and walks you through the one command. You run that command yourself and answer its questions. The agent never runs `sudo` and never sees your passwords or the parent PIN.

### 2. One command, by yourself

Log in to the Pi [over SSH](#before-you-start-put-the-system-on-the-card) from your laptop, or open **Terminal** on the Pi's own desktop with a keyboard. Then run the [one command](#with-one-command) as yourself, not with `sudo`. If you'd like each question explained as it comes, also give a chat AI one of [the prompts](#the-prompts).

### 3. Free AI chat, no app

No paid AI and no app needed. On your laptop, open a free chat AI in your web browser, such as ChatGPT, Claude or Gemini. Log in to the Pi [over SSH](#before-you-start-put-the-system-on-the-card) in a second window, and paste the first of [the prompts](#the-prompts) into the chat. The chat walks you through it: copy each command it gives you into your SSH window, and tell it only the short result it asks for. It can't see or change your Pi itself. If you are at the Pi with a keyboard instead, open the chat in the Pi's own web browser and use the second prompt.

### The prompts

Logged in to the Pi over SSH from your laptop:

```text
Help me install Sproutwall on my Raspberry Pi, set up for our family. I'm logged in to the Pi over SSH from my laptop, and I will run this one command myself in that SSH window:

curl -fsSL https://raw.githubusercontent.com/thebrianlee/sproutwall/main/install.sh | bash

The guide is https://github.com/thebrianlee/sproutwall/blob/main/INSTALL-WITH-AI.md, and I'm in its tier B. Explain each question the command asks me, and help me if it stops. Ask me whatever you need.
```

At the Pi's own Terminal, with a keyboard and screen:

```text
Help me install Sproutwall on my Raspberry Pi, set up for our family. I'm at the Pi's own Terminal and will run this one command myself:

curl -fsSL https://raw.githubusercontent.com/thebrianlee/sproutwall/main/install.sh | bash

The guide is https://github.com/thebrianlee/sproutwall/blob/main/INSTALL-WITH-AI.md. Explain each question the command asks me, and help me if it stops. Ask me whatever you need.
```

Each prompt names the one command itself, because a chat AI may not read the whole guide. To go step by step instead, tell the AI. [INSTALL-WITH-AI.md](INSTALL-WITH-AI.md) is the full guide, and you can also follow it by hand.

### With one command

In your SSH window, or in **Terminal** on the Pi's own desktop, run this as yourself, not with `sudo`:

```bash
curl -fsSL https://raw.githubusercontent.com/thebrianlee/sproutwall/main/install.sh | bash
```

It runs the steps of the [install guide](INSTALL-WITH-AI.md) for you, the way the guide's "Without AI" path does, and asks a few questions on the way:

- First it checks the device, and changes nothing if something is wrong: a 32-bit or unsupported system, running as root, or a hub that is already on this device. It never touches an existing hub or its data. If it finds one before installing anything, nothing is changed; if it only finds one after installing the tools, it stops there and says so.
- On Raspberry Pi OS it asks how the screen hangs; Debian and Ubuntu skip that question. Then it shows every `sudo` command it will run, with why and how to undo it, and asks you to approve that plan and to confirm the home-network rule. Only `y` or `yes` goes on (also `Y`, `Yes` or `YES`; spaces and tabs before or after the answer are ignored); any other answer, or just Enter, changes nothing. It then ends with a plain message that nothing was changed, not with a "Stopped:" line.
- Your password goes only into `sudo`'s own prompt. If Docker is already installed but your account cannot reach it, or Docker's data folder from an earlier install is still on the device, `sudo` may ask for it right after you approve the plan, for a read-only look for an existing hub. Otherwise it asks when the installs start, after the home-network question.
- It installs git and the GitHub CLI (`gh`) with the guide's commands, and Docker with Docker's own commands, with `-y` added to their installs because you approved them in the plan. Then it gets the code at the pinned commit, checks the image's signature with `verify-image`, and starts only that verified image.
- It waits while you set up your household and the parent PIN on the device's own screen. It never asks for, reads or shows the PIN.
- On Raspberry Pi OS it sets up the screen with `setup kiosk`, unless you chose no kiosk; Debian and Ubuntu skip this. At the end it tells you to restart and how to check the hub.

**Over SSH,** the command first asks you to accept that keeping SSH on is your own responsibility, and takes a read-only look at the SSH settings with `sudo`, before it changes anything. You set up the household in your laptop's browser. At the end it offers to turn SSH off, and turning it off is the safe choice: SSH is off only when it then prints a line that starts with "SSH is off:". It refuses an SSH session that does not come from your home network, and it needs the Pi to have an IPv4 address on your home network (most do), because your laptop's browser reaches the hub over IPv4.

What it doesn't do: put the system on the card, update or restore a hub that is already there, set up remote access, sign in to anything, or send anything anywhere except the package installs, the code and image downloads and the image's signature check. If a check fails, it stops with one line that says why and what to do; [If something goes wrong](INSTALL-WITH-AI.md#if-something-goes-wrong) has the details. The one-command install is new and has not been tried on a Raspberry Pi yet.

### For AI assistants helping someone install Sproutwall

If you are an AI assistant helping someone install Sproutwall, follow these rules:

- **Commands run on the Pi, never on the person's laptop.** The laptop only writes the SD card with Raspberry Pi Imager and, over SSH, holds the person's own SSH session to the Pi. If you are a chat assistant, the person copies each command into their SSH window on the laptop (tier B) or, with you open in the Pi's own web browser, into the Pi's Terminal (tier C).
- **Ask the safety question first, before the card is written:** may the card or device hold a household that must not be erased? The card may be erased only if the owner confirms in their own words that it is new or blank, or confirms that the household is backed up off the device and that the card may be erased. An unsure answer means stop: don't write the card. Your own check can only find a hub; finding nothing never counts as a yes. A device that already runs Sproutwall or Family Hub is backed up and updated in place, never reinstalled ([First](INSTALL-WITH-AI.md#first-is-sproutwall-already-on-this-device)). Then ask at most the guide's [five decisions](INSTALL-WITH-AI.md#the-five-decisions). Don't ask for anything you can find out yourself, such as the Pi model, memory or screen.
- **Default path in every tier: the one command above**, in the Pi's own Terminal or in the person's SSH session. The person runs it themselves; you never run `sudo`. Explain its questions in the order it asks them: on Raspberry Pi OS only, how the screen hangs (Enter is portrait); the install plan (the person reads it and types `y`); possibly the Pi password right after that, for a read-only look for an existing hub; the home-network rule (`y` only if it is true); then the Pi password when the installs start. The password goes only into `sudo`'s own prompt. When it says "Set up your household now", wait and look at nothing until the person is done. Over SSH from a laptop (tier B in the guide), the person runs the same command in their own SSH session and types the `sudo` password there; you never run it. It then also asks the person to accept the SSH risk before any change: the person answers that themselves, and you must not answer it or urge them to. At the end it offers to turn SSH off.
- **Never ask for or accept** the parent PIN, any password (the Pi's or the Wi-Fi's), calendar links, tokens or API keys. The person types them only into the hub's own screen, `sudo`'s prompt or a service's own sign-in page.
- **If the person declines** the plan or the home-network rule, the command ends with a plain message that nothing was changed. That is not an error to fix: end the session, or ask whether they want to continue. **If it stops,** it prints one line that starts with `Stopped:` and says why and what to do. Use that line with the guide's [If something goes wrong](INSTALL-WITH-AI.md#if-something-goes-wrong) and the doctor check, `cd ~/sproutwall && ./scripts/sproutwall doctor --json --phase running --tier C` once the hub has started (`--tier B` over SSH). Ask for and share nothing else: no logs, config files or screenshots. Never work around a stop.
- **Never suggest** Docker's convenience script, `docker compose down -v`, `docker volume rm`, deleting the `sproutwall` folder, the `:preview` tag, `gh auth login` or a GitHub token, skipping the image check, turning the screen lock off, or exposing the hub beyond the home network (port forwarding, tunnels, public servers).
- **Don't use the build-from-source installs** ([manual install](docs/manual-install.md), and the build steps of the [Raspberry Pi guide](docs/raspberry-pi.md)) for a family. They are for developers: they build the image on the device instead of installing the verified one.
- **Full rules:** [For the AI reading this](INSTALL-WITH-AI.md#for-the-ai-reading-this) in INSTALL-WITH-AI.md. They apply to every step.

> **Early preview.** Sproutwall started as one family's kitchen screen and runs there every day; the guided install is new. If you try it, please tell us how it went with an [install report](https://github.com/thebrianlee/sproutwall/issues/new?template=install_report.yml), whether it worked or not. Bugs are welcome as [issues](https://github.com/thebrianlee/sproutwall/issues/new/choose), and ideas and questions in [Discussions](https://github.com/thebrianlee/sproutwall/discussions).

It shows the day at a glance: weather, the family calendar, routines, meals, lists, a reading shelf, a points jar (Family Bucks), and Ask the Hub, a question wall for kids. The household's data stays on the computer that runs it.

Turn features on or off in Settings → Modules.

![The Today screen, showing the fictional Calder family](docs/screenshots/today.png)

The screenshots show the Calders, a made-up sample family. They are not a real household.

**Contents:**
[Install](#install) ·
[Using the hub](#using-the-hub) ·
[Keep it safe](#keep-it-safe) ·
[Back up and update](#back-up-and-update) ·
[Forgot the PIN](#forgot-the-pin) ·
[Ask the Hub](#ask-the-hub) ·
[Calendars](#calendars) ·
[Photos](#photos) ·
[Raspberry Pi](#raspberry-pi) ·
[For developers](#for-developers) ·
[Contributing](#contributing) ·
[License](#license)

## Using the hub

However you installed it, this is how you reach the hub and set it up.

### Open it from a phone or tablet

The hub uses port 3847.

- On the computer that runs it: <http://localhost:3847>
- On a phone, tablet or laptop on the same Wi-Fi: `http://<lan-ip>:3847`, for example `http://192.168.1.50:3847`

To find the computer's LAN address (`<lan-ip>`):

- Linux or Raspberry Pi: run `ip -o -4 addr show scope global` and use the address on the line for your Wi-Fi or network cable (often `wlan0` or `eth0`), for example `192.168.1.50` from `inet 192.168.1.50/24`. Never use an address on a `docker0`, `br-` or `veth` line (Docker's own network, for example `172.17.0.1`): no phone can reach it. Never use one that starts with `169.254.` either (a cable straight to a laptop).
- Mac: System Settings, then Wi-Fi, then Details next to your network.
- Windows: run `ipconfig` and look for "IPv4 Address".

Tips:

- Ask your router to always give this computer the same address (often called a "DHCP reservation"). Otherwise the address can change and the bookmark on your phone stops working.
- Some devices can also use the computer's name, for example `http://hub.local:3847`. This may not work on every phone.
- Use `http://`, not `https://`, unless you set up HTTPS yourself (see [Keep it safe](#keep-it-safe)).

### First-run setup

The first visit shows **Set up the house**. Finish it right away. Until setup is done, anyone on your network who opens the page could choose the PIN. After the first setup succeeds, the setup page is closed for good.

**Your family.** Choose one:

- **Try it with the sample family** keeps the Calders, a made-up family, with their sample routines, events and points. Good for a first look.
- **Set up my family** asks for 1 to 8 kids and 1 to 4 parents. Each kid has a name, an age (0 to 18), and a **Doesn't read yet** box for kids who need bigger pictures and fewer words. Each parent has a name. Everyone gets a color from a fixed set. The sample family and everything of theirs is removed.

You can change the family later in [Settings](#parent-settings), including starting over.

**The house:**

- **Household name**, **Greeting name**, and **Points name** (what the kids earn, for example "Family Bucks").
- **Timezone.** It is filled in from the device you are using. Use a name like `America/Chicago` or `Europe/Berlin`. The hub keeps its clock and "today" in this timezone, also inside Docker.
- **Latitude** and **Longitude** for the weather. The sample values point at a city downtown, not a home. A nearby town center is close enough. Weather comes from [Open-Meteo](https://open-meteo.com/) and is shown in °F.
- **Parent PIN**, typed twice.

PIN rules:

- 4 to 8 digits. There is no default PIN.
- Easy PINs are refused: well-known ones like `1234`, `0000`, `1212` and `2580`, the same digit over and over (`7777`), and straight runs up or down (`3456`, `9876`).
- Choose 6 or more digits if people you don't fully trust can reach the hub, for example guests on your Wi-Fi. A 4-digit PIN can be guessed in time (see the wrong-PIN limits below).
- The hub stores only a scrambled form of the PIN (an scrypt hash). Nobody can read it back. If you forget it, see [Forgot the PIN](#forgot-the-pin).

### Unlocking each screen

With Docker, every screen is locked until a parent unlocks it. That is the `REQUIRE_AUTH_FOR_READS: "1"` line in `docker-compose.yml`.

| | What it allows | How long it lasts |
| --- | --- | --- |
| **Screen unlock** | Seeing the hub, and kid actions: checking off routines, logging mood, reading and practice, lists, meals, adding events, picking goals, asking for rewards, editing routines, and Ask the Hub. | 30 days on that screen and browser. |
| **Parent actions** | Redeeming and pricing rewards, rules and status, deleting events, removing activities, and everything in [Settings](#parent-settings). | The hub asks for the PIN each time. Behind the scenes, a correct PIN opens a 15-minute parent session on that screen only. |

- The first time a new screen opens the hub, it shows **Unlock this screen**. Enter the parent PIN once. Entering the PIN again later, for example for a parent action, starts a fresh 30 days.
- The unlock belongs to one browser on one device. A private or incognito window, or clearing the browser's cookies, asks again.
- Resetting the PIN locks every screen. Changing it in Settings locks every screen except the one used to change it. Each locked screen asks for the new PIN.

**Wrong PINs.** The hub slows down guessing in layers:

- Each screen gets 5 tries. After that it must wait 1 minute, then 2, 4, 8, and at most 15 minutes after each wrong try.
- A device can pretend to be a new screen, so two hub-wide limits do the real work: one for screens that are not unlocked yet, and one for screens that are. 30 wrong tries in one hour lock PIN entry for that kind of screen for 15 minutes, and each repeat doubles the wait, up to 24 hours. Once 60 wrong tries have been made in a day, however slowly, PIN entry for that kind of screen stays locked until 24 hours after the first of them.
- A lock only stops people typing the PIN. Kids can keep using an unlocked screen, and a stranger on your Wi-Fi cannot lock the family's unlocked screens.
- That allows at most 60 wrong guesses a day for each kind of screen (120 in all). A 4-digit PIN could still be guessed within weeks to months, which is why 6 or more digits are safer.
- Someone on your network who keeps guessing can keep *new* screens from being unlocked for a day at a time. Screens that are already unlocked are not affected.
- [Resetting the PIN](#forgot-the-pin) clears the hub-wide locks. A single screen that is waiting out its own wrong tries (at most 15 minutes) keeps waiting until the hub restarts.

### Parent settings

Tap the gear button in the tab bar to open **Settings** (the page is `/settings`). It asks for the parent PIN. Tap **Done** when you finish: it ends the parent session on that screen. Typing is easier from a phone or laptop on your home Wi-Fi: open the same page there.

- **Household:** household name, greeting, the name for points, timezone (with a **Use this device's timezone** button), and latitude and longitude for the weather.
- **Family:** change a person's name, age, **Doesn't read yet** box or color; add a kid or a parent; or remove someone. Removing hides the person and keeps their history, but deletes their calendar link and calendar events. The hub always keeps at least one kid and one parent. **Start over with a different family** replaces everyone, with their routines, points, books, calendar links and history, after you confirm. Family-wide rewards, meals, lists and rules stay.
- **Calendars:** a link for each person and one for the kids' shared calendar. See [Calendars](#calendars).
- **Ask the Hub privacy:** the switch that sends kids' first names with their questions. See [Ask the Hub](#ask-the-hub).
- **Parent PIN:** change the PIN. It needs the current PIN and signs out every other screen.

The parent session lasts 15 minutes. If it ends while you are in Settings, the PIN keypad comes back: enter the PIN and tap **Save** again. What you typed is kept.

## Keep it safe

Sproutwall is built for a trusted home network. The short version:

- **It is a home-network appliance.** Anyone who can reach port 3847 sees the unlock screen and can try PINs. Only devices in your home should be able to reach it.
- **Never port-forward it.** Do not open port 3847, or any port that leads to it, on your router. Do not run it on a public server.
- **Plain `http://` does not encrypt anything.** On home Wi-Fi the PIN and the unlock cookies travel unencrypted. Someone who can watch your network traffic could copy them.
- **Keep screens locked.** Every screen stays locked until a parent unlocks it with the PIN. Never turn the lock off.
- **Treat calendar links and backups as secrets.** A secret iCal link lets anyone read that calendar. A backup holds the household database and the hub's secret keys.

A hub installed with the one command or [INSTALL-WITH-AI.md](INSTALL-WITH-AI.md) follows that guide's rules ([For the AI reading this](INSTALL-WITH-AI.md#for-the-ai-reading-this), rules 4 and 5): never expose it beyond the home network, never turn the screen lock off, and never change its compose files or its port binding. Outside access, binding the port to one address and the other settings below are for the [manual install](docs/manual-install.md#keep-it-safe-on-a-manual-install) only.

Kids' data stays on your computer. The one exception is Ask the Hub, and only if you turn it on (see [Ask the Hub](#ask-the-hub)).

Running your own copy for your own family is different from running it as a service for other families. Someone who hosts Sproutwall for other households takes on legal duties, such as COPPA for children's data in the US. This is not legal advice.

[SECURITY.md](SECURITY.md) has the full details and says how to report a security problem privately.

There are no per-person accounts. Google sign-in is not built. The parent PIN is the access control in this version. Sign-in may come later as an option that is off by default.

### Limit who can connect

For the [manual install](docs/manual-install.md#limit-who-can-connect) only. On a hub installed with the one command or INSTALL-WITH-AI.md, don't change the port binding: if doctor reports `restrict_ports`, follow [If something goes wrong](INSTALL-WITH-AI.md#if-something-goes-wrong).

### Settings outside the app

Environment variables such as `ANTHROPIC_API_KEY` and `PUBLIC_URL`, for the [manual install](docs/manual-install.md#settings-outside-the-app) only. Don't change the compose files of a hub installed with the one command or INSTALL-WITH-AI.md.

## Back up and update

These commands are for the [manual install](docs/manual-install.md), which builds the hub locally. Installed with the one command or the AI guide? Use the guide's [Existing install / update](INSTALL-WITH-AI.md#existing-install--update) instead.

### Back up

Run these in the hub's folder. The hub stops for a moment so the database is saved in a consistent state.

```bash
docker compose stop
docker compose run --rm -T --entrypoint tar family-hub czf - -C / data photos > sproutwall-backup.tgz
docker compose start
```

`sproutwall-backup.tgz` now holds the whole household (the Docker volume whose name ends in `familyhub-data`) and your `photos` folder. Copy it somewhere safe, such as a USB stick. Keep it private: it holds the database and the hub's secret keys.

### Restore

On the same computer, or on a new one after the [install steps](docs/manual-install.md#start-it). Restoring replaces the household on this computer with the one in the backup, so back up first if the hub holds anything you want to keep.

```bash
docker compose stop
docker compose run --rm -T --entrypoint sh family-hub -c 'rm -f /data/sproutwall.db* /data/family-hub.db* && tar xzf - -C /' < sproutwall-backup.tgz
docker compose start
```

The `rm` first removes the hub's current database and its temporary side files, so only the database from the backup is left. This also works with a backup made before the rename to Sproutwall (`family-hub-backup.tgz`, which holds `family-hub.db`). The hub's automatic safety copies (the volume's `backups` folder, made before each database upgrade) are not removed by a restore. After a restore they can still hold the household that was on this computer before; if that household should not stay on this computer, delete that folder once the restored hub works: `docker compose exec family-hub sh -c 'rm -rf /data/backups'`.

### Update

Back up first. Then, in the hub's folder:

```bash
git pull && docker compose up -d --build --remove-orphans
```

Your household data stays in its Docker volume (`docker volume ls` shows a name ending in `familyhub-data`). The hub updates its database by itself when it starts. Before it changes the database, it saves a copy in the volume's `backups` folder and keeps the last five.

### Installed before the rename

Sproutwall used to be called Family Hub. If you installed it then, there is nothing to change:

- Keep using your `family-hub` folder, and update with the command above. GitHub forwards the old address.
- The hub keeps using your existing database (`family-hub.db`), volume and commands.
- Do not clone the project again into a new folder. Docker names the data volume after the folder, so a new folder starts with an empty household. To move to a new folder anyway, [back up](#back-up) in the old folder, then [restore](#restore) in the new one.

## Forgot the PIN

There is no way to reset the PIN from the web page. That is on purpose. On the computer that runs the hub, in the hub's folder, run:

```bash
docker compose exec family-hub node scripts/reset-pin.mjs 4827
```

Use your own new PIN instead of `4827`. The same PIN rules apply. Every screen then asks for the new PIN. If a screen still says to wait after too many wrong tries, restart the hub with `docker compose restart`.

Without Docker, run `npm run reset-pin -- 4827` in the project folder.

## Ask the Hub

Kids type a question and get a short, kid-friendly answer. It is **off until a parent turns it on**. Until then, questions are saved on the Ask tab with a note that no model is connected.

### Turn it on

On a [manual install](docs/manual-install.md), pick one and add it as described in [Settings outside the app](docs/manual-install.md#settings-outside-the-app). For a hub installed with the one command or INSTALL-WITH-AI.md, a way to turn it on is not written yet: don't edit its compose files.

- **Claude:** set `ANTHROPIC_API_KEY` to your own key from Anthropic. You pay for what the family asks.
- **A local model:** set `OLLAMA_URL` to an Ollama server, for example `http://192.168.1.60:11434` for Ollama on another computer. That Ollama must accept connections from the network. On a Raspberry Pi a local model is likely to be very slow (see the [Pi guide](docs/raspberry-pi.md#ask-the-hub-is-slow-or-does-not-answer)).

Then, on the manual install, run `docker compose up -d`.

### What is sent, and where

- **Where:** to Anthropic's API (`api.anthropic.com`) when `ANTHROPIC_API_KEY` is set. Otherwise to your Ollama server. If Claude fails and `OLLAMA_URL` is also set, the question goes to Ollama instead.
- **Each question:** the question text (up to 500 characters), the hub's safety rules, and the child's age band (under 6, 6-7, 8-12, or 13 or older) or "very young, may not read yet". The exact age is not sent. A question asked as a guest sends no age.
- **Names:** the child's first name is **not** sent, unless a parent turns on first-name sharing (below).
- **Daily tiles:** when a model is connected, the hub also asks it to write the daily quote, fact, mindset prompt and dinner question for the next few days. Those requests contain dates and the quotes already shown. They contain no family data.
- **What stays home:** every question and answer is saved in the hub's own database and shown on the Ask tab of any unlocked screen. The bridge that talks to the model does not log question text.
- **Limits:** at most 6 questions a minute, 100 a day, and 2 at the same time (`ASK_MAX_PER_MINUTE`, `ASK_MAX_PER_DAY`). A model that takes longer than 40 seconds counts as no answer.

### Share first names (optional)

Kids' first names are not sent unless you turn this on. In [Settings](#parent-settings), under **Ask the Hub privacy**, tick **Include the child's first name so answers can be personal**. Untick it to stop.

## Calendars

Sproutwall shows each person's calendar from a secret iCal link. It only reads. Events added on the wall stay on the wall.

### Add a link

1. **Find the link.** In Google Calendar, open the calendar's settings and copy **Secret address in iCal format**. In Apple Calendar, share the calendar as a public calendar and copy its `webcal://` link. Other calendar apps call it a published or shared `.ics` link.
2. Open [Settings](#parent-settings) and go to **Calendars**. Each person has a row, and there is one more row for the **Kids' shared calendar**.
3. Paste the link into the person's row and tap **Save**. The hub fetches the link once to check it is a calendar before saving it.
4. After saving, the row shows only **Linked** and the calendar service's name, for example `calendar.google.com`. The full link is never shown again. To change it, paste a new link. To stop using it, tap **Remove**: the events it brought in are removed with it.

If Settings says the link sends the hub somewhere it won't follow (more than 3 redirects, or from `https://` down to `http://`), copy the final secret address from your calendar app and paste that instead.

**Kids' shared calendar.** One calendar can hold all the kids' events. An event whose title starts with a kid's name and a dash or colon, like "Riley - Swim" or "Riley: Swim", goes to that kid only. Other events go to every kid. The names come from your Family list. If one kid's name starts another's, like "Jo" and "Jo-Ann", the longer name wins.

### How it works

- **How often:** the hub checks the links about every 15 minutes while a screen shows Today or Calendar, and right after you save a new link. It shows events from 2 weeks back to about 4 months ahead.
- **Which links:** `https://`, `webcal://` (treated as `https://`) and plain `http://` addresses on the public internet. Links to private network addresses are refused.
- **Redirects:** the hub follows up to 3 redirects and checks each new address the same way. It never follows an `https://` link to a plain `http://` one.
- **Size:** calendars larger than 10 MB are refused. A repeating event shows at most its first 500 times in that window, and one calendar at most its first 5,000 entries.
- **When a link stops working:** if the answer is not a calendar (for example an expired-link page or a sign-in page), the hub treats it as an error. That person keeps the events the hub already had until the link works again.

## Photos

The screensaver shows your photos. It starts after 10 idle minutes, or when someone taps the moon button.

- Put `.jpg`, `.jpeg`, `.png` or `.webp` files in the `photos` folder inside the hub's folder.
- Use file names with only letters, numbers, dots, dashes and underscores. Files with spaces or other characters in the name are skipped.
- New photos show up without a restart.
- Without photos, the screensaver shows quotes.

**Headshots.** Each person can have a square JPEG photo named `<member id>.jpg` in the `avatars` folder of the data volume:

```bash
docker compose exec family-hub mkdir -p /data/avatars
docker compose cp riley.jpg family-hub:/data/avatars/riley.jpg
```

A person's member id comes from their name when they are added:

- lowercase, accents removed, and dashes instead of spaces and other characters, up to 24 characters. "Ana Lucía" becomes `ana-lucia`;
- a name that starts with a digit gets `m-` in front;
- a name with no Latin letters at all (for example one written only in Korean or Arabic script) becomes `member`;
- if the id is taken, or is one of the reserved words `guest`, `auto` and `px`, the hub adds `-2`, `-3` and so on;
- the sample family's ids are `riley`, `quinn`, `sam`, `avery` and `jordan`.

Without a headshot, the sample family shows cartoon avatars, and everyone else shows the first letter of their name in a circle.

## Raspberry Pi

A Raspberry Pi 4 or 5 with a touchscreen makes a good kitchen hub. To install on a Pi, use [Install](#install) above. The [Raspberry Pi guide](docs/raspberry-pi.md) builds the hub on the Pi instead, and covers setting up the screen by hand and troubleshooting.

## For developers

To build Sproutwall from source with Docker, on any computer including a Mac or a Windows PC, see [Manual install](docs/manual-install.md). It is not the install for a family's kitchen screen.

Requirements: Node.js 22 (`engines` says `>=22`; CI and the Docker image use 22). If `better-sqlite3` has no prebuilt binary for your platform, you also need `python3`, `make` and a C++ compiler.

```bash
npm ci
cp .env.example .env
npm run dev
```

`npm run dev` (`scripts/dev.mjs`) starts the web app on port 3847 (listening on all interfaces) and the Ask the Hub bridge on `127.0.0.1:8787`. Missing secrets are generated into `data/` (`session-secret`, `bridge-token`), which git ignores. The database is `data/sproutwall.db` (`data/family-hub.db` in a checkout from before the rename). `.env.example` sets `REQUIRE_AUTH_FOR_READS=0`, so screens are not locked in development. Open <http://127.0.0.1:3847>.

Checks (CI runs all of them in one job named `check`):

```bash
npm run lint -- --max-warnings 0
npm run typecheck
npm test
npm run build
node scripts/check-pii.mjs
```

Other scripts: `npm run bridge` starts only the bridge, and `npm run reset-pin -- <PIN>` resets the PIN in `data/`.

**Next.js 16.** This is not the Next.js in older tutorials. APIs and file conventions changed. For example, request middleware is now `src/proxy.ts` (the `middleware` file convention was renamed to `proxy`). Read the guide for what you are changing in `node_modules/next/dist/docs/` first. See [AGENTS.md](AGENTS.md).

### Project layout

| Path | What is there |
| --- | --- |
| `src/app/<screen>/page.tsx` | Screens: `today`, `calendar`, `my-day` (Routines), `meals`, `lists`, `ask`, `reading`, `balance`, `level-up`, `progress`, `unlock` |
| `src/app/settings/` | The parent Settings screen (household, family, calendars, Ask privacy, PIN change) |
| `src/app/api/` | Route handlers. Routes with parent-only actions check the parent session again themselves (`src/lib/guard.ts`). Parent settings are `src/app/api/settings/parent/`. |
| `src/proxy.ts` | Access policy for every request: same-origin writes, screen unlock, kid writes vs parent writes |
| `src/lib/session.ts`, `guard.ts`, `auth.ts` | Signed device (30 days) and parent (15 minutes) cookies, route-level checks, PIN hashing |
| `src/lib/pin-attempts.ts`, `weak-pin.ts` | Wrong-PIN limits (per screen, plus two hub-wide ceilings) and PIN rules |
| `src/lib/safe-next.ts` | Keeps the after-unlock redirect on this hub |
| `src/lib/household.ts` | The `members` table: validation, member ids, add, hide, replace the household |
| `src/lib/member-theme.ts` | The member color palette and per-member CSS variables |
| `src/lib/household-settings.ts` | Validation and saving for parent settings, including the calendar-link check |
| `src/lib/family.ts` | Member types and the household model shared with the client |
| `src/lib/safe-fetch.ts` | Outbound fetch guard (public addresses only, size caps) used for calendars and covers |
| `src/lib/ics.ts`, `calendar.ts` | iCal import (redirects, shared kids' feed) and the calendar model |
| `src/lib/db.ts` | SQLite schema, migrations and the sample family seed |
| `src/lib/queries.ts` | Most data access (ledger, routines, meals, books). Large; planned to be split by domain. |
| `src/lib/paths.ts` | Where files live (`DATA_DIR`, `PHOTO_DIR`) |
| `src/components/` | UI components, including `PersonEditor.tsx` (one person's name, age, reading box and color) and `MembersProvider.tsx` (the household for client components) |
| `bridge/` | Ask the Hub bridge (`ask-bridge.mjs`) and its prompts (`prompt.mjs`) |
| `scripts/` | Dev and production start, secret generation, `reset-pin`, the PII check |
| `Dockerfile`, `docker/entrypoint.sh`, `docker-compose.yml` | Container build and start |
| `tests/` | Vitest tests. `tests/setup.ts` gives each test file its own temporary data folder. |
| `docs/` | This guide's longer pages and the [skills proposal](docs/architecture/skills.md) |

## Contributing

Contributions are welcome, including small ones. Start with [CONTRIBUTING.md](CONTRIBUTING.md). Please follow the [Code of Conduct](CODE_OF_CONDUCT.md). Report security problems privately as described in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE).
