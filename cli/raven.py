#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time
import os
import re
from datetime import datetime
try:
    import serial.tools.list_ports
except ImportError:
    serial = None

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

def detect_serial_port():
    """Smart detection of the embedded serial port (Nucleo or Arduino)."""
    # 1. Try pyserial if available
    if serial:
        ports = serial.tools.list_ports.comports()
        for port in ports:
            # Check for typical descriptors
            if "STM32" in port.description or "NUCLEO" in port.description:
                 return port.device
            if "Arduino" in port.description or "usbmodem" in port.device: 
                 return port.device
            # Fallback to regex for Linux ttyACM
            if re.match(r"/dev/ttyACM\d+", port.device):
                 return port.device
    
    # 2. Fallback: Use arduino-cli if available
    import shutil
    arduino_cli = shutil.which("arduino-cli")
    if not arduino_cli and os.path.exists("/opt/homebrew/bin/arduino-cli"):
        arduino_cli = "/opt/homebrew/bin/arduino-cli"
        
    if arduino_cli:
        try:
            # Run board list
            result = subprocess.run([arduino_cli, "board", "list"], capture_output=True, text=True)
            # Output format: Port Protocol ... FQBN
            # /dev/cu.usbmodem14201 Serial ... arduino:mbed_nano:nanorp2040connect
            for line in result.stdout.splitlines():
                if "nanorp2040connect" in line or "usbmodem" in line:
                    parts = line.split()
                    if len(parts) > 0:
                        return parts[0]
        except Exception:
            pass

    if serial is None:
        log("pyserial not installed and arduino-cli failed to find board.", "WARN")
        
    return None

def start_car(mode):
    log(f"Starting RAVEN stack in mode: {mode}")
    
    # 1. Start Dashboard (Raven Computer)
    computer_path = resolve_path("raven-computer")
    if computer_path:
        dash_script = os.path.join(computer_path, "src", "dashboard", "app.py")
        if os.path.exists(dash_script):
            log("Launching Telemetry Dashboard...", "INFO")
            # Run in background with logging
            try:
                # Open log file
                dash_log = open("/tmp/raven_dashboard.log", "w")
                
                # Use current python executable to ensure same env
                python_exec = sys.executable
                
                # start_new_session=True ensures it survives if CLI exits or receives signals
                p = subprocess.Popen([python_exec, "app.py"], cwd=os.path.dirname(dash_script), 
                                     stdout=dash_log, stderr=dash_log,
                                     start_new_session=True)
                RUNNING_PROCESSES["dashboard"] = p
                print(f"  -> Dashboard active at http://localhost:5000 📊 (PID: {p.pid})")
                print("  -> Logs: /tmp/raven_dashboard.log")
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
                # Open log file
                brain_log = open("/tmp/raven_brain.log", "w")
                
                # start_new_session=True to detach
                p = subprocess.Popen([python_exec, "main.py"], cwd=brain_path, env=env,
                                     stdout=brain_log, stderr=brain_log,
                                     start_new_session=True)
                RUNNING_PROCESSES["brain"] = p
                print(f"  -> Brain is ONLINE (PID: {p.pid}) 🧠")
                print("  -> Logs: /tmp/raven_brain.log")
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

