# Twingate Tray v0.3 (Linux Mint)

A lightweight **system tray application** for Linux (Mint)  
that provides **GUI control over Twingate CLI** and **resource authentication**
without relying on the terminal.

This project is based strictly on the **real behavior of Twingate CLI on Linux**  
— no assumptions, no workarounds.

---

## ✨ Features

- ✅ System tray integration (AppIndicator)
- ✅ Live Twingate connection status (`online / not-running`)
- ✅ Connect / Disconnect via `pkexec`
- ✅ Detects transition `offline → online`
- ✅ Fetches resource list automatically on first `online`
- ✅ Dynamic menu entries:
  ```
  Auth <RESOURCE_NAME>
  ```
- ✅ Clicking a resource runs:
  ```bash
  twingate auth <resource-name>
  ```
- ✅ Live status window:
  - current connection state
  - full `twingate status` output
  - resource table including **AUTH STATUS**
- ✅ No caching, no guessing — CLI is the single source of truth

---

## 🖥 Requirements

### Operating System
- tested only on Linux Mint 22.3
- Desktop Environment with **AppIndicator support**
  (Cinnamon, MATE, XFCE)

### Packages
```bash
sudo apt install python3 python3-gi gir1.2-appindicator3-0.1 policykit-1
```

### Twingate
- Official **Twingate CLI** installed
- Working commands:
  ```bash
  twingate status
  twingate connect
  twingate resources
  twingate auth <resource>
  ```

---

## 🚀 Running the application

```bash
chmod +x twingate-tray.py
python3 ./twingate-tray.py
```

> ⚠️ Note  
> If you want to run it as `./twingate-tray.py`, make sure:
> - there is **no BOM**
> - the first line is exactly:
> ```python
> #!/usr/bin/env python3
> ```

---

## 🔐 Privilege model (important)

- **Connect / Disconnect**
  - executed as **root** using `pkexec`
- **Auth <resource>**
  - executed as **regular user**
- The application **does not store credentials or tokens**
- All authentication is handled entirely by **Twingate**

---

## 📋 Application logic

1. Periodically checks:
   ```bash
   twingate status
   ```
2. When transition is detected:
   ```
   not-running → online
   ```
3. Fetches resources **once**:
   ```bash
   twingate resources
   ```
4. Parses **RESOURCE NAME** column
5. Builds menu entries:
   ```
   Auth Router01
   Auth Ubuntu01
   Auth nas
   ```
6. Clicking a resource executes:
   ```bash
   twingate auth <resource-name>
   ```

---

## 🪟 Status window

Available from menu: **Show status**

Displays:
- current Twingate state
- raw `twingate status` output
- resource table:
  - NAME
  - ADDRESS
  - ALIAS
  - AUTH STATUS

The window **auto-refreshes** while open.

---
## 🔐 Resource authentication (AUTH handling)

When a resource requires additional authentication, the command:

```bash
twingate auth <resource>
```

may return an **HTTPS authentication URL**.

The tray application can handle this URL in three different ways,
controlled by a constant in the source code:

```python
AUTH_MODE = 0 | 1 | 2
```

### AUTH_MODE options

| Mode | Behavior |
|------|----------|
| `0` | Only executes `twingate auth` (no URL handling) |
| `1` | Automatically opens the authentication URL in the default web browser |
| `2` (default) | Displays a GTK window with the authentication URL |

The URL is extracted directly from **stdout / stderr** of the running
`twingate auth` process.

Only the **first detected HTTPS URL** is handled.

---

## 🪟 Authentication URL window

When `AUTH_MODE = 2`, a dedicated GTK window is displayed if authentication
requires user interaction.

The window contains:

- Title: `Twingate Auth – <RESOURCE_NAME>`
- Read-only text field with the authentication URL
- Buttons:
  - **Copy URL** – copies the URL to the system clipboard
  - **Open URL** – opens the URL in the default web browser

The window is shown once per authentication request.

---

## 🧩 Tray icon & tooltip

- Icons come from the system icon theme (freedesktop spec)
- Tooltip text is set dynamically, e.g.:
  ```
  Twingate Tray v0.3 — ONLINE
  ```
- Application title can be set via:
  ```python
  indicator.set_title("Twingate Tray v0.3")
  ```

---

## 🔁 Autostart on login (Linux Mint / Ubuntu)

To start **Twingate Tray** automatically after user login, use a standard
`.desktop` autostart entry.

### 1️⃣ Create autostart directory

```bash
mkdir -p ~/.config/autostart
```

### 2️⃣ Create autostart entry

Create the file:

```bash
nano ~/.config/autostart/twingate-tray.desktop
```

Paste the following content **and adjust paths if needed**:

```ini
[Desktop Entry]
Type=Application
Name=Twingate Tray
Comment=Twingate system tray controller
Exec=python3 /home/YOUR_USER/apps/twingate-tray/twingate-tray.py
Icon=network-vpn
Terminal=false
X-GNOME-Autostart-enabled=true
```

⚠️ Replace `/home/YOUR_USER/apps/twingate-tray/twingate-tray.py`
with the actual path to your script.

### 3️⃣ Make sure the script is executable

```bash
chmod +x /home/YOUR_USER/apps/twingate-tray/twingate-tray.py
```

### 4️⃣ Log out and log in again

After logging in:
- the tray icon should appear automatically
- Twingate status will be monitored immediately

Autostart does **not** automatically connect Twingate.
Connection remains user-controlled by design.

---


## 📌 Why AppIndicator

- Stable on Mint / Ubuntu
- Supported by Cinnamon / MATE / XFCE
- Avoids deprecated APIs (`Gtk.StatusIcon`)

---


## 📄 License

MIT License

Use, modify, and distribute at your own risk.

---

## 👤 Author

Created as a **practical administrative tool**
for Linux users of Twingate.

Pull requests and suggestions are welcome.
