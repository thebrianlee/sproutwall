# Install from your laptop over SSH (no keyboard on the Pi)

This guide installs Sproutwall on a Raspberry Pi from your laptop. The Pi needs its screen, but no keyboard or mouse. You type everything on the laptop, in an SSH window that runs commands on the Pi.

New to all of this and have a keyboard for the Pi? [The step-by-step guide](INSTALL-BEGINNERS.md) does the same with the keyboard on the Pi.

## Before you start

**If your family already uses Sproutwall (or Family Hub), don't reinstall it.** Writing a card erases it, household included. Use a new card, or one whose contents are backed up somewhere else.

You need:

- A Raspberry Pi 4 or 5 with its screen attached, and a power supply.
- A microSD card of 32 GB or more, and a card reader for your laptop.
- Your laptop on your home Wi-Fi (not a guest network). The Pi joins the same network.
- [Raspberry Pi Imager](https://www.raspberrypi.com/software/) on the laptop.

Never type a password or the parent PIN into a chat AI, a message or a GitHub issue. They go only into the Pi's own password prompt and the hub's own page.

## Step 1: Write the card with Raspberry Pi Imager

Put the card in the laptop's reader and open Imager. Choose:

1. **Device:** your Pi model.
2. **OS:** Raspberry Pi OS (64-bit), the version with the desktop.
3. **Storage:** the microSD card. Check the name and size twice: this card gets erased.
4. **Customisation:**
    - **Hostname:** `hub`. If another device on your network is already called `hub`, choose another name, such as `hub2`, and use it wherever this guide says `hub`.
    - **Localisation:** where you live (Imager may ask for your capital city), your time zone and keyboard layout. The hub takes its time zone from the Pi.
    - **User:** a username and a password you will remember. Keep the password to yourself.
    - **Wi-Fi:** your home network and its password.
    - **Remote access:** turn **SSH** on, with **password authentication**.
5. **Write.** Imager writes the card, then checks it (verifying).

If Imager says "Error reading from storage", or that verifying failed, see [If Imager can't read the card](INSTALL-BEGINNERS.md#if-imager-cant-read-the-card).

When Imager is done, put the card in the Pi. Connect the screen (and its touch cable, if it has one) as the screen's instructions say, then switch the Pi on.

## Step 2: Log in to the Pi from your laptop

The first start takes a few minutes: the Pi sets itself up and may restart once. Wait until its desktop shows on the screen.

On the laptop, open **Terminal** (Mac or Linux) or **PowerShell** (Windows) and type, with your own username:

```bash
ssh <your-username>@hub.local
```

- The first time, it asks whether to trust the Pi's fingerprint. On your own home network, type `yes`.
- Then type the Pi's password. Nothing shows while you type; that is normal.
- The prompt changes to `<your-username>@hub`. From now on, everything you type in this window runs on the Pi.

If ssh says **REMOTE HOST IDENTIFICATION HAS CHANGED**, this laptop has logged in to a Pi called `hub` before, for example with an earlier card. Run `ssh-keygen -R hub.local` on the laptop, then log in again.

If it says it can't find `hub.local`, wait a minute and try again. Still nothing after 5 minutes: find the Pi in your router's list of devices and use its address instead, for example `ssh <your-username>@192.168.1.50`.

## Step 3: Run the one command

In the SSH window, paste this and press Enter. Run it as yourself, never with `sudo` in front:

```bash
curl -fsSL https://raw.githubusercontent.com/thebrianlee/sproutwall/main/install.sh | bash
```

It asks these questions, in this order. For the yes/no questions in this table only `y` (or `yes`) goes on; anything else, or just Enter, ends with nothing changed.

| Question on screen | What it means | Your answer |
| --- | --- | --- |
| How does the screen hang? (1 to 5) | Which way the kitchen screen is turned. 5 = no kiosk, phones and tablets only. | Enter for portrait, or the number |
| Do you approve this plan? | It lists every command it will run as administrator, with why and how to undo it. Read it. | `y` |
| Is all of this true for the network this device is on? | Your own home network: not a guest network, no port forwarding, no tunnel. | `y` if true |
| SSH: YOUR RESPONSIBILITY. Do you understand and accept this? | While SSH is on, anyone on your home network who knows the Pi's password could log in. Keeping it safe is on you. | `y` to go on |
| The `sudo` password prompt, if it asks | Your Pi password, for a read-only look at the SSH settings, then for the installs. On some Pis `sudo` doesn't ask. | the Pi password |

Then it installs the tools, downloads the hub, checks the hub's signature and starts it. This is the long part. Let it run, and keep the SSH window open. Keep the laptop awake and plugged in until the command finishes: if the laptop sleeps, the SSH session closes and the install stops partway.

If the SSH window closed before the end, log in again (step 2) and type `ls ~/sproutwall`:

- **It prints `No such file or directory`:** the install had not got the hub yet. Run the one command again. If it stops with a `Stopped:` line, follow it. If the lines above that say to run `sudo dpkg --configure -a`, run it, then run the one command again.
- **Anything else** (a list of files, or nothing at all): the install had already started getting the hub. Don't run the one command again: it stops at once when it finds a hub on the device, because it never installs a second one. Don't delete the folder either. Start over instead: write the card again (step 1), then log in and run the one command (steps 2 and 3). Writing the card erases what this install put on it, including a household you may have set up in step 4. On a new card that is all there is, and you set the household up again in a few minutes. When you log in again, ssh warns that the Pi's identification has changed: see step 2. If you would rather not start over, tell us with an [install report](https://github.com/thebrianlee/sproutwall/issues/new?template=install_report.yml).

## Step 4: Set up the household, the screen, and finish

From here on, the hub is installed and running. Answer only what the last line in the SSH window asks:

- A line that ends with `(press Enter)` waits for Enter.
- A question that ends with `[y/N]` needs `y` to say yes. Enter alone there means no.

1. **"Set up your household now."** The command waits and prints an address such as `http://192.168.1.50:3847`. Open it in your laptop's web browser. On **Set up the house**, choose the sample family or your own, choose what the wall shows, then the house details and the **parent PIN** (typed twice). Tap **Open the wall**. Go back to the SSH window and press Enter.
2. **The screen.** If you chose 5 (no kiosk), this step is skipped. Otherwise the screen setup prints what it did. Then one of these happens:
    - **The last line asks you to tap and ends with `(press Enter)`.** Tap the four corners and the centre of the Pi's screen: each tap must land under your finger. Then press Enter. If the picture has not turned yet, it turns after the restart: check the taps then.
    - **There is no `(press Enter)` line,** and the setup says the new settings apply at the next login. The picture turns only after the restart. Don't press Enter, even though the setup's own text says to tap the corners: answer the next question (3), if it comes. You check the screen after the restart.
    - **"Try the screen setup again?"** It did not find the screen or its touch connection, or found more than one. Reconnect the screen and its touch cable, unplug any other screen, wait ten seconds, then type `y`. `n` leaves the Pi without the kiosk.
    - **"The screen is not set up."** The hub still works from phones and tablets. The message says how to set up the screen later.
3. **"Run it now? sudo asks for your password."** It asks only if the Pi's desktop doesn't log in by itself yet. Without that, the hub doesn't come back on the screen by itself after the restart or after a power cut. Type `y` (Enter alone means no), then the Pi password if `sudo` asks. If you answered no by mistake, type `sudo raspi-config nonint do_boot_behaviour B4` in the SSH window before the restart (6).
4. **"Sproutwall is installed."** It prints a summary and a phone check: on a phone on the same Wi-Fi, open the address it shows. The phone must show **Unlock this screen** and ask for the PIN. It must never show the family without asking.
5. **"Turn SSH off now?"** `y` is the safe choice. `n` keeps SSH on, and keeping the Pi safe is then on you. Either way, this SSH window stays open until the restart.
6. **Restart:** type `sudo reboot`. The SSH window closes.

After the restart, the hub comes back on the Pi's screen by itself, the right way up, and asks once for the parent PIN: type it on the screen. Tap the four corners and the centre again. With no kiosk (choice 5), the screen shows the normal desktop; use the hub from phones and tablets. Either way, a phone on the Wi-Fi must still show **Unlock this screen**. The install is done.

If you didn't choose 5 and, a few minutes after the restart, the screen shows a login screen or the normal desktop instead of the hub, the hub can't open by itself yet: usually the desktop doesn't log in by itself, or the screen setup didn't finish. SSH is off now, so plug a USB keyboard and mouse into the Pi. Log in on its screen if it asks, open **Terminal** and run `sudo raspi-config nonint do_boot_behaviour B4`, then `sudo reboot`. If the hub still doesn't come back, or taps land in the wrong place, run `cd ~/sproutwall && ./scripts/sproutwall setup kiosk --check` in that Terminal and follow [step 7 of the AI install guide](../INSTALL-WITH-AI.md#step-7-set-up-the-screen).

The [AI install guide](../INSTALL-WITH-AI.md#step-8-remove-the-assistant-and-check-once-more) has the final check, for when you have a keyboard on the Pi or kept SSH on.

## If it stops

If something is wrong, the command prints one line that starts with `Stopped:`. That line says why and what to do. It never deletes your files or the hub's data.

- Do what the line says. Don't work around it, and don't delete the `sproutwall` folder or anything Docker made.
- If you answered `n`, or just Enter, to one of the yes/no questions in step 3, it ends with a plain message that nothing was changed. That is not an error: run the command again when you're ready.
- The questions in step 4 don't end the install: by then the hub is installed and running. `n` there only skips that one thing (another screen setup try, autologin or turning SSH off), and the message says how to do it later. Don't run the one command again after that: it stops at once, because the hub is already there.

Please tell us how it went, whether it worked or not, with an [install report](https://github.com/thebrianlee/sproutwall/issues/new?template=install_report.yml). Copy the `Stopped:` line exactly if there was one. Share nothing else: no passwords, no PIN, no logs or screenshots of your network.

## Optional: let a free AI chat walk you through it

Open a free AI chat in your laptop's web browser, such as ChatGPT, Claude or Gemini. Keep the SSH window from step 2 open next to it, and paste this into the chat:

```text
Help me install Sproutwall on my Raspberry Pi, set up for our family. I'm logged in to the Pi over SSH from my laptop, and I will run this one command myself in that SSH window:

curl -fsSL https://raw.githubusercontent.com/thebrianlee/sproutwall/main/install.sh | bash

The guide is https://github.com/thebrianlee/sproutwall/blob/main/INSTALL-WITH-AI.md, and I'm in its tier B. Explain each question the command asks me, and help me if it stops. Ask me whatever you need.
```

Copy each command it gives you into the SSH window, and tell it only the short result it asks for. Never give it your passwords or the PIN.
