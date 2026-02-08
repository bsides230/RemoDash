import argparse
import sys
import os
import json
from hardware_manager import HardwareManager

def main():
    parser = argparse.ArgumentParser(description="Hardware Scanner and Mapper for Lyrn/RemoDash")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode (simulation)")
    parser.add_argument("--scan", action="store_true", help="Run hardware scan only and exit")
    parser.add_argument("--map", action="store_true", help="Run interactive mapper only (requires existing report)")
    parser.add_argument("--apply", action="store_true", help="Apply settings from existing map and exit")
    parser.add_argument("--auto", action="store_true", help="Run full flow non-interactively (Scan -> Propose -> Save -> Apply)")

    args = parser.parse_args()

    print("Initializing Hardware Manager...")
    hm = HardwareManager(mock_mode=args.mock)

    # 1. Apply Only
    if args.apply:
        if not hm.map_path.exists():
            print(f"Error: Hardware map not found at {hm.map_path}")
            sys.exit(1)

        try:
            with open(hm.map_path) as f:
                map_data = json.load(f)
            hm.apply_settings(map_data)
        except Exception as e:
            print(f"Error applying settings: {e}")
            sys.exit(1)
        return

    # 2. Map Only (Interactive)
    if args.map:
        if not hm.report_path.exists():
            print(f"Error: Hardware report not found at {hm.report_path}. Run --scan first.")
            sys.exit(1)

        try:
            with open(hm.report_path) as f:
                report = json.load(f)

            # Load existing map if present, else propose
            if hm.map_path.exists():
                print("Loading existing map...")
                with open(hm.map_path) as f:
                    current_map = json.load(f)
            else:
                print("Proposing new map...")
                current_map = hm.propose_map(report)

            final_map = hm.interactive_map(report, current_map)
            hm.save_map(final_map)

            # Ask to apply?
            ans = input("Apply settings now? [Y/n]: ").strip().lower()
            if ans != 'n':
                hm.apply_settings(final_map)

        except Exception as e:
            print(f"Error during mapping: {e}")
            sys.exit(1)
        return

    # 3. Scan Only
    if args.scan:
        print("Scanning hardware...")
        hm.scan()
        return

    # 4. Auto (Non-interactive full flow)
    if args.auto:
        print("Running Auto Mode...")
        print("1. Scanning...")
        report = hm.scan()
        print("2. Proposing Map...")
        map_data = hm.propose_map(report)
        print("3. Saving Map...")
        hm.save_map(map_data)
        print("4. Applying Settings...")
        hm.apply_settings(map_data)
        return

    # 5. Default: Full Wizard
    print("\n--- Hardware Setup Wizard ---")

    # Step A: Scan
    print("\n[Step 1/3] Scanning Hardware...")
    report = hm.scan()
    print(f"Scan complete. Found {len(report.get('input', []))} input devices, {len(report.get('leds', []))} LEDs.")

    # Step B: Map
    print("\n[Step 2/3] Mapping Hardware...")
    if hm.map_path.exists():
        ans = input("Existing hardware map found. Use it as base? [Y/n]: ").strip().lower()
        if ans != 'n':
            with open(hm.map_path) as f:
                current_map = json.load(f)
        else:
            current_map = hm.propose_map(report)
    else:
        current_map = hm.propose_map(report)

    final_map = hm.interactive_map(report, current_map)
    hm.save_map(final_map)

    # Step C: Apply
    print("\n[Step 3/3] Applying Settings...")
    hm.apply_settings(final_map)

    print("\nSetup Complete!")

if __name__ == "__main__":
    main()
