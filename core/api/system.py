import os
import sys
import platform
import socket
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import psutil
except ImportError:
    print("[System] Warning: psutil not found. Using mock implementation.")
    psutil = None

try:
    import pynvml
except ImportError:
    pynvml = None

from fastapi import APIRouter, HTTPException, Depends
from core.api.auth import verify_token

router = APIRouter()

# --- Psutil Mock for Android/No-Dep environments ---
if psutil is None:
    class MockPsutil:
        class VirtualMemory:
            percent = 0
            used = 0
            total = 0
        class DiskUsage:
            percent = 0
            used = 0
            total = 0
        class Battery:
            percent = 0
            power_plugged = False
            secsleft = 0
        class CpuFreq:
            current = 0
            max = 0
        class Process:
            def __init__(self, pid): pass
            def terminate(self): pass

        NoSuchProcess = Exception
        AccessDenied = Exception

        @staticmethod
        def cpu_percent(interval=None): return 0
        @staticmethod
        def virtual_memory(): return MockPsutil.VirtualMemory()
        @staticmethod
        def disk_usage(path): return MockPsutil.DiskUsage()
        @staticmethod
        def disk_partitions(): return []
        @staticmethod
        def cpu_count(logical=True): return 1
        @staticmethod
        def cpu_freq(): return MockPsutil.CpuFreq()
        @staticmethod
        def sensors_battery(): return None
        @staticmethod
        def net_io_counters():
            class NetIO:
                def _asdict(self): return {}
            return NetIO()
        @staticmethod
        def process_iter(attrs=None): return []
        @staticmethod
        def Process(pid): return MockPsutil.Process(pid)

    psutil = MockPsutil()

@router.get("/health")
async def health_check():
    # Wrap psutil calls for Android/PermissionError compatibility
    try:
        cpu_percent = psutil.cpu_percent()
    except (PermissionError, Exception):
        cpu_percent = 0

    try:
        ram = psutil.virtual_memory()
    except (PermissionError, Exception):
        # Mock object if access denied
        class MockRAM:
            percent = 0
            used = 0
            total = 0
        ram = MockRAM()

    # Disk Usage (Root)
    try:
        disk = psutil.disk_usage('.')
    except (PermissionError, Exception):
        class MockDisk:
            percent = 0
            used = 0
            total = 0
        disk = MockDisk()

    # Detailed Partitions (New)
    partitions_info = []
    try:
        for part in psutil.disk_partitions():
            try:
                # Skip inaccessible partitions
                if "cdrom" in part.opts or part.fstype == "":
                    continue
                usage = psutil.disk_usage(part.mountpoint)
                partitions_info.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total_gb": usage.total / (1024**3),
                    "used_gb": usage.used / (1024**3),
                    "percent": usage.percent
                })
            except (OSError, PermissionError):
                continue
    except Exception:
        pass

    # Extended System Info

    # CPU Info
    cpu_info = {
        "percent": cpu_percent,
        "count_logical": psutil.cpu_count(logical=True) or 1,
        "count_physical": psutil.cpu_count(logical=False) or 1,
        "freq_current": 0,
        "freq_max": 0
    }
    try:
        freq = psutil.cpu_freq()
        if freq:
            cpu_info["freq_current"] = freq.current
            cpu_info["freq_max"] = freq.max
    except: pass

    # GPU Info
    gpu_stats = {}
    if pynvml:
        try:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_stats[f"gpu_{i}"] = {
                    "name": name,
                    "vram_used_gb": mem_info.used / (1024**3),
                    "vram_total_gb": mem_info.total / (1024**3),
                    "vram_percent": (mem_info.used / mem_info.total) * 100,
                    "gpu_util_percent": util.gpu
                }
        except Exception as e:
            gpu_stats["error"] = str(e)

    # Battery
    battery_info = {}
    try:
        sb = psutil.sensors_battery()
        if sb:
            battery_info = {
                "percent": sb.percent,
                "power_plugged": sb.power_plugged,
                "secsleft": sb.secsleft
            }
        else:
            # Mock fallback for missing battery
            battery_info = {
                "percent": 100,
                "power_plugged": True,
                "secsleft": -1
            }
    except:
        # Mock fallback for errors
        battery_info = {
            "percent": 100,
            "power_plugged": True,
            "secsleft": -1
        }

    # OS Info
    os_info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "node": platform.node()
    }

    # Net IO
    net_io = {}
    try:
        if psutil:
            # Check if implemented
            try:
                net_io = psutil.net_io_counters()._asdict()
            except AttributeError: pass
    except (PermissionError, Exception):
        pass

    return {
        "status": "ok",
        "cpu": cpu_info,
        "ram": {
            "percent": ram.percent,
            "used_gb": ram.used / (1024**3),
            "total_gb": ram.total / (1024**3)
        },
        "disk": {
            "percent": disk.percent,
            "used_gb": disk.used / (1024**3),
            "total_gb": disk.total / (1024**3),
            "partitions": partitions_info
        },
        "gpu": gpu_stats,
        "battery": battery_info,
        "os": os_info,
        "net": net_io
    }

