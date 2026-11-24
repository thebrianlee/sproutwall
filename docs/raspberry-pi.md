# Sproutwall on a Raspberry Pi

This guide sets up Sproutwall on a Raspberry Pi, with an optional touchscreen that shows the hub full screen. You do not need to be a programmer. You will copy a few commands into a terminal.

Plan for an evening. Most of the time is waiting for downloads and the first build.

**Most people don't need this page.** The easiest way to install is [the one command](../README.md#with-one-command): run it in the Pi's Terminal and it installs the published, pre-built image for you, with no build. New to Raspberry Pi? Start with [the step-by-step guide](INSTALL-BEGINNERS.md). To install the pre-built image one step at a time, with or without an AI assistant, see [INSTALL-WITH-AI.md](../INSTALL-WITH-AI.md). This page builds the app on the Pi itself instead.

## What works

**Supported:**

- Raspberry Pi 4 or Raspberry Pi 5. Building the app on the Pi, as this page does, needs about 4 GB of memory (see "The build runs out of memory" below). The prebuilt preview image in [INSTALL-WITH-AI.md](../INSTALL-WITH-AI.md) needs no build; its minimum memory is not measured yet. That guide also lists the other supported devices.
- Raspberry Pi OS **64-bit**, Bookworm or later.
- An SSD on USB (best), or a good microSD card rated **A2**. Cheap cards make the Pi slow and can wear out. 32 GB or larger leaves room for updates and photos.
- The official power supply for your Pi model. A weak supply causes strange crashes.
- Optional: a screen. The kiosk tool in [Step 6](#step-6-show-the-hub-full-screen-on-the-pis-own-screen-optional) needs one touch screen on HDMI or DSI; A screen without touch can be set up by hand.

**Not supported:**

- 32-bit Raspberry Pi OS. Docker Engine 29 and later no longer ship 32-bit packages for it, and the database library has no ready-made 32-bit version, so it would need a slow compile.
- Raspberry Pi Zero, Pi 1, Pi 2 and Pi 3. They are too old or too small for this app.

## Step 1: Put Raspberry Pi OS on the card

1. On your regular computer, install [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Plug in the microSD card or SSD.
3. In Imager, choose your Pi model, then **Raspberry Pi OS (64-bit)**. Pick the version with the desktop if you will attach a screen. Then choose the card.
4. When Imager offers to customize the system (the button may say **Edit Settings** or **Customisation**, depending on the Imager version), set:
   - **Hostname:** `hub`. You can then reach the Pi as `hub.local` from many devices.
   - **Username and password.** Write them down.
   - **Wi-Fi** name and password, unless you use a network cable.
   - **Time zone** and keyboard layout.
   - **Enable SSH**, so you can type commands from your regular computer.
5. Write the card. Put it in the Pi and switch it on. The first start takes a few minutes.

## Step 2: Open a terminal on the Pi

Pick one:

- **On the Pi itself,** with a keyboard and screen: open the **Terminal** app.
- **From your regular computer:** open a terminal (on Windows, PowerShell) and type the line below, using the username you chose. Type `yes` if it asks about a fingerprint, then your password.

  ```bash
  ssh <username>@hub.local
  ```

Bring the Pi up to date, then restart it:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

Wait a minute and open the terminal again.

## Step 3: Install Docker

Docker runs Sproutwall in its own container. Use Docker's official instructions. The 64-bit Raspberry Pi OS is based on Debian, so Docker's [Raspberry Pi OS page](https://docs.docker.com/engine/install/raspberry-pi-os/) sends 64-bit users to the Debian steps.

1. Follow **Install using the `apt` repository** on Docker's [Debian install page](https://docs.docker.com/engine/install/debian/). Docker also offers a convenience script on that page, but Docker itself recommends it only for testing.
2. Let your user run Docker without `sudo`, as described in Docker's [post-install steps](https://docs.docker.com/engine/install/linux-postinstall/):

   ```bash
   sudo usermod -aG docker $USER
   ```

   Then log out and back in (or `sudo reboot`) so the change takes effect.
3. Check that it works:

   ```bash
   docker compose version
   ```

## Step 4: Download and start Sproutwall

```bash
sudo apt install -y git
git clone https://github.com/thebrianlee/sproutwall.git sproutwall
cd sproutwall
docker compose up -d --build
```

**The first build on a Pi can take a long time.** It compiles the whole app on the Pi. Leave it running and do not unplug the Pi. If it stops with `Killed`, `exit code: 137` or "out of memory", see [The build runs out of memory](#the-build-runs-out-of-memory).

When the build is done, check it:

```bash
docker compose ps
```

After a short wait the status says `healthy`. To watch the hub's messages, run `docker compose logs -f`. Press Ctrl+C to stop watching. The hub keeps running.

## Step 5: Find the hub's address

On the Pi, run:

```bash
ip -o -4 addr show scope global
```

The Pi's address is the one on the line for your Wi-Fi or network cable (often `wlan0` or `eth0`), for example `192.168.1.50` from `inet 192.168.1.50/24`. Never use an address on a `docker0`, `br-` or `veth` line (Docker's own network, for example `172.17.0.1`), or one that starts with `169.254.`: no phone can reach it. On a phone or tablet on the same Wi-Fi, open `http://192.168.1.50:3847` (with your number). Many devices can also open `http://hub.local:3847`, but not all.

Ask your router to always give the Pi this address (often called a "DHCP reservation"), so bookmarks keep working.

Now do the first-run setup: choose the parent PIN, your family and your timezone. The [README](../README.md#first-run-setup) explains each field. Do it right away: until setup is done, anyone on your network could choose the PIN.

## Step 6: Show the hub full screen on the Pi's own screen (optional)

This needs the desktop version of Raspberry Pi OS (64-bit) and a screen with touch. The Pi then opens the hub from itself at `http://127.0.0.1:3847`, full screen, and comes back by itself after a power cut.

### Set it up with the kiosk tool

1. With the Pi switched off, connect the screen and its touch connection, following the screen's own instructions. Many HDMI touch screens need a separate USB cable for touch. Connect only this one screen.
2. Switch the Pi on and log in to the desktop.
3. Open the **Terminal** on the Pi's desktop, go to the hub's folder and run:

   ```bash
   cd ~/sproutwall
   ./scripts/sproutwall setup kiosk
   ```

   The screen turns to portrait, the usual way to hang a kitchen screen. For another way, add one of `--orientation portrait-flipped`, `--orientation landscape` or `--orientation landscape-flipped`. Running it again with another orientation changes only that.
4. **Tap the four corners and the centre of the screen.** Each tap must land under your finger. If it does not, run `./scripts/sproutwall setup kiosk --undo` and set the screen up by hand (below).
5. If the tool prints an autologin command, run it yourself. It needs your password, so the tool never runs it:

   ```bash
   sudo raspi-config nonint do_boot_behaviour B4
   ```

6. Restart with `sudo reboot`. The hub opens full screen once it is ready and asks once for the parent PIN to unlock the screen. The unlock lasts 30 days. If the hub takes more than a minute and a half to start, the screen says it is starting and opens the hub by itself when it is ready.
7. Check it: `./scripts/sproutwall setup kiosk --check` should end with `Result: ok`.

The tool also turns off the desktop's screen blanking, so the screen stays lit. Sproutwall has its own screensaver instead: after 10 idle minutes it shows your photos and quotes.

- **Turn the kiosk off** (it closes the kiosk browser now and no longer starts it at login; the hub keeps running and phones still reach it): `./scripts/sproutwall setup kiosk --off`. Turn it back on with `./scripts/sproutwall setup kiosk`.
- **Remove it** and put every setting back as it was before: `./scripts/sproutwall setup kiosk --undo`.
- To leave the kiosk for a moment, press Alt+F4 with a keyboard attached. It opens again at the next login.

The tool supports exactly one setup: Raspberry Pi OS 64-bit with the desktop, its standard Wayland desktop (labwc), exactly one screen on HDMI or DSI, one touch input, and Chromium. On anything else it stops, changes nothing and says why; then set the screen up by hand. [docs/install-cli.md](install-cli.md#setup-kiosk-the-pis-own-touch-screen) lists every check, every file it writes and how each is undone.

### Set it up by hand

Use this when the tool stops, for a screen without touch, or on an older image.

1. **Screen blanking off:** run `sudo raspi-config`, choose **Display Options**, then **Screen Blanking**, and answer **No**.
2. **Desktop autologin:** in `sudo raspi-config`, under **System Options**, find the boot or auto-login option (the wording differs between releases) and choose **Desktop Autologin**.
3. **Rotation and touch:** open **Control Centre**, then **Screens**. Set the screen's orientation and, if it offers one, the touchscreen it belongs to (the menu wording differs between releases). Apply and confirm.
4. **Start Chromium at login.** Find the browser's name with `command -v chromium chromium-browser`. On current releases (labwc), add this line to `~/.config/labwc/autostart` (create the file if needed, for example with `nano ~/.config/labwc/autostart`), using the name it printed:

   ```bash
   chromium http://127.0.0.1:3847 --kiosk --noerrdialogs --disable-infobars --no-first-run &
   ```

   On older Bookworm images that use wayfire (`ps -e | grep -E 'labwc|wayfire'` shows which), add to `~/.config/wayfire.ini` instead:

   ```ini
   [autostart]
   sproutwall = chromium-browser http://127.0.0.1:3847 --kiosk --noerrdialogs --disable-infobars --no-first-run
   ```

5. Reboot.

Do **not** add `--incognito`. Incognito forgets the unlock every time Chromium restarts, so the screen would ask for the PIN again and again. This follows the official Raspberry Pi [kiosk tutorial](https://www.raspberrypi.com/tutorials/how-to-use-a-raspberry-pi-in-kiosk-mode/).

**A hand-made line and the tool.** If you added a Chromium line by hand and then run the tool, it stops so that the screen never opens two browsers. Delete your line from `~/.config/labwc/autostart` first.

### Remove the kiosk by hand

`--undo` refuses when a file it manages was changed after setup (for example by Control Centre), so that your change is not overwritten. To remove the kiosk by hand instead:

1. `./scripts/sproutwall setup kiosk --off` (it stops the browser even then).
2. In `~/.config/labwc/autostart`, delete the line that ends with `# sproutwall:kiosk-launcher`. Add the screen blanking back in Control Centre if you want it.
3. In `~/.config/labwc/rc.xml`, delete the line `<!-- sproutwall:kiosk-touch -->` and the `<touch … />` line below it.
4. In `~/.config/kanshi/config`, delete everything from `# sproutwall:kiosk-output begin` to `# sproutwall:kiosk-output end`.
5. Delete `~/.local/bin/sproutwall-kiosk` and the folder `~/.local/state/sproutwall/kiosk`. That folder also holds copies of the files as they were before setup, in `original/`, if you want to compare first.

### Kiosk on other devices

The hub runs on any 64-bit Linux computer, but the kiosk tool only sets up Raspberry Pi OS. On another device, such as a mini PC, another Linux desktop or a tablet, open the hub in a browser's kiosk mode:

- On the computer that runs the hub, the address is `http://127.0.0.1:3847`. On another device on the home network, it is `http://<hub address>:3847` (see [Step 5](#step-5-find-the-hubs-address)).
- Chromium: `chromium --kiosk --no-first-run http://127.0.0.1:3847`. Firefox: `firefox --kiosk http://127.0.0.1:3847`. Add it to the desktop's own startup programs.
- Use a normal (persistent) profile, never a private or incognito window, so the screen's unlock lasts.
- Turn off the device's own screen blanking and set rotation and touch in its own display settings.

## Keep it running

These run in the hub's folder: `cd ~/sproutwall`, or `cd ~/family-hub` if you installed before the rename to Sproutwall. The [README](../README.md#back-up-and-update) explains each one.

**Back up** the household and photos to one file:

```bash
docker compose stop
docker compose run --rm -T --entrypoint tar family-hub czf - -C / data photos > sproutwall-backup.tgz
docker compose start
```

Copy `sproutwall-backup.tgz` off the Pi, for example to a USB stick. SD cards fail sometimes.

**Update** (back up first):

```bash
git pull && docker compose up -d --build --remove-orphans
```

Updates rebuild the app on the Pi, so they also take a while.

**Forgot the PIN:**

```bash
docker compose exec family-hub node scripts/reset-pin.mjs 4827
```

Use your own new PIN instead of `4827`. Every screen then asks for the new PIN.

## Troubleshooting

### A phone or tablet can't reach the hub

- Is the phone on the same Wi-Fi as the Pi? Guest networks often keep devices apart. So can a VPN app on the phone.
- Did you type `http://` (not `https://`) and `:3847` at the end?
- Did the Pi's address change? Run `ip -o -4 addr show scope global` again and use the Wi-Fi or cable line ([step 5](#step-5-find-the-hubs-address)), and set a DHCP reservation in your router.
- Is the hub running? `docker compose ps` should say `healthy`. If not, `docker compose logs` shows why.
- Does the Pi's own screen work with `http://localhost:3847`? If yes, the hub is fine and the problem is the network between the phone and the Pi.

### The screen goes black

- Turn off screen blanking: `./scripts/sproutwall setup kiosk` does it, or see [Set it up by hand](#set-it-up-by-hand).
- Some monitors and TVs have their own power-saving setting. Check the monitor's menu.
- Sproutwall's own screensaver shows photos and quotes, not a black screen. Tap the screen to go back to the hub.

### The build runs out of memory

Building the app needs a lot of memory. On a 4 GB Pi the build may fail. Adding swap space (disk space used as extra memory) usually helps.

On Bookworm, swap is set in `/etc/dphys-swapfile`:

```bash
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
```

Change the line to `CONF_SWAPSIZE=2048`, save (Ctrl+O, Enter) and exit (Ctrl+X). Then:

```bash
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

Run `docker compose up -d --build` again. If `/etc/dphys-swapfile` does not exist, your release manages swap differently. Check the [Raspberry Pi documentation](https://www.raspberrypi.com/documentation/) for your release.

Swap on an SD card is slow and wears the card. An SSD is better if you build often.

### Ask the Hub is slow or does not answer

Running a local language model (Ollama) on the Pi itself is likely to be too slow. The hub gives up on an answer after 40 seconds. Use one of these instead:

- An Anthropic API key (`ANTHROPIC_API_KEY`), or
- Ollama on a faster computer in your home, with `OLLAMA_URL` set to that computer, for example `http://192.168.1.60:11434`. That Ollama must accept connections from the network.

The README explains [how to turn it on](../README.md#ask-the-hub) and what is sent to the model.

### The screen keeps asking for the PIN

- Chromium must not run in incognito mode (see [Set it up by hand](#set-it-up-by-hand)). The kiosk tool never uses it.
- Changing or resetting the PIN locks every screen once. Enter the new PIN.
- The unlock lasts 30 days. After that the screen asks again.

### The time or date is wrong

The hub uses the timezone chosen at setup, not the Pi's own setting. Open [Settings](../README.md#parent-settings), check **Timezone** under **Household** (for example `America/Chicago`), or tap **Use this device's timezone**, then save.
