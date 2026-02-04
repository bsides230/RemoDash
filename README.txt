# RemoDash
A Visual Control Plane for Headless Machines

---

## What Is RemoDash?

RemoDash turns a headless machine into a server that **serves its GUI**.

Instead of installing a heavy desktop environment, forwarding pixels, or memorizing terminal commands, RemoDash exposes system capabilities through a **browser-based dashboard**:

- files
- processes
- terminals
- scripts
- system info
- one-click actions

If a machine can run a lightweight server and you have a browser, RemoDash can control it.

RemoDash works everywhere — but it reaches its full potential on **headless Linux systems**.

---

## What Problem Does This Solve?

Most headless systems are controlled by:
- SSH
- terminal commands
- text editors
- scripts you have to remember how to run

That works — but it is slow, error-prone, and painful on mobile devices.

RemoDash replaces that workflow with:
- visual file browsing
- clickable actions
- persistent shortcuts
- terminal tabs
- a consistent UI across all machines

You stop thinking about *which machine you’re on* and start thinking about *what you want to do*.

---

## Core Design Principles

- Headless-first (no desktop environment required)
- Browser-native (works on phones, tablets, laptops, TVs)
- Low bandwidth (no pixel streaming, no VNC/RDP)
- Capability-based UI (control the system, not its screen)
- Explicit power (dangerous features are opt-in and clearly warned)
- No memorization required (buttons instead of commands)

---

## Secure Remote Access (Tailscale Recommended)

RemoDash is designed to run on **private networks**.

While it can be exposed in other ways, the **recommended setup is Tailscale**.

Why Tailscale:
- Encrypted peer-to-peer networking
- No port forwarding
- No firewall gymnastics
- Works across NATs, mobile networks, and cloud machines
- Ideal for headless systems

With Tailscale:
- Each RemoDash instance gets a stable private IP
- The dashboard is only accessible to devices on your tailnet
- RemoDash never needs to be publicly exposed

RemoDash is a **private control plane**, not a public service.

---

## Admin Token (Optional, Wizard-Configured)

RemoDash does **not** force an authentication model.

During installation, the wizard allows you to choose how access is handled:

- **Admin Token Enabled**
  - All API access requires the admin token
  - Intended for remote access, shared networks, or Tailscale setups

- **Admin Token Disabled**
  - No token required
  - Intended for:
    - local-only installs
    - trusted private networks
    - kiosk or single-user environments

This choice is explicit and intentional.

---

## Admin Token Handling (When Enabled)

When enabled:
- The token is generated during installation
- The token is never printed to the terminal
- The token is never displayed in the dashboard UI
- The wizard provides a **downloadable .txt file** containing the token

This avoids leaking credentials via:
- terminal history
- screenshots
- copy/paste mistakes

The token can be regenerated, rotated, or disabled by re-running the wizard.

---

## Installation Wizards

RemoDash includes comprehensive interactive install wizards.

### PC Wizard (Windows / Desktop Systems)

- Designed for desktops and laptops
- Prompts for:
  - admin token option
  - filesystem access mode
  - startup behavior
- Windows support is useful but not the primary target

### Linux Wizard (Servers & Headless Systems)

This is where RemoDash shines.

Designed for:
- servers
- headless systems
- Raspberry Pi / SBCs
- NAS devices
- homelabs
- Android / TV boxes

The wizard configures:
- admin token
- filesystem access mode
- additional allowed filesystem roots
- network binding
- startup service installation

---

## Startup Service (Persistent on Reboot)

RemoDash can be installed as a **startup service**.

When enabled:
- RemoDash starts automatically on boot
- No user login is required
- The dashboard is always available

This is ideal for:
- servers
- headless Linux systems
- edge devices
- kiosks
- Android boxes

---

## Dashboard Overview

The dashboard is fully responsive and automatically resizes to work on:
- desktops
- tablets
- phones

No special client is required — only a browser.

---

## Terminal Module

- Multiple terminal tabs
- Each command or shortcut opens a new tab
- Tabs can be popped out into separate windows
- Popped-out tabs are visually removed or marked in the main panel
- Designed to work well on mobile devices

This is a real system shell exposed through the browser.

---

## File Explorer

- Visual filesystem browsing
- Create, rename, delete files and folders
- Edit text files
- View images
- Create shortcuts directly from selected files

No SCP. No memorized paths.

---

## Shortcuts Module (User-Defined App Launchers)

Shortcuts are **one-click actions** you define.

They can run:
- Python scripts
- JavaScript files
- Bash / shell scripts
- Batch files
- PowerShell scripts
- Executables

Each shortcut supports:
- arguments
- working directory
- confirmation prompts
- output capture
- run in Terminal
- run as admin (explicit)

---

## Run in Terminal

Any shortcut can be configured to run:
- normally with captured output, or
- inside the Terminal module in a new terminal tab

Perfect for interactive or long-running commands.

---

## Run as Admin (Explicit Elevation)

Admin execution is explicit and honest:

- Windows uses standard UAC prompts
- Linux/macOS uses sudo
- Rooted Android uses su

Admin runs:
- are clearly labeled
- default to Terminal mode
- never bypass filesystem restrictions

---

## Filesystem Access Modes

### Open Mode (Default)
- Full filesystem access
- Intended for trusted environments

### Jailed Mode (Optional)
- Restricted root directory
- Optional additional allowed roots (external drives, mounts, partitions)
- Enforced server-side

Nothing is restricted silently.

---

## Persistent Dashboard State

RemoDash remembers:
- shortcuts
- layout
- UI state

You can hop between machines without losing your workflow.

---

## Power Clipboard (Dashboard Clipboard)

- Copy inside RemoDash
- Paste anywhere inside RemoDash
- Persists across reloads and devices

This clipboard belongs to the dashboard, not the OS.

---

## Mobile-First by Design

RemoDash works naturally on:
- phones
- tablets
- touchscreens

No pixel streaming. No fragile layouts.

---

## What RemoDash Is Not

- Not a remote desktop
- Not VNC/RDP
- Not a SaaS platform
- Not a sandbox
- Not a terminal pretending to be a GUI

It is a **visual control surface for machines**.

---

## Final Note

RemoDash exists because:
- headless machines do not need heavy GUIs
- control should be visual, not memorized
- a browser is the best thin client ever invented

Install it once.
Access it from anywhere.
Stop worrying about which machine you are on.