@router.get("/sysinfo", dependencies=[Depends(verify_token)])
async def get_sysinfo():
    """Returns static system information."""
    hostname = socket.gethostname()
    try:
        ip_address = socket.gethostbyname(hostname)
    except:
        ip_address = "Unknown"

    # CPU Model
    cpu_model = "Unknown"
    if platform.system() == "Windows":
        try:
            cpu_model = subprocess.check_output(["wmic", "cpu", "get", "name"]).decode().split("\n")[1].strip()
        except: pass
    elif platform.system() == "Linux":
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        cpu_model = line.split(":")[1].strip()
                        break
        except: pass

    if cpu_model == "Unknown":
        cpu_model = platform.processor()

    # Partitions
    partitions = []
    try:
        for part in psutil.disk_partitions():
            try:
                # Skip inaccessible/dummy partitions
                if "cdrom" in part.opts or part.fstype == "":
                    continue
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "opts": part.opts,
                    "total_gb": usage.total / (1024**3),
                    "used_gb": usage.used / (1024**3),
                    "percent": usage.percent
                })
            except OSError:
                continue
    except: pass

    # Android Detection & Paths
    is_android = "ANDROID_ROOT" in os.environ or "com.termux" in os.environ.get("PREFIX", "")
    standard_paths = []

    # Always include Home
    home_dir = str(Path.home().resolve())

    if is_android:
        standard_paths.append({"name": "Home", "path": home_dir})
        if os.path.exists("/sdcard"):
            standard_paths.append({"name": "Internal Storage", "path": "/sdcard"})

        # Check for Termux storage links
        storage_shared = Path.home() / "storage" / "shared"
        if storage_shared.exists():
             standard_paths.append({"name": "Shared Storage", "path": str(storage_shared.resolve())})

    return {
        "hostname": hostname,
        "ip_address": ip_address,
        "os": f"{platform.system()} {platform.release()}",
        "cpu_model": cpu_model,
        "partitions": partitions,
        "home_dir": home_dir,
        "standard_paths": standard_paths
    }

# --- Power Endpoints ---
@router.post("/power/restart", dependencies=[Depends(verify_token)])
async def restart_server():
    """Restarts the RemoDash server process."""
    try:
        # We use sys.executable to restart the current script
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/power/reboot", dependencies=[Depends(verify_token)])
async def reboot_system():
    """Reboots the host machine."""
    try:
        if platform.system() == "Windows":
            subprocess.run(["shutdown", "/r", "/t", "0"])
        else:
            subprocess.run(["sudo", "reboot"])
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/power/shutdown", dependencies=[Depends(verify_token)])
async def shutdown_system():
    """Shuts down the host machine."""
    try:
        if platform.system() == "Windows":
            subprocess.run(["shutdown", "/s", "/t", "0"])
        else:
            subprocess.run(["sudo", "shutdown", "now"])
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
