#!/usr/bin/env python3
import gi
import subprocess
import shutil
import sys
import re
import webbrowser


gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("AppIndicator3", "0.1")

from gi.repository import Gdk, Gtk, AppIndicator3, GLib

# AUTH handling mode:
# 0 = do nothing (just trigger twingate auth)
# 1 = open auth URL in default browser automatically
# 2 = show GUI window with clickable + copyable auth URL
AUTH_MODE = 2
DEBUG_LOG = False

APP_ID = "twingate-tray"
app_ver = "0.3"
app_name = f"Twingate Tray v{app_ver}"

last_status = None
status_window = None
resource_menu_items = []


def debug_log(msg):
    if DEBUG_LOG:
        print(msg)

def extract_auth_url(text):
    """
    Extract HTTPS URL from a line of text.
    """
    match = re.search(r"https://\S+", text)
    if match:
        url = match.group(0)
        debug_log(f"[AUTH:URL:FOUND] {url}")
        return url

    debug_log("[AUTH:URL:NOT_FOUND] no URL in line")

    return None


# ==================================================
# CLI helpers
# ==================================================


def check_twingate_available_or_exit():
    if shutil.which("twingate") is None:
        print("ERROR: twingate binary not found in PATH", file=sys.stderr)
        sys.exit(1)

def show_auth_url_window(resource_name, url):
    """
    Show GTK window with authentication URL.
    Provides buttons to copy or open the URL.
    """

    win = Gtk.Window(title=f"Twingate Auth – {resource_name}")
    win.set_default_size(700, 180)
    win.set_border_width(10)

    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

    label = Gtk.Label(label="Additional authentication is required.")
    label.set_xalign(0)

    entry = Gtk.Entry()
    entry.set_text(url)
    entry.set_editable(False)
    entry.set_can_focus(True)

    # Buttons container
    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

    btn_copy = Gtk.Button(label="Copy URL")
    btn_copy.connect(
        "clicked",
        lambda _: Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(url, -1)
    )

    btn_open = Gtk.Button(label="Open URL")
    btn_open.connect(
        "clicked",
        lambda _: webbrowser.open(url)
    )

    hbox.pack_start(btn_copy, False, False, 0)
    hbox.pack_start(btn_open, False, False, 0)

    vbox.pack_start(label, False, False, 0)
    vbox.pack_start(entry, False, False, 0)
    vbox.pack_start(hbox, False, False, 0)

    win.add(vbox)
    win.show_all()

def run_cmd(cmd):
    try:
        out = subprocess.check_output(
            cmd,
            stderr=subprocess.STDOUT,
            text=True
        )
        return out.strip()
    except subprocess.CalledProcessError as e:
        return e.output.strip()
    except Exception as e:
        return str(e)


def twingate_status():
    out = run_cmd(["twingate", "status"]).lower()
    if "online" in out:
        return "online"
    if "not-running" in out:
        return "offline"
    return "unknown"
def twingate_resources_full():
    raw = run_cmd(["twingate", "resources"])
    lines = raw.splitlines()

    if len(lines) < 2:
        return []

    resources = []

    for line in lines[1:]:  # skip header
        if not line.strip():
            continue

        # split after whitespace
        parts = line.split()

        name = parts[0]
        address = parts[1] if len(parts) > 1 else "-"
        alias = parts[2] if len(parts) > 2 else "-"
        auth = parts[3] if len(parts) > 3 else "NOT AUTHORIZED"

        resources.append({
            "name": name,
            "address": address,
            "alias": alias,
            "auth": auth
        })

    return resources



def twingate_resources():
    raw = run_cmd(["twingate", "resources"])
    resources = []

    lines = raw.splitlines()

    # skip header
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue

        # first column = RESOURCE NAME
        resource_name = line.split()[0]
        resources.append(resource_name)

    return resources



# ==================================================
# Actions
# ==================================================

def connect_root(_=None):
    subprocess.Popen(["pkexec", "twingate", "connect"])


def disconnect_root(_=None):
    subprocess.Popen(["pkexec", "twingate", "disconnect"])