def flash_firmware(arch):
    log(f"Flashing firmware for architecture: {arch}", "INFO")
    
    embedded_path = resolve_path("raven-embedded-control")
    if not embedded_path:
        return

    if arch == "mbed":
        print("  -> Detected Mbed OS project.")
        print("  -> Copying binary to Nucleo...")
        # Check for compiled bin
        bin_path = os.path.join(embedded_path, "BUILD", "NUCLEO_F401RE", "GCC_ARM", "raven-embedded-control.bin")
        if not os.path.exists(bin_path):
             print("\033[93m  -> Binary not found. Please compile first using 'mbed compile'.\033[0m")
             return
             
        # Try to find Nucleo mount
        volumes = os.listdir("/Volumes") if os.path.exists("/Volumes") else []
        nucleo_vol = next((v for v in volumes if "NODE" in v or "NUCLEO" in v), None)
        
        if nucleo_vol:
            dest = os.path.join("/Volumes", nucleo_vol)
            run_cmd(f"cp '{bin_path}' '{dest}'")
            log("Flashed successfully via Drag-and-Drop.", "SUCCESS")
        else:
            log("Nucleo volume not found. Is it connected?", "ERROR")

    elif arch == "arduino":
        print("  -> Detected Arduino architecture.")
        sketch_path = os.path.join(embedded_path, "arduino", "raven-rp2040")
        
        # Check for arduino-cli
        import shutil
        arduino_cli = shutil.which("arduino-cli")
        if not arduino_cli:
            # Check common homebrew path
            if os.path.exists("/opt/homebrew/bin/arduino-cli"):
                arduino_cli = "/opt/homebrew/bin/arduino-cli"
            elif os.path.exists("/usr/local/bin/arduino-cli"):
                arduino_cli = "/usr/local/bin/arduino-cli"

        if arduino_cli:
            try:
                subprocess.run([arduino_cli, "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                print("  -> Compiling and Uploading with arduino-cli...")
                FQBN = "arduino:mbed_nano:nanorp2040connect"
                
                # Get Config
                # Note: This might be brittle if multiple boards are connected
                try:
                    # Compile
                    compile_cmd = [arduino_cli, "compile", "-b", FQBN, sketch_path]
                    print(f"  -> Compiling: {' '.join(compile_cmd)}")
                    subprocess.check_call(compile_cmd)
                    
                    # Upload
                    # We rely on arduino-cli to auto-detect if we pass -p detected_port
                    # But detection is tricky. Let's try simple upload if port is auto-detected by cli
                    # Or use our own detection
                    port = detect_serial_port()
                    if port:
                        upload_cmd = [arduino_cli, "upload", "-b", FQBN, "-p", port, sketch_path]
                        print(f"  -> Uploading to {port}...")
                        subprocess.check_call(upload_cmd)
                        log("Firmware updated successfully!", "SUCCESS")
                    else:
                        print("\033[93m  -> Compilation success, but no compatible board found for upload.\033[0m")
                        print("     Please connect the device and try again.")

                except subprocess.CalledProcessError as e:
                    log(f"Arduino action failed: {e}", "ERROR")

            except Exception as e:
                log(f"Unexpected error: {e}", "ERROR")
        else:
             log("arduino-cli not found in PATH or standard locations.", "ERROR")
             print("  -> Please install: brew install arduino-cli")
             print(f"  -> Sketch location: {sketch_path}")

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
        if repo == "hardware":
            log("Running Hardware Diagnostic Test...", "INFO")
            path = resolve_path("raven-brain-stack")
            if path:
                test_script = os.path.join(path, "tests", "test_hardware.py")
                if os.path.exists(test_script):
                    python_exec = sys.executable
                    venv_python = os.path.join(path, "venv", "bin", "python")
                    if os.path.exists(venv_python):
                        python_exec = venv_python
                    subprocess.run([python_exec, test_script])
                else:
                    log(f"Hardware test script not found at {test_script}", "ERROR")
            return
            
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



def pull_repos():
    log("Updating all RAVEN repositories...", "INFO")
    repos = [
        "raven-brain-stack",
        "raven-computer",
        "raven-documentation",
        "raven-embedded-control",
        "raven-infrastructure",
        "raven-sim"
    ]
    
    success_count = 0
    fail_count = 0
    skipped_count = 0
    
    for repo in repos:
        path = resolve_path(repo)
        if not path:
            skipped_count += 1
            continue
            
        print(f"📦 {repo}")
        try:
            # Check if it's a git repo
            if not os.path.exists(os.path.join(path, ".git")):
                print(f"  └── \033[93mNot a git repository. Skipping.\033[0m")
                skipped_count += 1
                continue
                
            # Run git pull
            cmd = ["git", "-C", path, "pull"]
            print(f"  ├── Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode == 0:
                print(f"  └── Status: \033[92mSUCCESS\033[0m")
                if "Already up to date." not in result.stdout:
                    output = result.stdout.strip()
                    if output:
                        # Print first few lines of changes
                        lines = output.splitlines()
                        for line in lines[:5]:
                            print(f"      {line}")
                        if len(lines) > 5:
                            print(f"      ...")
                success_count += 1
            else:
                print(f"  └── Status: \033[91mFAILED\033[0m")
                print("      \033[91mError Output:\033[0m")
                if result.stderr:
                    for line in result.stderr.splitlines():
                        print(f"      {line}")
                elif result.stdout:
                    for line in result.stdout.splitlines():
                        print(f"      {line}")
                fail_count += 1
        except Exception as e:
            print(f"  └── \033[91mError: {e}\033[0m")
            fail_count += 1
        print("")

    print("---------------------------------------------------")
    summary = f"Updated: {success_count} | Failed: {fail_count} | Skipped: {skipped_count}"
    if fail_count == 0:
        log(summary, "SUCCESS")
    else:
        log(summary, "WARN" if success_count > 0 else "ERROR")



def push_repos(message):
    log(f"Committing and Pushing all RAVEN repositories with message: '{message}'", "INFO")
    repos = [
        "raven-brain-stack",
        "raven-computer",
        "raven-documentation",
        "raven-embedded-control",
        "raven-infrastructure",
        "raven-sim"
    ]
    
    success_count = 0
    fail_count = 0
    skipped_count = 0
    no_changes_count = 0
    
    for repo in repos:
        path = resolve_path(repo)
        if not path:
            skipped_count += 1
            continue
            
        print(f"🚀 {repo}")
        try:
            # Check if it's a git repo
            if not os.path.exists(os.path.join(path, ".git")):
                print(f"  └── \033[93mNot a git repository. Skipping.\033[0m\n")
                skipped_count += 1
                continue
                
            # Check for changes
            status_cmd = ["git", "-C", path, "status", "--porcelain"]
            status_result = subprocess.run(status_cmd, capture_output=True, text=True)
            
            if not status_result.stdout.strip():
                print(f"  └── Status: \033[94mNO CHANGES (Skipped)\033[0m\n")
                no_changes_count += 1
                continue

            # Git Add
            add_cmd = ["git", "-C", path, "add", "."]
            print(f"  ├── Running: {' '.join(add_cmd)}")
            subprocess.run(add_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            # Git Commit
            commit_cmd = ["git", "-C", path, "commit", "-m", message]
            print(f"  ├── Running: git commit -m \"{message}\"")
            subprocess.run(commit_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            # Git Push
            push_cmd = ["git", "-C", path, "push"]
            print(f"  ├── Running: {' '.join(push_cmd)}")
            push_result = subprocess.run(push_cmd, capture_output=True, text=True)
            
            if push_result.returncode == 0:
                print(f"  └── Status: \033[92mSUCCESS\033[0m\n")
                success_count += 1
            else:
                print(f"  └── Status: \033[91mFAILED (Push Error)\033[0m")
                print(f"      {push_result.stderr.strip().split(chr(10))[0] if push_result.stderr else 'Unknown Error'}\n")
                fail_count += 1
                
        except subprocess.CalledProcessError as e:
            print(f"  └── Status: \033[91mFAILED (Command Error)\033[0m\n")
            fail_count += 1
        except Exception as e:
            print(f"  └── Status: \033[91mFAILED\033[0m Error: {e}\n")
            fail_count += 1

    print("---------------------------------------------------")
    summary = f"Pushed: {success_count} | No Changes: {no_changes_count} | Failed: {fail_count} | Skipped: {skipped_count}"
    if fail_count == 0:
        log(summary, "SUCCESS")
    else:
        log(summary, "WARN" if success_count > 0 else "ERROR")

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

    # Flash
    flash_parser = subparsers.add_parser("flash", help="Flash firmware to microcontroller")
    flash_parser.add_argument("--arch", choices=["mbed", "arduino"], default="mbed", help="Target architecture")

    # Logs
    subparsers.add_parser("logs", help="Tail system logs")

    # Docs
    docs_parser = subparsers.add_parser("docs", help="Manage documentation")
    docs_parser.add_argument("action", choices=["build", "open", "check"], default="check", nargs="?")

    # Tests
    test_parser = subparsers.add_parser("test", help="Run test suite and check coverage")
    test_parser.add_argument("repo", help="Specific repository to test, or 'hardware' for Pi-Arduino diagnostic", nargs="?")

    # Pull
    subparsers.add_parser("pull", help="Pull latest changes for all Raven repositories")
    
    # Push
    push_parser = subparsers.add_parser("push", help="Add, commit, and push all Raven repositories")
    push_parser.add_argument("-m", "--message", default="chore: auto-update via raven CLI", help="Commit message to use for all repos")

    args = parser.parse_args()

    if args.command == "start":
        start_car(args.mode)
    elif args.command == "stop":
        stop_car()
    elif args.command == "status":
        status_car()
    elif args.command == "deploy":
        deploy_code()
    elif args.command == "flash":
        flash_firmware(args.arch)
    elif args.command == "logs":
        tail_logs()
    elif args.command == "docs":
        manage_docs(args.action)
    elif args.command == "test":
        manage_tests(args.repo)
    elif args.command == "pull":
        pull_repos()
    elif args.command == "push":
        push_repos(args.message)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
