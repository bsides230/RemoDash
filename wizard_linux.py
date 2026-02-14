import os
import sys
import subprocess
import platform
import json
import time
import shutil
import re
import getpass
from pathlib import Path

# --- Global State ---
venv_python = sys.executable

def print_header(title):
    print("\n" + "=" * 60)
    print(f"       {title}")
    print("=" * 60 + "\n")

def save_wizard_state(key, value):
    """Saves a key-value pair to settings.json under 'wizard_state'."""
    settings_path = Path("settings.json")
    data = {"settings": {}, "ui_settings": {}, "wizard_state": {}}

    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
        except: pass

    if "wizard_state" not in data:
        data["wizard_state"] = {}

    data["wizard_state"][key] = value

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_wizard_state(key, default=None):
    """Loads a value from settings.json 'wizard_state'."""
    settings_path = Path("settings.json")
    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("wizard_state", {}).get(key, default)
        except: pass
    return default

def install_dependencies():
    print_header("Dependencies")

    # Check if we are already in a venv
    in_venv = (sys.prefix != sys.base_prefix)
    global venv_python

    use_venv = False
    break_system = False

    if not in_venv:
        print("You are not running in a virtual environment.")
        v_choice = input("Would you like to create/use a local virtual environment (venv)? (Y/n): ").strip().lower()
        if v_choice in ['y', 'yes', '']:
            use_venv = True
        else:
            # If they decline venv, ask about break-system-packages (mostly for Linux/PEP 668)
            bs_choice = input("Install globally? This may require '--break-system-packages' on some systems. Proceed? (Y/n): ").strip().lower()
            if bs_choice in ['y', 'yes', '']:
                break_system = True
            else:
                print("Aborting dependency installation.")
                return False

    choice = input("Install/Update Dependencies now? (Y/n): ").strip().lower()
    if choice in ['y', 'yes', '']:
        print("\nInstalling dependencies...")

        # Check for offline packages
        offline_dir = Path("offline_packages")
        use_offline = False
        if offline_dir.exists() and offline_dir.is_dir():
            print(f"\n[!] Offline packages detected in '{offline_dir}'.")
            off_choice = input("Install from local offline packages? (Y/n): ").strip().lower()
            if off_choice in ['y', 'yes', '']:
                use_offline = True

        pip_cmd = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]

        if use_venv:
            # Create venv if not exists
            venv_path = Path("venv")
            if not venv_path.exists():
                print("Creating virtual environment...")
                try:
                    subprocess.check_call([sys.executable, "-m", "venv", "venv"])
                except subprocess.CalledProcessError:
                    print("Failed to create venv.")
                    return False

            # Adjust pip command to use venv
            if platform.system() == "Windows":
                pip_exe = venv_path / "Scripts" / "pip.exe"
                python_exe = venv_path / "Scripts" / "python.exe"
            else:
                pip_exe = venv_path / "bin" / "pip"
                python_exe = venv_path / "bin" / "python"

            if pip_exe.exists():
                pip_cmd = [str(pip_exe), "install", "-r", "requirements.txt"]
                # Update sys.executable for the rest of the script/launch
                venv_python = str(python_exe)
            else:
                print("Error: venv created but pip not found.")
                return False

        elif break_system:
            pip_cmd.append("--break-system-packages")

        if use_offline:
            pip_cmd.extend(["--no-index", f"--find-links={offline_dir}"])

        try:
            subprocess.check_call(pip_cmd)
            print("Dependencies installed successfully.")
        except subprocess.CalledProcessError:
            print("Error installing dependencies.")
            return False
    else:
        print("Skipping dependencies.")

    input("\nPress Enter to return to menu...")
    return True

