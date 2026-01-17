#!/usr/bin/env python3
import gi
import subprocess
import shutil
import sys


gi.require_version("Gtk", "3.0")
gi.require_version("AppIndicator3", "0.1")

from gi.repository import Gtk, AppIndicator3, GLib

APP_ID = "twingate-tray"
app_ver = "0.2"
app_name = f"Twingate Tray v{app_ver}"

last_status = None
status_window = None
resource_menu_items = []


# ==================================================
# CLI helpers
# ==================================================

def check_twingate_available_or_exit():
    if shutil.which("twingate") is None:
        print("ERROR: twingate binary not found in PATH", file=sys.stderr)
        sys.exit(1)


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
    subprocess.Popen(["twingate", "auth", resource_name])


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
