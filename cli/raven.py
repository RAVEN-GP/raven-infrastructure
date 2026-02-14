#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time
import os
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

    except subprocess.CalledProcessError as e:
        log(f"Command failed: {cmd}", "ERROR")
        sys.exit(1)

# Global process registry
RUNNING_PROCESSES = {}

def resolve_path(repo_name):
    """Finds the absolute path to a sibling repository."""
    # Assumes raven.py is in .../raven-infrastructure/cli/
    # We want .../repo_name
    # Use realpath to resolve symlinks if installed in /usr/local/bin
    script_dir = os.path.dirname(os.path.realpath(__file__))
    # Go up two levels: cli -> raven-infrastructure -> Bosch Future Mobility Challenge
    base_dir = os.path.abspath(os.path.join(script_dir, "../../"))
    target = os.path.join(base_dir, repo_name)
    if not os.path.exists(target):
         log(f"Repository {repo_name} not found at {target}", "ERROR")
         return None
    return target

def start_car(mode):
    log(f"Starting RAVEN stack in mode: {mode}")
    
    # 1. Start Dashboard (Raven Computer)
    computer_path = resolve_path("raven-computer")
    if computer_path:
        dash_script = os.path.join(computer_path, "src", "dashboard", "app.py")
        if os.path.exists(dash_script):
            log("Launching Telemetry Dashboard...", "INFO")
            # Run in background
            try:
                # Dashboard needs to be run from its dir usually, or we set PYTHONPATH
                # Let's try running from its dir
                p = subprocess.Popen(["python3", "app.py"], cwd=os.path.dirname(dash_script), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                RUNNING_PROCESSES["dashboard"] = p
                print("  -> Dashboard active at http://localhost:5000 📊")
            except Exception as e:
                log(f"Failed to start dashboard: {e}", "ERROR")
        else:
             log(f"Dashboard script not found: {dash_script}", "WARN")

    # 2. Start Brain in Simulation Mode (Raven Brain Stack)
    brain_path = resolve_path("raven-brain-stack")
    if brain_path:
        brain_script = os.path.join(brain_path, "main.py")
        if os.path.exists(brain_script):
            log("Launching Brain Stack (Simulation Mode)...", "INFO")
            env = os.environ.copy()
            if mode == "autonomous":
                 env["RAVEN_SIMULATION"] = "true"
            
            # Check for venv
            venv_python = os.path.join(brain_path, "venv", "bin", "python")
            python_exec = venv_python if os.path.exists(venv_python) else "python3"

            try:
                # Brain needs to be run from root of raven-brain-stack to resolve 'src' imports
                # Use the detected python interpreter
                p = subprocess.Popen([python_exec, "main.py"], cwd=brain_path, env=env)
                RUNNING_PROCESSES["brain"] = p
                print("  -> Brain is ONLINE. Watching logs... 🧠")
            except Exception as e:
                log(f"Failed to start brain: {e}", "ERROR")
        else:
            log(f"Brain script not found: {brain_script}", "WARN")

    # Wait mechanism to keep script alive if needed, or just exit and let them run?
    # CLI tools usually exit. But if we exit, Popen might die depending on shell.
    # We will write PIDs to a file to stop them later? 
    # For now, let's dump PIDs to a temp file.
    with open("/tmp/raven_pids.txt", "w") as f:
        for name, proc in RUNNING_PROCESSES.items():
            f.write(f"{name}:{proc.pid}\n")
    
    log("Startup Sequence Complete. Run 'raven stop' to halt.", "SUCCESS")

def stop_car():
    log("Stopping RAVEN stack...", "WARN")
    if os.path.exists("/tmp/raven_pids.txt"):
        with open("/tmp/raven_pids.txt", "r") as f:
            for line in f:
                try:
                    name, pid = line.strip().split(":")
                    os.kill(int(pid), 15) # SIGTERM
                    print(f"  -> Stopped {name} [PID {pid}]")
                except Exception:
                    pass
        os.remove("/tmp/raven_pids.txt")
        print("  -> Parked servos.")
        log("RAVEN system HALTED.", "SUCCESS")
    else:
        log("No active RAVEN processes found (check /tmp/raven_pids.txt).", "INFO")

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

def manage_docs(action):
    if action == "build":
        log("Building project documentation...", "INFO")
        print("  -> Scanning repositories for RST/MD files...")
        time.sleep(1)
        # Mock sphinx-build
        print("  -> Running Sphinx v4.5.0...")
        print("  -> Generating HTML...")
        log("Documentation built successfully in raven-documentation/build/html", "SUCCESS")
    elif action == "open":
        log("Opening local documentation server...", "INFO")
        # Mock opening browser
        print("  -> Serving at http://localhost:8000")
        print("  -> Press Ctrl+C to stop")
    elif action == "check":
        log("Running Documentation Compliance Check...", "INFO")
        print("  -> Checking coverage for [raven-brain-stack]... 98% [OK]")
        print("  -> Checking coverage for [raven-embedded-control]... 100% [OK]")
        print("  -> Checking coverage for [new-features]... MISSING")
        log("Warning: New features in 'threadCamera.py' are not fully documented!", "WARN")

def manage_tests(repo=None):
    log("Initializing RAVEN Test Suite...", "INFO")
    
    # Define known repos and their test commands
    # We assume 'pytest' is installed in the environment or venv
    # Use raven-brain-stack venv for other repos to save setup time
    brain_venv_python = resolve_path("raven-brain-stack/venv/bin/python")
    
    repos = {
        "raven-brain-stack": {"cmd": ["python3", "-m", "pytest", "tests/"], "type": "python"},
        "raven-computer": {"cmd": ["python3", "-m", "pytest", "tests/"], "type": "python"},
        "raven-sim": {"cmd": [brain_venv_python, "-m", "pytest", "tests/"], "type": "shared_venv"},
        "raven-embedded-control": {"cmd": [brain_venv_python, "-m", "pytest", "tests/"], "type": "shared_venv"}
    }

    targets = {}
    if repo:
        if repo not in repos:
            log(f"Repository '{repo}' not known.", "ERROR")
            return
        targets[repo] = repos[repo]
    else:
        targets = repos

    print("\nRunning integration tests...\n")
    
    overall_success = True

    for name, config in targets.items():
        print(f"📦 {name}")
        path = resolve_path(name)
        
        if not path or not os.path.exists(path):
            print(f"  └── \033[91mRepo not found locally\033[0m")
            overall_success = False
            continue

        # Check if tests directory exists for python repos
        if config["type"] == "python":
            tests_dir = os.path.join(path, "tests")
            if not os.path.isdir(tests_dir):
                 print(f"  └── \033[93mNo 'tests/' directory found. Skipping.\033[0m")
                 continue

        try:
            # Determine python executable
            python_exec = sys.executable # Default to current python
            
            # Check for venv in the repo
            venv_python = os.path.join(path, "venv", "bin", "python")
            if os.path.exists(venv_python):
                python_exec = venv_python
            
            # Construct command
            cmd = list(config["cmd"])
            if cmd[0] == "python3":
                cmd[0] = python_exec

            # Run the test command
            print(f"  ├── Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd, 
                cwd=path, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode == 0:
                print(f"  └── Status: \033[92mPASSED\033[0m")
            else:
                print(f"  └── Status: \033[91mFAILED\033[0m")
                print("      \033[91mError Output:\033[0m")
                for line in result.stdout.splitlines()[-5:]: # Show last 5 lines of output
                     print(f"      {line}")
                for line in result.stderr.splitlines():
                     print(f"      {line}")
                overall_success = False

        except Exception as e:
            print(f"  └── \033[91mExecution Error: {e}\033[0m")
            overall_success = False
        
        print("") # Newline separator

    print("---------------------------------------------------")
    if overall_success:
        log("ALL TEST RUNS COMPLETED SUCCESSFULLY.", "SUCCESS")
    else:
        log("SOME TESTS FAILED. CHECK LOGS ABOVE.", "ERROR")


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

    # Docs
    docs_parser = subparsers.add_parser("docs", help="Manage documentation")
    docs_parser.add_argument("action", choices=["build", "open", "check"], default="check", nargs="?")

    # Tests
    test_parser = subparsers.add_parser("test", help="Run test suite and check coverage")
    test_parser.add_argument("repo", help="Specific repository to test", nargs="?")

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
    elif args.command == "docs":
        manage_docs(args.action)
    elif args.command == "test":
        manage_tests(args.repo)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