def configure_general():
    print_header("General Settings")

    # Device Name
    settings_path = Path("settings.json")
    data = {"settings": {}, "ui_settings": {}}

    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
        except: pass

    if "settings" not in data: data["settings"] = {}

    current_name = data["settings"].get("device_name", "")
    print(f"Current Device Name: {current_name if current_name else '(Not Set)'}")

    new_name = input("Enter Device Name (leave empty to keep/skip): ").strip()
    if new_name:
        data["settings"]["device_name"] = new_name
        print(f"Device Name set to: {new_name}")

    # VLC Path
    current_vlc = data["settings"].get("vlc_path", "")
    print(f"\nCurrent VLC Path: {current_vlc if current_vlc else '(Auto/Default)'}")
    print("Required if VLC is not in your system PATH or you want to use a specific version.")

    new_vlc = input("Enter path to VLC executable (leave empty to keep/skip): ").strip()
    if new_vlc:
        data["settings"]["vlc_path"] = new_vlc
        print(f"VLC Path set to: {new_vlc}")

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    input("\nPress Enter to return to menu...")

def configure_filesystem_mode():
    print_header("Filesystem Access Mode")
    print("[1] FULL SYSTEM ACCESS (DEFAULT)")
    print("    RemoDash can read, write, delete, and execute files")
    print("    anywhere on this machine.")
    print("\n[2] JAILED FILESYSTEM (RESTRICTIVE MODE)")
    print("    RemoDash is locked to one directory and cannot")
    print("    access anything outside it.")
    print("    This may break some modules and workflows.")

    choice = input("\nChoose [1/2]: ").strip()

    mode = "open"
    root = ""
    extra_roots = []

    if choice == "2":
        mode = "jailed"
        while True:
            r = input("\nEnter Jail Root Directory: ").strip()
            if not r:
                print("Root directory is required for Jailed mode.")
                continue

            p = Path(r)
            try:
                if not p.exists():
                    create = input(f"Directory '{r}' does not exist. Create it? (Y/n): ").strip().lower()
                    if create in ['y', 'yes', '']:
                        p.mkdir(parents=True, exist_ok=True)
                    else:
                        print("Please enter a valid directory.")
                        continue
                if not p.is_dir():
                    print("Path exists but is not a directory.")
                    continue
                root = str(p.resolve())
                break
            except Exception as e:
                print(f"Error validating path: {e}")

        # Extra Roots
        print("\n--- Extra Allowed Roots (Optional) ---")
        print("You can allow access to additional paths (e.g., external drives).")
        print("Examples: D:\\, /mnt, /media")

        while True:
            extra = input("Add an extra root path (leave empty to finish): ").strip()
            if not extra:
                break

            p_extra = Path(extra)
            try:
                if p_extra.exists() and p_extra.is_dir():
                    extra_roots.append(str(p_extra.resolve()))
                    print(f"Added: {p_extra.resolve()}")
                else:
                    print("Path does not exist or is not a directory. Skipping.")
            except Exception as e:
                print(f"Error: {e}")

    # Save to settings.json
    settings_path = Path("settings.json")
    data = {"settings": {}, "ui_settings": {}}

    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
        except: pass

    if "settings" not in data:
        data["settings"] = {}

    data["settings"]["filesystem_mode"] = mode
    if mode == "jailed":
        data["settings"]["filesystem_root"] = root
        data["settings"]["filesystem_extra_roots"] = extra_roots
        print(f"\nMode set to JAILED. Root: {root}")
        if extra_roots:
            print(f"Extra Roots: {extra_roots}")
    else:
        print("\nMode set to OPEN (Full Access).")

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    input("\nPress Enter to return to menu...")

def configure_tailscale():
    print_header("Tailscale (Remote Access)")
    if platform.system() != "Linux":
        print("Note: Automated Tailscale installation is only supported on Linux.")
        return

    choice = input("Install Tailscale? (y/N): ").strip().lower()
    if choice in ['y', 'yes']:
        print("Installing Tailscale...")
        try:
            # Using the official install script for better compatibility
            subprocess.check_call("curl -fsSL https://tailscale.com/install.sh | sh", shell=True)
            print("Tailscale installed. You may need to run 'sudo tailscale up' to connect.")
        except subprocess.CalledProcessError:
             print("Tailscale installation failed. Please install manually.")
    else:
        print("Skipping Tailscale.")

    input("\nPress Enter to return to menu...")

