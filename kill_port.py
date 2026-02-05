import psutil
import sys
import os

def list_active_ports():
    """Lists all active TCP/UDP ports and their associated processes."""
    connections = []
    try:
        # Get all network connections (inet = IPv4/IPv6, tcp/udp)
        for conn in psutil.net_connections(kind='inet'):
            if conn.status == psutil.CONN_LISTEN or conn.status == psutil.CONN_ESTABLISHED:
                try:
                    proc = psutil.Process(conn.pid) if conn.pid else None
                    proc_name = proc.name() if proc else "Unknown"
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    proc_name = "Unknown/System"

                connections.append({
                    "pid": conn.pid,
                    "name": proc_name,
                    "local_address": f"{conn.laddr.ip}:{conn.laddr.port}",
                    "port": conn.laddr.port,
                    "status": conn.status
                })
    except psutil.AccessDenied:
        print("Warning: Access Denied to some network information. Try running as root/admin.")
    except Exception as e:
        print(f"Error listing ports: {e}")

    # Sort by port
    connections.sort(key=lambda x: x["port"])
    return connections

def kill_process_on_port(port_to_kill):
    """Finds and kills processes listening on the specified port."""
    killed = False
    for conn in psutil.net_connections(kind='inet'):
        if conn.laddr.port == port_to_kill:
            if conn.pid:
                try:
                    p = psutil.Process(conn.pid)
                    name = p.name()
                    print(f"Killing process {name} (PID {conn.pid}) on port {port_to_kill}...")
                    p.terminate()
                    p.wait(timeout=3)
                    print(f"Successfully killed PID {conn.pid}")
                    killed = True
                except psutil.NoSuchProcess:
                    print(f"Process {conn.pid} already gone.")
                except psutil.AccessDenied:
                    print(f"Error: Access Denied to kill PID {conn.pid}. Try running as root/admin.")
                except Exception as e:
                    print(f"Error killing PID {conn.pid}: {e}")
            else:
                print(f"Port {port_to_kill} is in use but no PID found (System/Kernel owned?).")

    if not killed:
        print(f"No active process found listening on port {port_to_kill}.")

def main():
    print("========================================")
    print("   RemoDash Port Killer Utility")
    print("========================================")

    while True:
        print("\nActive Ports:")
        print(f"{'Port':<8} {'PID':<8} {'Process':<20} {'Status':<15} {'Address'}")
        print("-" * 70)

        connections = list_active_ports()
        seen_ports = set()

        for c in connections:
            # simple dedupe for display (same port might have multiple connections)
            # We prioritize LISTEN
            if c['port'] not in seen_ports or c['status'] == psutil.CONN_LISTEN:
                print(f"{c['port']:<8} {str(c['pid']):<8} {c['name']:<20} {c['status']:<15} {c['local_address']}")
                seen_ports.add(c['port'])

        print("-" * 70)
        user_input = input("Enter port to kill (or 'exit'): ").strip()

        if user_input.lower() in ["exit", "quit", "q"]:
            print("Exiting...")
            break

        if not user_input.isdigit():
            print("Invalid input. Please enter a numeric port number.")
            continue

        port = int(user_input)
        kill_process_on_port(port)

        input("\nPress Enter to refresh list...")

if __name__ == "__main__":
    main()
