import os
import sys
import json
import glob
import time
import platform
import subprocess
import shutil
from pathlib import Path

# Try to import evdev, but don't fail if missing
try:
    import evdev
except ImportError:
    evdev = None

class HardwareManager:
    def __init__(self, mock_mode=False):
        self.mock_mode = mock_mode
        self.data_dir = Path("data/config")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.report_path = self.data_dir / "hardware_report.json"
        self.map_path = self.data_dir / "hardware_map.json"
        self.notes_path = self.data_dir / "hardware_map_notes.json"

    def _run_cmd(self, cmd):
        if self.mock_mode:
            return ""
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            return res.stdout.strip()
        except Exception:
            return ""

    def _read_file(self, path):
        if self.mock_mode:
            return ""
        try:
            return Path(path).read_text().strip()
        except Exception:
            return ""

    def scan(self):
        """Generates a hardware report."""
        if self.mock_mode:
            report = self._mock_scan()
        else:
            report = {
                "timestamp": time.time(),
                "os": self._scan_os(),
                "usb": self._scan_usb(),
                "pci": self._scan_pci(),
                "input": self._scan_input(),
                "leds": self._scan_leds(),
                "display": self._scan_display(),
                "power": self._scan_power(),
                "network": self._scan_network(),
                "serial": self._scan_serial(),
                "audio": self._scan_audio()
            }

        self.save_report(report)
        return report

    def save_report(self, report):
        with open(self.report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Hardware report saved to {self.report_path}")

    def _scan_os(self):
        info = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "hostname": platform.node(),
            "cpu": self._get_cpu_info(),
            "ram": self._get_ram_info()
        }
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        info["distro"] = line.split("=", 1)[1].strip().strip('"')
        except:
            pass
        return info

    def _get_cpu_info(self):
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":", 1)[1].strip()
        except:
            pass
        return platform.processor()

    def _get_ram_info(self):
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if "MemTotal" in line:
                        return line.split(":", 1)[1].strip()
        except:
            pass
        return "Unknown"

    def _scan_usb(self):
        devices = []
        output = self._run_cmd("lsusb")
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 6:
                bus = parts[1]
                dev = parts[3].rstrip(':')
                vid_pid = parts[5]
                desc = " ".join(parts[6:])
                devices.append({
                    "bus": bus,
                    "device": dev,
                    "id": vid_pid,
                    "description": desc
                })
        return devices

    def _scan_pci(self):
        devices = []
        output = self._run_cmd("lspci -nn")
        for line in output.splitlines():
            devices.append({"raw": line})
        return devices

    def _scan_input(self):
        devices = []
        input_path = Path("/dev/input")
        if input_path.exists():
            for event_dev in input_path.glob("event*"):
                dev_path = str(event_dev)
                name = "Unknown"
                phys = ""
                uniq = ""

                sys_path = Path(f"/sys/class/input/{event_dev.name}/device/name")
                if sys_path.exists(): name = self._read_file(sys_path)

                sys_phys = Path(f"/sys/class/input/{event_dev.name}/device/phys")
                if sys_phys.exists(): phys = self._read_file(sys_phys)

                sys_uniq = Path(f"/sys/class/input/{event_dev.name}/device/uniq")
                if sys_uniq.exists(): uniq = self._read_file(sys_uniq)

                category = "unknown"
                lower_name = name.lower()
                if "keyboard" in lower_name or "kbd" in lower_name: category = "keyboard"
                elif "mouse" in lower_name: category = "mouse"
                elif "touch" in lower_name: category = "touch"
                elif "button" in lower_name or "power" in lower_name or "lid" in lower_name: category = "button"

                stable_path = self.get_stable_path(dev_path)

                devices.append({
                    "path": dev_path,
                    "stable_path": stable_path,
                    "name": name,
                    "phys": phys,
                    "uniq": uniq,
                    "category": category
                })
        return devices

    def get_stable_path(self, device_path):
        if self.mock_mode:
             return device_path.replace("/event", "/by-id/mock-event")

        by_id = Path("/dev/input/by-id")
        if by_id.exists():
            for link in by_id.iterdir():
                if link.is_symlink() and str(link.resolve()) == str(Path(device_path).resolve()):
                    return str(link)

        by_path = Path("/dev/input/by-path")
        if by_path.exists():
            for link in by_path.iterdir():
                if link.is_symlink() and str(link.resolve()) == str(Path(device_path).resolve()):
                    return str(link)

        return device_path

    def _scan_leds(self):
        leds = []
        base = Path("/sys/class/leds")
        if base.exists():
            for led_dir in base.iterdir():
                name = led_dir.name
                max_brightness = self._read_file(led_dir / "max_brightness")
                brightness = self._read_file(led_dir / "brightness")
                trigger = self._read_file(led_dir / "trigger")

                current_trigger = "none"
                if "[" in trigger:
                    import re
                    m = re.search(r'\[(.*?)\]', trigger)
                    if m: current_trigger = m.group(1)

                leds.append({
                    "name": name,
                    "path": str(led_dir),
                    "max_brightness": int(max_brightness) if max_brightness.isdigit() else 1,
                    "brightness": int(brightness) if brightness.isdigit() else 0,
                    "trigger": current_trigger,
                    "available_triggers": trigger
                })
        return leds

    def _scan_display(self):
        displays = []
        base = Path("/sys/class/backlight")
        if base.exists():
            for bl_dir in base.iterdir():
                name = bl_dir.name
                max_b = self._read_file(bl_dir / "max_brightness")
                curr_b = self._read_file(bl_dir / "brightness")
                displays.append({
                    "type": "backlight",
                    "name": name,
                    "path": str(bl_dir),
                    "max_brightness": int(max_b) if max_b.isdigit() else 100,
                    "brightness": int(curr_b) if curr_b.isdigit() else 50
                })

        if shutil.which("xset"):
             displays.append({"type": "x11_dpms", "available": True})

        return displays

    def _scan_power(self):
        power = {"batteries": [], "lid": None, "logind": {}}
        base = Path("/sys/class/power_supply")
        if base.exists():
            for supply in base.iterdir():
                type_ = self._read_file(supply / "type")
                if type_ == "Battery":
                    capacity = self._read_file(supply / "capacity")
                    status = self._read_file(supply / "status")
                    power["batteries"].append({
                        "name": supply.name,
                        "capacity": capacity,
                        "status": status
                    })

        try:
             with open("/etc/systemd/logind.conf") as f:
                 for line in f:
                     line = line.strip()
                     if line.startswith("HandlePowerKey="):
                         power["logind"]["HandlePowerKey"] = line.split("=")[1]
                     elif line.startswith("HandleLidSwitch="):
                         power["logind"]["HandleLidSwitch"] = line.split("=")[1]
        except:
            pass

        return power

    def _scan_network(self):
        networks = []
        base = Path("/sys/class/net")
        if base.exists():
            for net in base.iterdir():
                name = net.name
                operstate = self._read_file(net / "operstate")
                address = self._read_file(net / "address")
                networks.append({"name": name, "state": operstate, "mac": address})

        rfkills = []
        rf_out = self._run_cmd("rfkill list -o ID,TYPE,SOFT,HARD -n")
        for line in rf_out.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                rfkills.append({
                    "id": parts[0],
                    "type": parts[1],
                    "soft": parts[2],
                    "hard": parts[3]
                })

        return {"interfaces": networks, "rfkill": rfkills}

    def _scan_serial(self):
        ports = []
        for p in glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"):
             ports.append({"path": p, "type": "usb_serial"})

        by_id = Path("/dev/serial/by-id")
        if by_id.exists():
             for link in by_id.iterdir():
                 ports.append({"path": str(link), "resolved": str(link.resolve()), "type": "by-id"})
        return ports

    def _scan_audio(self):
        cards = []
        try:
            with open("/proc/asound/cards") as f:
                cards = [line.strip() for line in f if line.strip()]
        except: pass
        return cards

    # --- Mapping Logic ---

    def propose_map(self, report):
        """Generates a proposed hardware map based on heuristics."""
        m = {
            "capabilities": {},
            "settings": {},
            "unmapped": []
        }

        # 1. Inputs
        for dev in report.get("input", []):
            name = dev["name"].lower()
            mapped = False

            # Buttons
            if "power" in name and "button" in name:
                m["capabilities"]["button.power"] = dev["stable_path"]
                mapped = True
            elif "lid" in name:
                m["capabilities"]["button.lid"] = dev["stable_path"]
                mapped = True

            # Scanners
            if "scanner" in name or "barcode" in name:
                m["capabilities"]["scanner.barcode"] = dev["stable_path"]
                m["settings"]["scanner.barcode"] = {"mode": "keyboard", "prefix": "", "suffix": "enter"}
                mapped = True

            if not mapped:
                m["unmapped"].append({"type": "input", "info": dev})

        # 2. LEDs
        for led in report.get("leds", []):
            name = led["name"]
            # Heuristics
            if "mmc" in name or "disk" in name:
                m["capabilities"]["led.activity"] = led["path"]
            elif "pwr" in name or "power" in name:
                m["capabilities"]["led.status"] = led["path"]
            else:
                m["unmapped"].append({"type": "led", "info": led})

        # 3. Display
        for disp in report.get("display", []):
            if disp["type"] == "backlight":
                # Assuming first backlight is main screen
                if "screen.backlight" not in m["capabilities"]:
                    m["capabilities"]["screen.backlight"] = disp["path"]
                else:
                     m["unmapped"].append({"type": "backlight", "info": disp})
            elif disp["type"] == "x11_dpms":
                m["capabilities"]["screen.dpms"] = "x11"

        # 4. Radios
        for rf in report.get("network", {}).get("rfkill", []):
            if rf["type"] == "wlan":
                m["capabilities"]["radio.wifi"] = rf["id"]
            elif rf["type"] == "bluetooth":
                m["capabilities"]["radio.bt"] = rf["id"]
            elif rf["type"] == "wwan":
                m["capabilities"]["radio.wwan"] = rf["id"]

        # 5. Power Settings
        logind = report.get("power", {}).get("logind", {})
        if "HandlePowerKey" in logind:
            m["settings"]["power.powerkey_behavior"] = logind["HandlePowerKey"]
        if "HandleLidSwitch" in logind:
             m["settings"]["power.lid_behavior"] = logind["HandleLidSwitch"]

        return m

    def interactive_map(self, report, current_map):
        """
        Interactive CLI loop to refine the map.
        Returns the updated map.
        """
        print("\n--- Interactive Hardware Mapper ---")

        capabilities = [
            "button.power", "button.vol_up", "button.vol_down", "button.custom_1",
            "led.status", "led.activity",
            "touch.primary", "scanner.barcode",
            "radio.wifi", "radio.bt", "radio.wwan",
            "screen.backlight"
        ]

        updated_map = current_map.copy()

        for cap in capabilities:
            print(f"\nConfiguration for: {cap}")
            current = updated_map["capabilities"].get(cap, "Unmapped")
            print(f"  Current Binding: {current}")

            print("  [K]eep, [C]hange, [T]est/Identify, [S]kip")
            choice = input("  Choice: ").lower().strip()

            if choice == "c":
                # List candidates based on type
                candidates = []
                if cap.startswith("button") or cap.startswith("scanner") or cap.startswith("touch"):
                     candidates = report.get("input", [])
                elif cap.startswith("led"):
                     candidates = report.get("leds", [])
                elif cap.startswith("screen.backlight"):
                     candidates = [d for d in report.get("display", []) if d["type"] == "backlight"]
                elif cap.startswith("radio"):
                     candidates = report.get("network", {}).get("rfkill", [])

                if not candidates:
                    print("  No candidates found in report.")
                    continue

                print("  Available Devices:")
                for idx, cand in enumerate(candidates):
                    # Format display string based on type
                    desc = cand.get("name", cand.get("stable_path", str(cand)))
                    print(f"  {idx + 1}. {desc}")

                sel = input("  Select device # (or '0' to clear): ").strip()
                if sel.isdigit():
                    idx = int(sel)
                    if idx == 0:
                        if cap in updated_map["capabilities"]:
                            del updated_map["capabilities"][cap]
                        print(f"  Cleared {cap}")
                    elif 1 <= idx <= len(candidates):
                        selected = candidates[idx-1]
                        # Determine binding value
                        val = None
                        if cap.startswith("radio"):
                             val = selected["id"]
                        elif "stable_path" in selected:
                             val = selected["stable_path"]
                        elif "path" in selected:
                             val = selected["path"]

                        updated_map["capabilities"][cap] = val
                        print(f"  Set {cap} -> {val}")

            elif choice == "t":
                self.test_capability(cap, updated_map["capabilities"].get(cap))

        # Settings
        print("\n--- Power Settings ---")
        print("Supported: poweroff, suspend, hibernate, ignore, reboot")
        for setting in ["power.powerkey_behavior", "power.lid_behavior"]:
            curr = updated_map["settings"].get(setting, "ignore")
            print(f"  {setting}: {curr}")
            new_val = input(f"  New value (Enter to keep): ").strip()
            if new_val:
                updated_map["settings"][setting] = new_val

        return updated_map

    def test_capability(self, cap, binding):
        if not binding:
            print("  No binding to test.")
            return

        print(f"  Testing {cap} on {binding}...")

        if cap.startswith("led"):
            # Flash LED
            if self.mock_mode:
                print(f"  [MOCK] Flashing LED at {binding}")
            else:
                try:
                     path = Path(binding) / "brightness"
                     max_path = Path(binding) / "max_brightness"
                     if path.exists():
                         max_val = int(Path(max_path).read_text().strip()) if max_path.exists() else 1
                         current = int(Path(path).read_text().strip())
                         # Blink
                         Path(path).write_text(str(max_val))
                         time.sleep(0.5)
                         Path(path).write_text("0")
                         time.sleep(0.5)
                         Path(path).write_text(str(current))
                         print("  LED flashed.")
                except Exception as e:
                    print(f"  Test failed: {e}")

        elif cap.startswith("screen.backlight"):
            if self.mock_mode:
                print(f"  [MOCK] Dimming backlight at {binding}")
            else:
                 try:
                     path = Path(binding) / "brightness"
                     max_path = Path(binding) / "max_brightness"
                     if path.exists():
                         current = int(Path(path).read_text().strip())
                         max_val = int(Path(max_path).read_text().strip()) if max_path.exists() else 100
                         print(f"  Current: {current}, Max: {max_val}")

                         # Dim test
                         targets = [int(max_val * 0.5), int(max_val * 0.1), current]
                         for t in targets:
                             print(f"  Setting to {t}...")
                             Path(path).write_text(str(t))
                             time.sleep(0.5)
                         print("  Backlight test complete.")
                 except Exception as e:
                     print(f"  Test failed: {e}")

        elif cap.startswith("button") or cap.startswith("scanner"):
            print("  Press the button/scan now... (Ctrl+C to stop)")
            if self.mock_mode:
                print("  [MOCK] Detected keypress: KEY_POWER")
                time.sleep(1)
            else:
                if evdev:
                    try:
                        dev = evdev.InputDevice(binding)
                        print(f"  Listening on {dev.name} ({dev.phys})...")
                        for event in dev.read_loop():
                            if event.type == evdev.ecodes.EV_KEY:
                                print(f"  Event: {evdev.categorize(event)}")
                                # Break after first key release for test
                                if event.value == 0:
                                    break
                    except Exception as e:
                        print(f"  evdev error: {e}")
                else:
                    print(f"  evdev not installed. Please run 'evtest {binding}' manually.")
                    # wait for user to ack
                    input("  Press Enter to continue...")

    def save_map(self, map_data):
        with open(self.map_path, "w") as f:
            json.dump(map_data, f, indent=2)

        # Also save notes (unmapped)
        notes = {
            "unmapped": map_data.get("unmapped", []),
            "timestamp": time.time()
        }
        with open(self.notes_path, "w") as f:
            json.dump(notes, f, indent=2)

        print(f"Hardware map saved to {self.map_path}")

    # --- Application Logic ---

    def apply_settings(self, map_data):
        """Applies configuration from the map to the system."""
        print("Applying settings...")

        # 1. Generate Logind Conf
        self.generate_logind_conf(map_data)

        caps = map_data.get("capabilities", {})
        settings = map_data.get("settings", {})

        # 2. Radios (Unblock mapped radios)
        for cap, val in caps.items():
            if cap.startswith("radio."):
                rf_id = val
                if self.mock_mode:
                    print(f"[MOCK] Unblocking radio ID {rf_id} for {cap}")
                else:
                    self._run_cmd(f"rfkill unblock {rf_id}")

        # 3. LEDs & Backlight
        # If specific settings exist (e.g. "led.status.brightness": 255), apply them.
        # Otherwise, we might default to max brightness for status LEDs if mapped?
        # For now, we only apply explicit settings if found in map['settings']
        for key, val in settings.items():
            if key in caps:
                path = caps[key]
                # Check if it's an LED or Backlight setting
                # Expect setting to be a dict like {"brightness": 100} or just a value?
                # Let's assume the key in settings matches the capability name
                # and the value is a dict of attributes to apply.
                if isinstance(val, dict):
                    if "brightness" in val:
                        b_val = val["brightness"]
                        target_path = Path(path) / "brightness"
                        if self.mock_mode:
                            print(f"[MOCK] Setting {key} brightness to {b_val}")
                        else:
                            try:
                                if target_path.exists():
                                    target_path.write_text(str(b_val))
                            except Exception as e:
                                print(f"Failed to set {key} brightness: {e}")

        print("Settings applied.")

    def generate_logind_conf(self, map_data):
        """Generates systemd-logind configuration file."""
        settings = map_data.get("settings", {})

        conf_lines = ["[Login]"]
        has_settings = False

        if "power.powerkey_behavior" in settings:
            val = settings["power.powerkey_behavior"]
            if val != "ignore":
                conf_lines.append(f"HandlePowerKey={val}")
                has_settings = True

        if "power.lid_behavior" in settings:
            val = settings["power.lid_behavior"]
            if val != "ignore":
                conf_lines.append(f"HandleLidSwitch={val}")
                has_settings = True

        if has_settings:
            conf_content = "\n".join(conf_lines) + "\n"
            target = Path("/etc/systemd/logind.conf.d/lyrn-hwmap.conf")

            if self.mock_mode:
                print(f"[MOCK] Would write to {target}:\n{conf_content}")
            else:
                try:
                    # Check directory
                    if not target.parent.exists():
                        # We might need sudo, but assuming we run as root or user handles it
                        try:
                            target.parent.mkdir(parents=True, exist_ok=True)
                        except:
                            print(f"Warning: Could not create {target.parent}")
                            return

                    with open(target, "w") as f:
                        f.write(conf_content)
                    print(f"Written {target}")
                    print("Note: Run 'systemctl restart systemd-logind' to apply changes.")
                except Exception as e:
                    print(f"Failed to write logind conf: {e}")

    def _mock_scan(self):
        """Returns a consistent mock report for testing."""
        return {
            "timestamp": time.time(),
            "os": {
                "system": "Linux",
                "release": "5.10.0-mock",
                "version": "#1 SMP Mock",
                "machine": "x86_64",
                "hostname": "mock-device",
                "distro": "MockOS 1.0",
                "cpu": "Mock CPU @ 2.0GHz",
                "ram": "8GB"
            },
            "usb": [
                {"bus": "001", "device": "002", "id": "1d6b:0002", "description": "Linux Foundation 2.0 root hub"},
                {"bus": "001", "device": "003", "id": "1234:5678", "description": "Mock Barcode Scanner"}
            ],
            "pci": [],
            "input": [
                {
                    "path": "/dev/input/event0",
                    "stable_path": "/dev/input/by-id/mock-power-button",
                    "name": "Power Button",
                    "phys": "LNXPWRBN/input0",
                    "uniq": "",
                    "category": "button"
                },
                {
                    "path": "/dev/input/event1",
                    "stable_path": "/dev/input/by-path/platform-i8042-serio-0-event-kbd",
                    "name": "AT Translated Set 2 keyboard",
                    "phys": "isa0060/serio0/input0",
                    "uniq": "",
                    "category": "keyboard"
                },
                {
                    "path": "/dev/input/event2",
                    "stable_path": "/dev/input/by-id/usb-Mock_Scanner-event-kbd",
                    "name": "Mock Barcode Scanner",
                    "phys": "usb-0000:00:14.0-1/input0",
                    "uniq": "",
                    "category": "keyboard"
                }
            ],
            "leds": [
                {
                    "name": "mmc0::",
                    "path": "/sys/class/leds/mmc0::",
                    "max_brightness": 255,
                    "brightness": 0,
                    "trigger": "mmc0",
                    "available_triggers": "none mmc0 heartbeat"
                },
                {
                    "name": "input2::capslock",
                    "path": "/sys/class/leds/input2::capslock",
                    "max_brightness": 1,
                    "brightness": 0,
                    "trigger": "none",
                    "available_triggers": "none kbd-scrolllock kbd-numlock kbd-capslock"
                }
            ],
            "display": [
                {
                    "type": "backlight",
                    "name": "intel_backlight",
                    "path": "/sys/class/backlight/intel_backlight",
                    "max_brightness": 937,
                    "brightness": 400
                }
            ],
            "power": {
                "batteries": [{"name": "BAT0", "capacity": "85", "status": "Discharging"}],
                "logind": {"HandlePowerKey": "poweroff", "HandleLidSwitch": "suspend"}
            },
            "network": {
                "interfaces": [
                    {"name": "lo", "state": "unknown", "mac": "00:00:00:00:00:00"},
                    {"name": "wlan0", "state": "up", "mac": "aa:bb:cc:dd:ee:ff"}
                ],
                "rfkill": [
                    {"id": "0", "type": "wlan", "soft": "unblocked", "hard": "unblocked"},
                    {"id": "1", "type": "bluetooth", "soft": "blocked", "hard": "unblocked"}
                ]
            },
            "serial": [],
            "audio": ["0 [PCH]: HDA-Intel - HDA Intel PCH"]
        }