def configure_service():
    print_header("Service Installer")
    choice = input("Install RemoDash as a system service/startup task? (y/N): ").strip().lower()
    if choice not in ['y', 'yes']:
        print("Skipping service installation.")
        return

    if platform.system() == "Windows":
        # Windows: Startup Folder Shortcut via VBS
        try:
            startup_folder = os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup')
            if not os.path.exists(startup_folder):
                print(f"Error: Startup folder not found at {startup_folder}")
                return

            # Ensure we have a .bat file to launch
            bat_path = Path("start_remodash.bat").resolve()
            with open(bat_path, "w") as f:
                f.write(f'@echo off\ncd /d "{os.getcwd()}"\n"{venv_python}" server.py\n')

            # Create VBS script in startup to launch invisible
            vbs_path = os.path.join(startup_folder, "RemoDash.vbs")
            with open(vbs_path, "w") as f:
                f.write('Set WshShell = CreateObject("WScript.Shell")\n')
                f.write(f'WshShell.Run chr(34) & "{bat_path}" & chr(34), 0\n')
                f.write('Set WshShell = Nothing\n')

            print(f"Created startup entry: {vbs_path}")
            print("RemoDash will start automatically on login.")

        except Exception as e:
            print(f"Error installing service: {e}")

    elif platform.system() == "Linux":
        # Linux: systemd service
        if os.geteuid() != 0:
            print("Error: You must run this script with sudo to install a systemd service.")
            return

        try:
            # Determine user
            user = os.environ.get('SUDO_USER') or os.environ.get('USER')
            if not user or user == 'root':
                user = input("Enter username to run service as: ").strip()

            cwd = str(Path.cwd().resolve())
            python_path = str(Path(venv_python).resolve())
            server_script = str(Path("server.py").resolve())

            service_content = f"""[Unit]
Description=RemoDash Server
After=network.target

[Service]
User={user}
WorkingDirectory={cwd}
ExecStart={python_path} {server_script}
Restart=always

[Install]
WantedBy=multi-user.target
"""
            service_path = "/etc/systemd/system/remodash.service"
            with open(service_path, "w") as f:
                f.write(service_content)

            print(f"Created {service_path}")

            print("Reloading systemd...")
            subprocess.check_call(["systemctl", "daemon-reload"])

            print("Enabling service...")
            subprocess.check_call(["systemctl", "enable", "remodash"])

            choice = input("Start service now? (Y/n): ").strip().lower()
            if choice in ['y', 'yes', '']:
                subprocess.check_call(["systemctl", "start", "remodash"])
                print("Service started.")

        except Exception as e:
             print(f"Error installing service: {e}")

    input("\nPress Enter to return to menu...")

def configure_port():
    print_header("Server Port")
    current_port = "8240"
    port_file = Path("port.txt")
    if port_file.exists():
        try:
            current_port = port_file.read_text().strip()
        except:
            pass

    print(f"Current Port: {current_port}")
    choice = input(f"Change Port? (current: {current_port}) (y/N): ").strip().lower()
    if choice in ['y', 'yes']:
        new_port = input("Enter new port number: ").strip()
        if new_port.isdigit():
            try:
                port_file.write_text(new_port)
                print(f"Port updated to {new_port}.")
            except Exception as e:
                print(f"Error saving port: {e}")
        else:
            print("Invalid port number. Keeping current port.")
    else:
        print("Keeping current port.")

    input("\nPress Enter to return to menu...")

def configure_auth():
    print_header("Authentication")
    token_file = Path("admin_token.txt")

    if token_file.exists():
        print("Admin Token: Found.")
        choice = input("Regenerate Admin Token? (y/N): ").strip().lower()
        if choice in ['y', 'yes']:
             run_token_gen()
    else:
        print("Admin Token: Not Found.")
        choice = input("Generate Admin Token? (Y/n): ").strip().lower()
        if choice in ['y', 'yes', '']:
            run_token_gen()
        else:
            print("WARNING: No admin token generated. You may not be able to log in unless No-Auth mode is enabled.")

    input("\nPress Enter to return to menu...")