def auth_resource(resource_name):
    """
    Trigger Twingate auth and handle authentication URL using GLib I/O watches.
    No threading, GTK-native implementation.
    """

    try:
        proc = subprocess.Popen(
            ["twingate", "auth", resource_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        url_handled = {"done": False}

        def on_io_ready(stream, _condition):
            line = stream.readline()
            if not line:
                return False

            debug_log(f"[AUTH] {line.strip()}")

            if url_handled["done"]:
                return True

            url = extract_auth_url(line)
            if not url:
                return True

            url_handled["done"] = True
            debug_log("[AUTH] URL extracted and handled once")

            if AUTH_MODE == 1:
                debug_log("[AUTH] Opening URL in default browser")
                webbrowser.open(url)

            elif AUTH_MODE == 2:
                debug_log("[AUTH] Showing GTK auth window")
                show_auth_url_window(resource_name, url)

            return False  # stop watching after URL is handled

        GLib.io_add_watch(proc.stdout, GLib.IO_IN, on_io_ready)
        GLib.io_add_watch(proc.stderr, GLib.IO_IN, on_io_ready)

    except Exception as e:
        debug_log(f"[AUTH:ERROR] {e}")


# ==================================================
# GUI helpers
# ==================================================

def show_status_window(_=None):
    global status_window
    if status_window is None:
        status_window = StatusWindow()
    else:
        status_window.present()

def rebuild_resource_menu(menu, resources):
    global resource_menu_items

    for item in resource_menu_items:
        menu.remove(item)
    resource_menu_items.clear()

    if not resources:
        return

    separator = Gtk.SeparatorMenuItem()
    separator.show()
    menu.append(separator)
    resource_menu_items.append(separator)

    for res in resources:
        item = Gtk.MenuItem(label=f"Auth {res}")
        item.connect("activate", lambda _, r=res: auth_resource(r))
        item.show()
        menu.append(item)
        resource_menu_items.append(item)


def refresh(indicator, menu):
    global last_status

    status = twingate_status()

    if status == "online":
        indicator.set_icon_full("network-vpn", "Twingate: ONLINE")
        indicator.set_title(f"{app_name} : Online")
    elif status == "offline":
        indicator.set_icon_full("network-vpn-disconnected", "Twingate: OFFLINE")
        indicator.set_title(f"{app_name} : Offline")
    else:
        indicator.set_icon_full("dialog-question", "Twingate: UNKNOWN")
        indicator.set_title(f"{app_name} : UNKNOWN")

    # go to ONLINE
    if last_status != "online" and status == "online":
        resources = twingate_resources()
        rebuild_resource_menu(menu, resources)

    # go to OFFLINE
    if last_status == "online" and status != "online":
        rebuild_resource_menu(menu, [])

    last_status = status
    return True


# ==================================================
# Main
# ==================================================

def main():
    check_twingate_available_or_exit()

    indicator = AppIndicator3.Indicator.new(
        APP_ID,
        "network-vpn-disconnected",
        AppIndicator3.IndicatorCategory.SYSTEM_SERVICES
    )

    indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

    menu = Gtk.Menu()

    item_status = Gtk.MenuItem(label="Show status")
    item_status.connect("activate", show_status_window)

    item_connect = Gtk.MenuItem(label="Connect")
    item_connect.connect("activate", connect_root)

    item_disconnect = Gtk.MenuItem(label="Disconnect")
    item_disconnect.connect("activate", disconnect_root)

    item_quit = Gtk.MenuItem(label="Quit")
    item_quit.connect("activate", Gtk.main_quit)

    for item in [
        item_status,
        Gtk.SeparatorMenuItem(),
        item_connect,
        item_disconnect,
        Gtk.SeparatorMenuItem(),
        item_quit
    ]:
        item.show()
        menu.append(item)
    indicator.set_menu(menu)

    GLib.timeout_add_seconds(5, refresh, indicator, menu)
    refresh(indicator, menu)

    Gtk.main()
class StatusWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Twingate Status")
        self.set_default_size(600, 400)

        self.textview = Gtk.TextView()
        self.textview.set_editable(False)
        self.textview.set_monospace(True)

        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self.textview)
        self.add(scrolled)

        self.update_content()

        # refresh every 5 seconds
        self.timer_id = GLib.timeout_add_seconds(5, self.update_content)

        self.connect("destroy", self.on_destroy)

        self.show_all()

    def on_destroy(self, *_):
        global status_window
        if self.timer_id:
            GLib.source_remove(self.timer_id)
            self.timer_id = None
        status_window = None

    def update_content(self):
        status = twingate_status()
        status_raw = run_cmd(["twingate", "status"])

        lines = []
        lines.append(f"Twingate status: {status.upper()}")
        lines.append("")
        lines.append(status_raw)
        lines.append("")

        if status == "online":
            resources = twingate_resources_full()

            lines.append("Resources:")
            lines.append("-" * 60)
            lines.append(f"{'NAME':15} {'ADDRESS':15} {'ALIAS':15} {'AUTH'}")
            lines.append("-" * 60)

            for r in resources:
                lines.append(
                    f"{r['name']:15} {r['address']:15} {r['alias']:15} {r['auth']}"
                )
        else:
            lines.append("Resources unavailable (Twingate offline).")

        text = "\n".join(lines)
        self.textview.get_buffer().set_text(text)

        return True


if __name__ == "__main__":
    main()
