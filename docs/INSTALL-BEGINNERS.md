# Install Sproutwall: a step-by-step guide for beginners

This guide is for you if you have never used a Raspberry Pi, a Terminal or GitHub, and you have a keyboard for the Pi. No keyboard? [Install from your laptop over SSH](INSTALL-OVER-SSH.md) instead. If you can use a laptop and a web browser, you can do this. A chat AI (an AI assistant you talk to on a web page) is optional.

It takes you from "I have a Pi, a screen and an SD card" to Sproutwall on your kitchen screen. In this guide, "the hub" means Sproutwall running on your Pi. You prepare the card and start the Pi yourself. Then you install the hub in one of two ways: with [one command](#5-install-with-one-command-no-ai-needed) that asks a few questions, or with [a chat AI](#6-install-with-your-ai-assistant) that walks you through [INSTALL-WITH-AI.md](../INSTALL-WITH-AI.md) one command at a time. That page stays the full reference. This one gets you to the point where the install takes over, tells you what you will see on the way, and lists what never to share. This guide uses a keyboard on the Pi. To install from your laptop over SSH instead, with no keyboard on the Pi, see the README's [three install options](../README.md#choose-how-to-install).

> **Early preview.** The guided install is new. It has been tested several times in a Debian 13 virtual machine (a computer simulated inside another computer), with an AI agent following the guide and the household set up on the screen. It has not yet been tested end to end on a real Raspberry Pi. The one-command install is new too, and has not been tried on a Raspberry Pi yet. If you try either, please tell us how it went with an [install report](https://github.com/thebrianlee/sproutwall/issues/new?template=install_report.yml), whether it worked or not.

## 1. What you need

- [ ] A **Raspberry Pi 4 or Raspberry Pi 5**, with its power supply. The official power supply for your model is the safe choice: a weak one causes strange crashes.
- [ ] A **screen**. A touch screen is best for a kitchen. Connect it the way the screen's own instructions say: many HDMI touch screens need a second, USB cable for touch. The automatic screen setup needs a touch screen. Any other screen works too, but is set up [by hand](raspberry-pi.md#set-it-up-by-hand).
- [ ] A **microSD card of 32 GB or more**, and an **SD card reader** for your laptop (a slot in the laptop, or a small USB reader).
- [ ] A **USB keyboard**. Strongly recommended for the setup: you will paste commands and type passwords. A mouse helps too, and a touch screen also works as a mouse.
- [ ] Your **home Wi-Fi name and password**. Use your own home network, not a guest network. A network cable works too.
- [ ] **About an hour.** Much of it is waiting for downloads.

If this Pi already runs something you care about, use a different card and keep the old one safe. The next section erases everything on the card you use.

## 2. Put Raspberry Pi OS on the card

Raspberry Pi OS is the Pi's operating system, like Windows or macOS on a laptop. You put it on the card from your laptop with Raspberry Pi Imager, the official free tool.

1. On your laptop, download and install [Raspberry Pi Imager](https://www.raspberrypi.com/software/). This guide follows Imager 2. If your Imager looks very different, get the current version from that page.
2. Put the microSD card in your laptop and open Imager. It walks you through six screens: **Device**, **OS**, **Storage**, **Customisation**, **Writing** and **Done**. Raspberry Pi's [Getting started](https://www.raspberrypi.com/documentation/computers/getting-started.html) page shows each screen with pictures.

- **Device:** choose your Pi model.
- **OS:** choose **Raspberry Pi OS (64-bit)**, the version with the desktop. Not "Lite": Lite has no desktop, and you need one for the web browser and the kitchen screen.
- **Storage:** choose the microSD card. **Double-check that it is the card and not another drive: everything on it is erased.** Leave **Exclude system drives** switched on. It hides your laptop's own drives from the list.
- **Customisation:** fill this in; don't skip it. These settings match [step 1 of the install guide](../INSTALL-WITH-AI.md#step-1-put-the-system-on-the-card):
  - **Hostname:** `hub`. This is the Pi's name on your home network.
  - **Localisation:** Imager asks for a capital city and fills in the time zone and keyboard layout from it. Check both, and change the time zone if yours is different. The hub takes its time zone from the Pi later.
  - **User:** a username and a password. The username must start with a lowercase letter; use only lowercase letters and numbers. Keep the password to yourself. You type it into the Pi when a command asks for it.
  - **Wi-Fi:** your home network's name and password. Imager needs the password. If someone else in your home keeps it, leave Wi-Fi out of Imager (clear the network name). They can type the password on the Pi later, with the network icon on the bar at the top of the screen. Or use a network cable.
  - **Remote Access:** leave **Enable SSH** off. SSH lets another computer control the Pi over the network. This install doesn't use it.
  - **Raspberry Pi Connect:** if Imager shows it, leave it off. It is a service for reaching your Pi from outside your home, and the hub stays on your home network.
- **Writing:** check the summary. Writing erases everything on the card, so first make sure it may be erased. Go on only if the card is new or blank, or the card's owner says, in their own words, that anything on it (such as a hub that was set up before) is backed up somewhere other than the card and that the card may be erased. If you're not sure, stop: don't write the card, and ask the owner first. Then choose **Write**. Imager warns that it will erase the card. Confirm (**I understand, erase and write**) only if you chose the right card. Imager then writes the card and checks it. This can take a while.
- **Done:** choose **Finish**, then take the card out of the laptop.

**On a Mac:** after writing, macOS may say the disk is not readable. Choose **Ignore**. Don't choose Initialize: that would erase the card. Part of the card uses a Linux format that macOS can't read, and that is normal. **On Windows,** if it offers to format the card, choose Cancel, for the same reason.

### If Imager can't read the card

If Imager says "Error reading from storage. SD card may be broken", or that verifying the write failed, the card is often fine. Try these in order:

1. Quit Imager.
2. If the microSD card sits in a full-size SD adapter, find the small lock switch on the adapter's side and slide it to the unlocked position.
3. **On a Mac:** open System Settings, then Privacy & Security, then Files and Folders. Find Raspberry Pi Imager and allow it to use removable volumes. The names can differ a little between macOS versions.
4. Take the card out and put it back in. Don't open it in Finder or File Explorer; go straight to Imager.
5. Try another card reader, or another USB port. Plug the reader into the computer itself, not through a hub or dock.
6. If the write finishes and only the verifying step fails, write again: it often passes the second time. You can also select **Skip verification** while Imager is verifying (Raspberry Pi's own [Imager guide](https://www.raspberrypi.com/documentation/computers/getting-started.html#install) describes it). Then a bad write goes unnoticed: if the Pi doesn't start or its desktop doesn't appear after five minutes, write the card again.
7. If it still fails, use another card.

## 3. Start the Pi

> **From here on, the Pi does the work.** Everything after writing the card happens on the Pi itself, in its own Terminal and its own web browser. Your laptop's job ended when the card was written: Sproutwall is never installed on the laptop and copied over.

1. With the Pi unplugged, connect the screen (and its touch cable, if it has one) as the screen's instructions say.
2. Put the microSD card in the Pi's card slot.
3. Plug in the keyboard, and a mouse if you have one.
4. Plug in the power last. The Pi switches on by itself.

The first start takes a few minutes, and the Pi may restart once by itself. Wait for the desktop to appear. Because you filled in the settings in Imager, it should not ask setup questions. If it does, give the same answers you gave in Imager. If it shows a login screen, log in with the username and password you chose.

**Open the Terminal.** The Terminal is a window where you type commands for the Pi. Click the Raspberry Pi icon in the top-left corner of the screen to open the main menu, then choose **Accessories**, then **Terminal**. There may also be a Terminal button on the bar at the top of the screen.

**Open the web browser.** Click the web browser button on the bar at the top of the screen, or find the browser in the main menu. Raspberry Pi OS comes with Chromium and Firefox. Either one is fine.

Tip: put the browser and the Terminal side by side, so you can copy from one and paste into the other.

## 4. Terminal basics in five lines

- **Paste** into the Terminal with **Ctrl+Shift+V**. Plain Ctrl+V doesn't paste there.
- **Enter** runs the command you pasted. Wait until it finishes before the next one.
- When a command asks for your **password**, typing shows nothing, not even dots. That's normal: type it and press Enter.
- When a command asks `[Y/n]`, press **Enter** to answer yes. When it asks `[y/N]`, Enter alone means no: type `y`, then press Enter.
- **Never type commands by hand.** Copy them from the browser, so no letter is wrong.

## 5. Install with one command (no AI needed)

One command runs the install guide's steps for you and asks a few questions on the way. Run it in the Pi's own Terminal. To copy the line below, open this page in the Pi's web browser.

1. **Wait 3 to 5 minutes** after the desktop first appears. A new Pi finishes its own first-start setup in the background. The command also waits for that by itself (on Raspberry Pi OS, for up to 10 minutes).
2. **Open the Terminal** (section 3), paste this line and press Enter. Don't put `sudo` in front of it.

   ```bash
   curl -fsSL https://raw.githubusercontent.com/thebrianlee/sproutwall/main/install.sh | bash
   ```

   It checks the Pi first, and changes nothing if something is wrong: for example a 32-bit system or an unsupported Pi model. It never touches a hub that is already on this Pi, or its data. If it finds one before installing anything, nothing is changed; if it only finds one after installing the tools, it stops there and says so.
3. **Answer its questions,** in this order:
   - **How does the screen hang?** Press Enter for portrait, the usual choice for a kitchen wall, or type a number from 1 to 5 from the list it shows (5 is no full-screen setup). Only on Raspberry Pi OS.
   - **The install plan.** It lists every command it will run as administrator (`sudo`), why, and how to undo it. Read it, then type `y` and press Enter.
   - **Maybe your Pi password, right away.** Only if Docker was already on this Pi: `sudo` asks for it so the command can look, read-only, for a hub that is already there. On a freshly written card this doesn't happen.
   - **The home-network rule:** this is your own router, it is not a guest or public network, nothing on the router forwards a port to the Pi, and no tunnel or remote-access service exposes it. If all of that is true, type `y` and press Enter.
   - **Your Pi password,** when `sudo` asks for it as the installs start: the one you chose in Imager. Type it only there, into `sudo`'s own prompt.

   For the plan and the home-network rule, only `y`, `yes`, `Y`, `Yes` or `YES` goes on; spaces and tabs before or after the answer are ignored. Anything else, or Enter alone, cancels: it ends with a message that nothing was changed. That is not an error, and there is no `Stopped:` line.
4. **Then it works on its own** for a while: system updates and the tools (git, Docker and the GitHub CLI, as described in [section 6](#6-install-with-your-ai-assistant)), the code in a folder named `sproutwall`, the check that the hub's image really was built by the project, and starting the hub. Nothing starts unless the image check passes. Leave it running.
5. **Set up your household.** When it says "Set up your household now", open the web browser at `http://localhost:3847` on the Pi's screen. Set up your family and choose the parent PIN alone, as [section 6, point 7](#6-install-with-your-ai-assistant) describes. The command never asks for, reads or shows the PIN. When you have tapped **Open the wall**, go back to the Terminal and press Enter. If setup is not finished yet, it says so and waits.
6. **The screen setup** (Raspberry Pi OS, unless you chose 5). The picture turns the way you chose. When the Terminal asks you to tap (the line ends with `(press Enter)`), tap the four corners and the center of the screen: each tap must land under your finger. Then press Enter. If it says instead that the new settings apply at the next login, it doesn't ask for Enter: don't press it, and check the taps after the restart. If it offers to turn on automatic desktop login, so the hub comes back by itself after a power cut, type `y` and press Enter (Enter alone means no).
7. **The summary.** It ends with "Sproutwall is installed", a phone check (open the address it shows on a phone on your Wi-Fi: it must ask for the PIN and must not show the family) and the final check to run after a restart. Then restart the Pi by running `sudo reboot`. After the restart, if the hub is full screen, press Alt+F4 to reach the desktop, open the Terminal and run the final check:

   ```bash
   cd ~/sproutwall && ./scripts/sproutwall doctor --phase final --tier C --kiosk on
   ```

   Use `--kiosk off` instead if the screen was not set up. It passes with `Result: pass`, or with `Result: unknown` when the only unknown is `app_bind` / `confirm_trusted_lan` (see [section 6](#6-install-with-your-ai-assistant)). In this preview, after an install over SSH, `ssh_policy` unknown and `temporary_access` unknown (`retry_local`) are also acceptable here, but only when SSH is off and `systemctl is-active ssh.service ssh.socket` prints `inactive` for both (the guide's [step 8](../INSTALL-WITH-AI.md#step-8-remove-the-assistant-and-check-once-more)). If you chose to keep SSH on, `ssh_policy` and `temporary_access` results caused by SSH being on are expected instead, and every other check must pass (same step 8). Then see [section 8](#8-when-its-done).

**If it stops,** it prints one line that starts with `Stopped:` and says why and what to do. It never deletes your files or the hub's data and never works around a problem, and the line usually says whether anything was changed and whether it is safe to run the command again. Share only that line and the status check's output, as [section 9](#9-if-you-get-stuck) says. Declining a question is not a stop: see point 3.

## 6. Install with your AI assistant

From here a chat AI guides you through [INSTALL-WITH-AI.md](../INSTALL-WITH-AI.md). That guide calls this **tier C**: the AI only chats, and you paste each command into the Pi's Terminal yourself. Nothing is installed for the AI on the Pi.

1. **Open your chat AI** in the Pi's web browser and sign in.
2. **Paste this prompt** from the guide's [Start here](../INSTALL-WITH-AI.md#start-here-what-to-tell-your-ai). It gives the AI the one command and the install guide's address:

   ```text
   Help me install Sproutwall on my Raspberry Pi, set up for our family. I'm at the Pi's own Terminal and will run this one command myself:

   curl -fsSL https://raw.githubusercontent.com/thebrianlee/sproutwall/main/install.sh | bash

   The guide is https://github.com/thebrianlee/sproutwall/blob/main/INSTALL-WITH-AI.md. Explain each question the command asks me, and help me if it stops. Ask me whatever you need.
   ```

   A chat AI can't see your Pi, and it may not read the whole guide, so the prompt names the command itself. The AI explains the command's questions as they come, the same ones as in [section 5](#5-install-with-one-command-no-ai-needed). If you'd rather go step by step, tell it, and it gives you one block at a time, as below. If your AI can't open web pages, paste the text of [INSTALL-WITH-AI.md](../INSTALL-WITH-AI.md) into the chat instead.

3. **The AI asks first** whether the card might hold another household's data, such as a hub that was set up before. It may not decide this itself. Answer truthfully, in your own words: say what you checked before you chose **Write** in section 2, and that you then wrote a fresh system to the card. If you're not sure, say so; the AI then stops.
4. **Then it asks at most five questions**, each once ([the five decisions](../INSTALL-WITH-AI.md#the-five-decisions)):
   - **Who runs the commands?** You, pasting into the Terminal (tier C). The AI may work this out itself.
   - **How does the screen hang?** Portrait (tall) is the usual choice for a kitchen wall. Landscape (wide), either one turned upside down, or no full-screen setup at all also work.
   - **Do you approve the install plan?** See the next point. It also asks you to confirm the home-network rule: this is your own router, it is not a guest or public network, nothing on the router forwards a port to the Pi (port forwarding lets the internet reach a device at home), and no tunnel or remote-access service exposes it.
   - **Your household:** the sample family or your own. You set this up yourself on the hub's screen (point 7).
   - **Which features show?** One screen during setup. **Skip, use recommended** keeps everything except Ask the Hub. Ask the Hub stays off unless you turn it on, because it sends the questions kids type to an AI service. You can change this later in Settings → Modules.
5. **The install plan comes before any password.** The AI shows every command that runs as administrator once, before the first one: what it does, why it is needed and how to undo it. These commands start with `sudo` ("run as administrator") and ask for the Pi's password in the Terminal. Read the plan, then say yes or ask questions. Your yes covers that plan only.
6. **One block at a time.** The AI gives you one block of commands. Copy it, paste it into the Terminal, press Enter and wait until it finishes. Then tell the AI only the short result it asks for, such as `64-bit OK`, `exit 0` or `healthy`. Don't copy whole Terminal output, logs or screenshots.
7. **Household setup: you do this alone.** When the AI reaches this step, it waits and doesn't look. On the Pi's own screen, open the web browser at `http://localhost:3847` (the hub on this Pi). You see **Set up the house**:
   1. Pick **Set up my family**, or **Try it with the sample family** (the Calders, a made-up family) for a first look.
   2. **What should your wall show?** Choose, or tap **Skip, use recommended**.
   3. **The house:** names, the time zone (filled in from the Pi; keep it), the location for the weather (a nearby town center is close enough), and the **Parent PIN**, typed twice.
   4. Tap **Open the wall**. Then tell the AI only "done".

   Choose the PIN yourself and never tell it to the AI. It must be 4 to 8 digits. Easy PINs such as `1234`, `0000` or `7777` are refused. Use 6 or more digits if people you don't fully trust, such as guests, use your Wi-Fi. The README's [First-run setup](../README.md#first-run-setup) explains every field.

**What you will see on the way.** The AI follows the guide's steps:

- **Step 2:** a check that the Pi runs a 64-bit system.
- **Step 3:** system updates, then three tools: git (downloads the code), Docker (runs the hub in its own sealed box, called a container) and the GitHub CLI, `gh` (only checks the hub's download; it never signs in). Then a restart, and the code goes into a folder named `sproutwall`. Updates and downloads can take a while.
- **Step 4:** a check that the hub's ready-made app (the image) really was built by the project from the published code. Nothing starts unless this check passes.
- **Step 5:** the hub starts.
- **Step 6:** you set up the household (point 7 above). Then the AI asks you to open the hub on a phone: it must ask for the PIN and must not show the family.
- **Step 7:** the screen setup. The picture turns the way you chose, and you tap the corners to check touch.
- **Step 8:** a last check and a restart.

In steps 5, 6 and 8 the AI has you run a status check called `doctor`. On a home network, one check normally comes back `unknown`: `app_bind`, with the action `confirm_trusted_lan`. The Pi can't see inside your router, so it asks you to confirm the home-network rule. That one is expected. Any `fail`, or any other `unknown`, means stop, and the AI tells you what to do.

## 7. Never share

Never paste these into a chat, an issue or a screenshot, not even for the AI that is helping you:

- the parent PIN;
- the Pi's password;
- the Wi-Fi password;
- calendar links (the secret calendar addresses the hub reads);
- tokens and API keys (secret codes that let a program use an account).

Type them only into the hub's own screen, into the Terminal when a command asks, or into a service's own sign-in page.

Never run these, even if an AI suggests them:

- `docker compose down -v`: it deletes the household's data;
- `docker volume rm`: it can delete the household's data too;
- deleting the `sproutwall` folder: it is the hub's folder;
- anything that "turns off a check", skips the image check, turns the screen lock off or opens the hub to the internet.

If an AI suggests something that is not in the guide, stop and ask in [Discussions](https://github.com/thebrianlee/sproutwall/discussions) before you run it.

## 8. When it's done

- After the screen setup and the restart, the Pi opens the full-screen hub by itself. It asks once for the parent PIN to unlock this screen: type it yourself. The unlock lasts 30 days on that screen. From then on, the hub comes back by itself every time the Pi starts.
- **Tap the four corners and the center of the screen.** Each tap must land under your finger. If it doesn't, see section 9.
- Phones, tablets and laptops on the same Wi-Fi can open the hub too. The README's [Open it from a phone or tablet](../README.md#open-it-from-a-phone-or-tablet) shows how. Each new screen asks for the PIN once.
- If you used a chat AI, close the chat and sign out of it in the Pi's browser.
- Keep the `sproutwall` folder. It is the hub's folder.
- For backups, and before any update, read [Existing install / update](../INSTALL-WITH-AI.md#existing-install--update). Don't use the README's update command on this install: it builds the hub differently.

## 9. If you get stuck

- **Stop the install** when a step fails, the install command stops, or the AI says stop. Don't try fixes that are not in the guide.
- **Share only two things,** with the AI or anyone else:
  1. the short result the step asked for, such as `exit 1`, or the one line a step printed to say why it stopped (with the one-command install, the line that starts with `Stopped:`);
  2. the output of the status check below.

  Don't copy whole Terminal output, and never paste logs, config files or screenshots of the hub.
- **The safe status check.** Once the `sproutwall` folder is on the Pi and the hub has started, run this. It only reads and changes nothing, and its output is safe to share by design:

  ```bash
  cd ~/sproutwall && ./scripts/sproutwall doctor --json --phase running --tier C
  ```

  Each check that does not pass names an action. [If something goes wrong](../INSTALL-WITH-AI.md#if-something-goes-wrong) explains each one.
- **Starting over** with a freshly written card (section 2) is often the fastest fix on a new setup. Do it only while the hub holds nothing you want to keep: writing the card erases everything on it.
- **Where to ask:** send an [install report](https://github.com/thebrianlee/sproutwall/issues/new?template=install_report.yml) (whether it worked or not), and ask questions in [Discussions](https://github.com/thebrianlee/sproutwall/discussions). Say which step stopped and give its short result and the status check's output: no logs, names or links. Report security problems privately, as [SECURITY.md](../SECURITY.md) says.

## 10. Undo

To go back to the setup the Pi had before:

1. If the hub is full screen, press **Alt+F4** on the keyboard to close it.
2. Shut the Pi down from the main menu (the Raspberry Pi icon in the top-left corner). When the screen goes dark, wait a few seconds, then unplug the power.
3. Swap the card for your old one and plug the power back in.

Your Sproutwall card keeps the hub and its household. Put it back in the same way to return to the hub.

- To stop the full-screen hub but keep the hub running for phones: [Undo the kiosk](../INSTALL-WITH-AI.md#undo-the-kiosk).
- If a Pi already runs Sproutwall, or to back up a hub you installed with this guide: [Existing install / update](../INSTALL-WITH-AI.md#existing-install--update).