def run_token_gen():
    try:
        subprocess.check_call([venv_python, "token_generator.py"])
    except Exception as e:
        print(f"Error generating token: {e}")

def check_root():
    if os.geteuid() != 0:
        print("Error: This operation requires root privileges. Please run with sudo.")
        return False
    return True

def get_wifi_interfaces():
    interfaces = []
    try:
        # Prefer iw dev
        output = subprocess.check_output(["iw", "dev"], text=True)
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Interface "):
                interfaces.append(line.split()[1])
    except: pass

    if not interfaces:
        try:
            # Fallback to ip link
            output = subprocess.check_output(["ip", "link"], text=True)
            for line in output.splitlines():
                if ": wl" in line or ": wlp" in line: # heuristic
                    parts = line.split(": ")
                    if len(parts) >= 2:
                        interfaces.append(parts[1])
        except: pass

    return list(set(interfaces))

def wifi_scan(iface):
    networks = []
    try:
        subprocess.run(["ip", "link", "set", iface, "up"], check=False)
        cmd = ["iw", "dev", iface, "scan"]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            print(f"Scan failed: {proc.stderr}")
            return []

        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.startswith("SSID: "):
                ssid = line[6:].strip()
                if ssid:
                    networks.append(ssid)
    except Exception as e:
        print(f"Scan error: {e}")

    return sorted(list(set(networks)))

