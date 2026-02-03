#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time
from datetime import datetime

# Configuration
SERVICES = {
    "brain": "raven-brain.service",
    "embedded": "raven-embedded.service",
    "dashboard": "raven-dashboard.service"
}

def log(msg, level="INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{level}] {msg}")

def run_cmd(cmd, shell=True):
    try:
        subprocess.check_call(cmd, shell=shell)
    except subprocess.CalledProcessError as e:
        log(f"Command failed: {cmd}", "ERROR")
        sys.exit(1)

def start_car(mode):
    log(f"Starting RAVEN stack in mode: {mode}")
    print("  -> Starting engine... 🏎️")
    print("  -> Lights out and away we go! 🚦")
    
    # Example logic: Start ROS core depending on configuration
    # run_cmd("systemctl start roscore") 
    
    if mode == "autonomous":
        log("Launching Brain Stack...", "INFO")
        # In a real scenario, this calls roslaunch or systemctl
        print("  -> Starting perception pipeline...")
        print("  -> Starting state machine...")
        print("  -> Connecting to Embedded Controller...")
        time.sleep(1)
        log("RAVEN is ONLINE and READY.", "SUCCESS")
        
    elif mode == "manual":
        log("Enabling Manual Control via Dashboard...", "INFO")
        # run_cmd("systemctl start raven-dashboard")

def stop_car():
    log("Stopping RAVEN stack...", "WARN")
    print("  -> Box, box, box! 🏁")
    # run_cmd("systemctl stop raven-brain")
    # run_cmd("systemctl stop raven-embedded")
    print("  -> Stopping all ROS nodes...")
    print("  -> Parking servos...")
    log("RAVEN system HALTED.", "SUCCESS")

def deploy_code():
    log("Deploying latest code...", "INFO")
    print("  -> Pulling from git (origin/main)...")
    # run_cmd("git pull origin main")
    print("  -> Building ROS workspace...")
    time.sleep(1)
    log("Deploy complete! New strategy available.", "SUCCESS")

def tail_logs():
    log("Tailing system logs (Ctrl+C to exit)...", "INFO")
    try:
        while True:
            # Mock log stream
            time.sleep(2)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [BRAIN] Planner: Waypoint reached.")
    except KeyboardInterrupt:
        print("\nLog stream stopped.")

def status_car():
    print("\n--- RAVEN SYSTEM STATUS ---")
    print("CPU Temp:  42.0°C  [OK]")
    print("Battery:   12.4V   [OK]")
    print("ROS Core:  Running [PID 1234]")
    print("---------------------------\n")

def main():
    parser = argparse.ArgumentParser(description="Raven Vehicle Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Start
    start_parser = subparsers.add_parser("start", help="Start the vehicle stack")
    start_parser.add_argument("mode", choices=["autonomous", "manual", "debug"], default="autonomous", nargs="?")

    # Stop
    subparsers.add_parser("stop", help="Stop all vehicle services")

    # Status
    subparsers.add_parser("status", help="Show system diagnostic status")

    # Deploy
    subparsers.add_parser("deploy", help="Pull and build latest code")

    # Logs
    subparsers.add_parser("logs", help="Tail system logs")

    args = parser.parse_args()

    if args.command == "start":
        start_car(args.mode)
    elif args.command == "stop":
        stop_car()
    elif args.command == "status":
        status_car()
    elif args.command == "deploy":
        deploy_code()
    elif args.command == "logs":
        tail_logs()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