def wifi_connect(iface, ssid, password):
    print(f"\nConnecting to '{ssid}' on {iface}...")
    conf_file = f"/etc/wpa_supplicant/wpa_supplicant-{iface}.conf"

    try:
        # Generate Config
        if not password:
            print("Configuring open network...")
            with open(conf_file, "w") as f:
                f.write(f'network={{\n\tssid="{ssid}"\n\tkey_mgmt=NONE\n}}\n')
        else:
            # Use wpa_passphrase
            cmd = ["wpa_passphrase", ssid, password]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode != 0:
                print(f"Error generating passphrase: {proc.stderr}")
                return False

            with open(conf_file, "w") as f:
                f.write(proc.stdout)

        os.chmod(conf_file, 0o600)

        # Kill existing
        print("Stopping existing wpa_supplicant processes...")
        subprocess.run(["pkill", "-f", f"wpa_supplicant.*-i {iface}"], check=False)
        # Also release DHCP
        subprocess.run(["dhclient", "-r", iface], check=False)
        time.sleep(1)

        # Start wpa_supplicant
        print("Starting wpa_supplicant...")
        # -B background, -D nl80211, -i iface, -c conf
        # Using -D nl80211,wext to try both
        wpa_cmd = ["wpa_supplicant", "-B", "-D", "nl80211,wext", "-i", iface, "-c", conf_file, "-p", "use_p2p_group_interface=0"]

        proc = subprocess.run(wpa_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            print(f"wpa_supplicant failed: {proc.stderr}")
            return False

        # DHCP
        print("Obtaining IP address (dhclient)...")
        # dhclient -v iface
        proc = subprocess.run(["dhclient", "-v", iface], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
             print(f"dhclient failed: {proc.stderr}")
             return False

        # Verify
        print("Verifying connection (ping)...")
        try:
            # ping 1.1.1.1 -c 3 -W 2
            subprocess.check_call(["ping", "-c", "3", "-W", "2", "1.1.1.1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("\nSUCCESS: Wi-Fi Connected!")
            save_wizard_state("last_wifi_ssid", ssid)
            save_wizard_state("last_wifi_iface", iface)

            # Show IP
            try:
                ip_out = subprocess.check_output(["ip", "-4", "addr", "show", iface], text=True)
                match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", ip_out)
                if match:
                    print(f"IP Address: {match.group(1)}")
            except: pass

            return True

        except subprocess.CalledProcessError:
            print("\nWARNING: Connected to Wi-Fi but Internet ping failed.")
            print("Check your password, gateway, or DNS settings.")
            return True # Technically connected layer 2/3

    except Exception as e:
        print(f"Connection Error: {e}")
        return False

def wifi_disconnect(iface):
    print(f"Disconnecting {iface}...")
    subprocess.run(["dhclient", "-r", iface], check=False)
    subprocess.run(["pkill", "-f", f"wpa_supplicant.*-i {iface}"], check=False)
    subprocess.run(["ip", "link", "set", iface, "down"], check=False)
    print("Disconnected.")

def wifi_ignore_nm():
    print("\nConfiguring NetworkManager to ignore Wi-Fi devices...")
    conf_dir = Path("/etc/NetworkManager/conf.d")
    conf_path = conf_dir / "99-ignore-wifi.conf"

    if not Path("/etc/NetworkManager").exists():
        print("NetworkManager configuration directory not found. Is it installed?")
        return

    content = "[keyfile]\nunmanaged-devices=type:wifi\n"

    try:
        conf_dir.mkdir(parents=True, exist_ok=True)
        with open(conf_path, "w") as f:
            f.write(content)
        print(f"Created {conf_path}")

        if shutil.which("systemctl"):
            print("Restarting NetworkManager...")
            subprocess.run(["systemctl", "restart", "NetworkManager"], check=False)
        print("Done.")
    except Exception as e:
        print(f"Error: {e}")

def configure_wifi():
    print_header("Wi-Fi Setup (wpa_supplicant)")

    if not check_root():
        input("\nPress Enter to return to menu...")
        return

    # Check dependencies
    deps = ["iw", "wpa_supplicant", "dhclient", "ip"]
    missing = [d for d in deps if not shutil.which(d)]
    if missing:
        print(f"Error: Missing required tools: {', '.join(missing)}")
        print("Please install them (e.g., sudo apt install wireless-tools wpasupplicant isc-dhcp-client)")
        input("\nPress Enter to return to menu...")
        return

    interfaces = get_wifi_interfaces()
    if not interfaces:
        print("No wireless interfaces found.")
        input("\nPress Enter to return to menu...")
        return

    selected_iface = interfaces[0]
    # Use last saved iface if available
    saved_iface = load_wizard_state("last_wifi_iface")
    if saved_iface and saved_iface in interfaces:
        selected_iface = saved_iface

    if len(interfaces) > 1:
        print("\nAvailable Interfaces:")
        for i, iface in enumerate(interfaces):
            marker = "*" if iface == selected_iface else " "
            print(f"{i+1}. {iface} {marker}")

        while True:
            sel = input(f"\nSelect Interface [{interfaces.index(selected_iface)+1}]: ").strip()
            if not sel:
                break
            if sel.isdigit() and 1 <= int(sel) <= len(interfaces):
                selected_iface = interfaces[int(sel)-1]
                break
            print("Invalid selection.")

    print(f"\nSelected Interface: {selected_iface}")

    while True:
        print(f"\n--- Wi-Fi Menu ({selected_iface}) ---")
        print("1. Scan and Connect")
        print("2. Enter SSID Manually (Hidden/Open)")
        print("3. Disconnect / Release DHCP")
        print("4. Configure NetworkManager to Ignore Wi-Fi")
        print("0. Back to Main Menu")

        choice = input("\nChoice: ").strip()

        if choice == "1":
            networks = wifi_scan(selected_iface)
            if networks:
                print("\nAvailable Networks:")
                for i, ssid in enumerate(networks):
                    print(f"{i+1}. {ssid}")

                sel = input("\nSelect Network (number) or 0 to cancel: ").strip()
                if sel and sel.isdigit() and 1 <= int(sel) <= len(networks):
                    ssid = networks[int(sel)-1]
                    password = getpass.getpass(f"Password for '{ssid}': ").strip()
                    wifi_connect(selected_iface, ssid, password)

        elif choice == "2":
            ssid = input("Enter SSID: ").strip()
            if ssid:
                password = getpass.getpass(f"Password for '{ssid}' (leave empty for open): ").strip()
                wifi_connect(selected_iface, ssid, password)

        elif choice == "3":
            wifi_disconnect(selected_iface)

        elif choice == "4":
            wifi_ignore_nm()

        elif choice == "0":
            return

        else:
            print("Invalid choice.")

def bt_check_install():
    if not shutil.which("bluetoothctl"):
        print("bluetoothctl not found. Installing bluez...")
        try:
            subprocess.run(["apt", "update"], check=False)
            subprocess.run(["apt", "install", "-y", "bluez", "bluez-tools"], check=True)
            subprocess.run(["systemctl", "enable", "--now", "bluetooth"], check=False)
        except Exception as e:
            print(f"Error installing bluez: {e}")
            return False

    # Ensure service is running
    subprocess.run(["systemctl", "start", "bluetooth"], check=False)
    return True

def bt_scan(timeout=10):
    print(f"Scanning for {timeout} seconds...")
    try:
        # Start scan in background?
        # bluetoothctl scan on is blocking.
        # We can run it with timeout if supported, otherwise manual kill.
        try:
            subprocess.run(["bluetoothctl", "--timeout", str(timeout), "scan", "on"], check=False)
        except:
            # Fallback
            proc = subprocess.Popen(["bluetoothctl", "scan", "on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(timeout)
            proc.terminate()

    except Exception as e:
        print(f"Scan error: {e}")

def bt_list_devices():
    devices = []
    try:
        output = subprocess.check_output(["bluetoothctl", "devices"], text=True)
        for line in output.splitlines():
            # Device XX:XX:XX:XX:XX:XX Name
            parts = line.split(" ", 2)
            if len(parts) >= 3 and parts[0] == "Device":
                devices.append({"mac": parts[1], "name": parts[2]})
    except: pass
    return devices

def bt_pair_connect(mac):
    print(f"Pairing with {mac}...")
    subprocess.run(["bluetoothctl", "pair", mac], check=False)
    print("Trusting...")
    subprocess.run(["bluetoothctl", "trust", mac], check=False)
    print("Connecting...")
    subprocess.run(["bluetoothctl", "connect", mac], check=False)

def bt_remove(mac):
    print(f"Removing {mac}...")
    subprocess.run(["bluetoothctl", "remove", mac], check=False)

def configure_bluetooth():
    print_header("Bluetooth Setup (bluez)")

    if not check_root():
        input("\nPress Enter to return to menu...")
        return

    if not bt_check_install():
        print("Bluetooth tools missing and installation failed.")
        input("\nPress Enter to return to menu...")
        return

    save_wizard_state("bluetooth_enabled", True)

    while True:
        print("\n--- Bluetooth Menu ---")
        print("1. Power On")
        print("2. Power Off")
        print("3. Scan for Devices")
        print("4. List Known Devices")
        print("5. Pair & Connect (Select from List)")
        print("6. Remove Device")
        print("0. Back to Main Menu")

        choice = input("\nChoice: ").strip()

        if choice == "1":
            subprocess.run(["bluetoothctl", "power", "on"], check=False)
        elif choice == "2":
            subprocess.run(["bluetoothctl", "power", "off"], check=False)
        elif choice == "3":
            bt_scan()
        elif choice == "4":
            devs = bt_list_devices()
            if not devs:
                print("No devices found.")
            else:
                for d in devs:
                    print(f"{d['mac']} - {d['name']}")
        elif choice == "5":
            devs = bt_list_devices()
            if not devs:
                print("No devices found. Run a scan first.")
            else:
                print("\nDevices:")
                for i, d in enumerate(devs):
                    print(f"{i+1}. {d['name']} ({d['mac']})")

                sel = input("\nSelect Device: ").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(devs):
                    mac = devs[int(sel)-1]['mac']
                    bt_pair_connect(mac)
        elif choice == "6":
            devs = bt_list_devices()
            if not devs:
                 print("No devices found.")
            else:
                print("\nDevices:")
                for i, d in enumerate(devs):
                    print(f"{i+1}. {d['name']} ({d['mac']})")

                sel = input("\nSelect Device to Remove: ").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(devs):
                    mac = devs[int(sel)-1]['mac']
                    bt_remove(mac)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")

def run_diagnostics():
    print_header("System Diagnostics")
    print("Collecting system information...\n")

    commands = [
        ("Wireless Interfaces", ["iw", "dev"]),
        ("IP Addresses", ["ip", "a"]),
        ("Routing Table", ["ip", "route"]),
        ("RFKill Status", ["rfkill", "list"]),
        ("Service Status", ["systemctl", "status", "bluetooth", "NetworkManager", "wpa_supplicant", "--no-pager"]),
    ]

    output_log = []

    for title, cmd in commands:
        print(f"--- {title} ---")
        output_log.append(f"\n--- {title} ---")
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(res.stdout)
            output_log.append(res.stdout)
        except FileNotFoundError:
            print(f"Command not found: {cmd[0]}")
            output_log.append(f"Command not found: {cmd[0]}")
        except Exception as e:
            print(f"Error: {e}")
            output_log.append(f"Error: {e}")
        print("-" * 40 + "\n")
        output_log.append("-" * 40 + "\n")

    print("--- DMESG (WiFi/Bluetooth) ---")
    output_log.append("\n--- DMESG (WiFi/Bluetooth) ---")
    try:
        # dmesg | tail -n 200 | grep ...
        # Doing this in python to be safe with pipes
        dmesg = subprocess.run(["dmesg"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        lines = dmesg.stdout.splitlines()[-200:]
        filtered = [l for l in lines if re.search(r'(firmware|iwl|rtl|wlan|wifi|blue)', l, re.IGNORECASE)]

        for l in filtered:
            print(l)
            output_log.append(l)
    except Exception as e:
        print(f"Error reading dmesg: {e}")
        output_log.append(f"Error reading dmesg: {e}")

    print("\nDiagnostics complete.")

    save = input("Save to 'diagnostics.txt'? (Y/n): ").strip().lower()
    if save in ['y', 'yes', '']:
        try:
            with open("diagnostics.txt", "w") as f:
                f.write("\n".join(output_log))
            print("Saved to diagnostics.txt")
        except Exception as e:
            print(f"Error saving file: {e}")

    input("\nPress Enter to return to menu...")

def start_server():
    print_header("Launch Server")
    choice = input("Start RemoDash Server now? (Y/n): ").strip().lower()
    if choice in ['y', 'yes', '']:
        print("\nStarting Server...")
        try:
            # Use the python executable determined during dependency install (venv or system)
            subprocess.run([venv_python, "server.py"])
        except KeyboardInterrupt:
            print("\nServer stopped.")
        except Exception as e:
            print(f"Error starting server: {e}")
    else:
        print("Cancelled.")

def main_menu():
    while True:
        print_header("REMODASH LINUX WIZARD")
        print("1.  Install/Update Dependencies")
        print("2.  Configure Port")
        print("3.  Authentication Setup")
        print("4.  General Settings (Device Name, VLC)")
        print("5.  Filesystem Access Mode")
        print("6.  Wi-Fi Setup (wpa_supplicant)")
        print("7.  Bluetooth Setup (bluez)")
        print("8.  Diagnostics")
        print("9.  Install Tailscale")
        print("10. Install as Service")
        print("11. Start Server")
        print("0.  Exit")

        choice = input("\nEnter choice [0-11]: ").strip()

        if choice == "1":
            install_dependencies()
        elif choice == "2":
            configure_port()
        elif choice == "3":
            configure_auth()
        elif choice == "4":
            configure_general()
        elif choice == "5":
            configure_filesystem_mode()
        elif choice == "6":
            configure_wifi()
        elif choice == "7":
            configure_bluetooth()
        elif choice == "8":
            run_diagnostics()
        elif choice == "9":
            configure_tailscale()
        elif choice == "10":
            configure_service()
        elif choice == "11":
            start_server()
        elif choice == "0":
            print("\nExiting wizard. Goodbye!")
            sys.exit(0)
        else:
            print("\nInvalid choice. Please try again.")
            time.sleep(1)

def main():
    # Initial dependency check or offer
    # We can go straight to menu, but maybe good to check if we can run python?
    # No, we are running python.
    main_menu()

if __name__ == "__main__":
    main()
