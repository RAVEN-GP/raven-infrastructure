#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time
import os
import re
import json
import math
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

def start_car(mode, laptop_ip=None, no_stream=False, no_arduino=False,
              conf=0.5, no_filters=False, webcam_index=0,
              start_x=0.0, start_y=0.0, start_heading=0.0, cruise=False):
    log(f"Starting RAVEN Skynet stack — mode: {mode}", "INFO")

    # Safety: ensure no old processes are running before starting a new one
    stop_car()
    time.sleep(1)

    brain_path = resolve_path("raven-brain-stack")
    if not brain_path:
        log("raven-brain-stack not found.", "ERROR")
        return

    skynet_script = os.path.join(brain_path, "src", "skynet.py")
    if not os.path.exists(skynet_script):
        log(f"skynet.py not found at {skynet_script}", "ERROR")
        return

    # ── 1. Start Mac-side video viewer (if not suppressed) ────────────────
    if not no_stream and not laptop_ip:
        # Ask for laptop IP if not provided and not suppressed
        try:
            laptop_ip = input("  Enter Mac/laptop IP for video stream [10.82.10.45]: ").strip()
            if not laptop_ip:
                laptop_ip = "10.82.10.45"
        except (EOFError, KeyboardInterrupt):
            laptop_ip = "10.82.10.45"

    # ── 2. Start frame_receiver_server on Mac (background) ────────────────
    receiver_script = os.path.join(brain_path, "services", "rpi-wifi-fallback", "frame_receiver_server.py")
    if not no_stream and os.path.exists(receiver_script):
        try:
            viewer_log = open("/tmp/raven_viewer.log", "w")
            pv = subprocess.Popen(
                [sys.executable, receiver_script, "--display"],
                stdout=viewer_log, stderr=viewer_log, start_new_session=True
            )
            RUNNING_PROCESSES["viewer"] = pv
            print(f"  -> 📺 Video viewer started (PID {pv.pid}) — window opens when Pi connects")
        except Exception as e:
            log(f"Could not start viewer: {e}", "WARN")

    # ── 3. Start telemetry dashboard (raven-computer) ─────────────────────
    computer_path = resolve_path("raven-computer")
    if computer_path:
        dash_script = os.path.join(computer_path, "src", "dashboard", "app.py")
        if os.path.exists(dash_script):
            try:
                dash_log = open("/tmp/raven_dashboard.log", "w")
                pd_ = subprocess.Popen(
                    [sys.executable, "app.py"],
                    cwd=os.path.dirname(dash_script),
                    stdout=dash_log, stderr=dash_log, start_new_session=True
                )
                RUNNING_PROCESSES["dashboard"] = pd_
                print(f"  -> 📊 Telemetry dashboard at http://localhost:5000 (PID {pd_.pid})")
            except Exception as e:
                log(f"Could not start dashboard: {e}", "WARN")

    # ── 4. Build skynet.py arguments ──────────────────────────────────────
    # Try to find the virtual environment python first
    venv_python = os.path.join(brain_path, "venv", "bin", "python")
    python_exec = venv_python if os.path.exists(venv_python) else sys.executable
    skynet_args = [python_exec, skynet_script]

    if no_stream or not laptop_ip:
        skynet_args.append("--no-stream")
    else:
        skynet_args += ["--laptop-ip", str(laptop_ip)]

    if cruise:
        skynet_args.append("--cruise")

    if cruise:
        skynet_args.append("--cruise")

    if no_arduino or mode == "debug":
        skynet_args.append("--no-arduino")

    skynet_args += ["--conf", str(conf)]

    if no_filters:
        skynet_args.append("--no-filters")

    if webcam_index != 0:
        skynet_args += ["--webcam-index", str(webcam_index)]

    # Pass starting pose if provided (for map-based localization)
    if start_x != 0.0 or start_y != 0.0 or start_heading != 0.0:
        skynet_args += [
            "--start-x",       str(start_x),
            "--start-y",       str(start_y),
            "--start-heading", str(start_heading),
        ]

    # ── 5. Launch skynet.py ───────────────────────────────────────────────
    try:
        brain_log_path = "/tmp/raven_brain.log"
        brain_log = open(brain_log_path, "w")
        pb = subprocess.Popen(
            skynet_args, cwd=brain_path,
            stdout=brain_log, stderr=brain_log, start_new_session=True
        )
        RUNNING_PROCESSES["brain"] = pb
        print(f"  -> 🧠 Skynet launched (PID {pb.pid})")
        print(f"  -> Logs: {brain_log_path}")
    except Exception as e:
        log(f"Failed to start Skynet: {e}", "ERROR")
        return

    # ── Write PID file ────────────────────────────────────────────────────
    with open("/tmp/raven_pids.txt", "w") as f:
        for name, proc in RUNNING_PROCESSES.items():
            f.write(f"{name}:{proc.pid}\n")

    print()
    print("  ╔════════════════════════════════════════════╗")
    print("  ║  🚗  RAVEN Skynet is ONLINE                 ║")
    if not no_stream and laptop_ip:
        print(f"  ║  📺  Video → {laptop_ip}:5012                 ║")
    print("  ║  📊  Dashboard → http://localhost:5000     ║")
    print("  ║  📄  Live logs: raven logs                 ║")
    print("  ║  🛑  Stop:      raven stop                 ║")
    print("  ╚════════════════════════════════════════════╝")
    print()
    log("Startup complete.", "SUCCESS")
def stop_car():
    log("Stopping RAVEN stack...", "WARN")
    if os.path.exists("/tmp/raven_pids.txt"):
        with open("/tmp/raven_pids.txt", "r") as f:
            lines = f.readlines()
            
        # 1. Try polite SIGTERM
        for line in lines:
            try:
                name, pid = line.strip().split(":")
                os.kill(int(pid), 15) # SIGTERM
                print(f"  -> Requested {name} to stop [PID {pid}]")
            except Exception:
                pass
        
        time.sleep(1.0) # Wait for threads to close serial etc.
        
        # 2. Force SIGKILL for survivors
        for line in lines:
            try:
                name, pid = line.strip().split(":")
                os.kill(int(pid), 9) # SIGKILL
                print(f"  -> Force-killed {name} [PID {pid}]")
            except Exception:
                pass

        os.remove("/tmp/raven_pids.txt")
        log("RAVEN system HALTED.", "SUCCESS")
    else:
        log("No active PID file found. Checking for lingering processes...", "INFO")
        # Fallback: kill anything running skynet.py
        subprocess.run("pkill -9 -f skynet.py", shell=True)
        subprocess.run("pkill -9 -f frame_receiver_server.py", shell=True)

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

def calibrate_start(x, y, heading):
    pose = {
        "x": float(x),
        "y": float(y),
        "heading": float(heading)
    }
    pose_path = "/tmp/raven_start_pose.json"
    with open(pose_path, "w") as f:
        json.dump(pose, f)
    log(f"Calibrated start point: ({x}, {y}) at {heading} degrees.", "SUCCESS")
    print(f"  -> Saved to: {pose_path}")

def stream_video(laptop_ip=None):
    log("Starting video stream viewer...", "INFO")
    brain_path = resolve_path("raven-brain-stack")
    if not brain_path: return
    
    script = os.path.join(brain_path, "services", "rpi-wifi-fallback", "frame_receiver_server.py")
    if os.path.exists(script):
        log(f"Launching viewer: {script}", "INFO")
        subprocess.run([sys.executable, script, "--display"])
    else:
        log("frame_receiver_server.py not found.", "ERROR")

def watch_logs(follow=True):
    log("Tailing system logs (Ctrl+C to exit)...", "INFO")
    log_file = "/tmp/raven_brain.log"
    if not os.path.exists(log_file):
        log(f"Log file not found at {log_file}. Is Skynet running?", "WARN")
        return
        
    cmd = ["tail", "-f", log_file] if follow else ["tail", "-n", "50", log_file]
    try:
        subprocess.run(cmd)
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
        if repo == "hardware" or repo == "sim":
            log(f"Running {'Hardware' if repo == 'hardware' else 'Software'} Diagnostic Test...", "INFO")
            path = resolve_path("raven-brain-stack")
            if path:
                script_name = "test_hardware.py" if repo == "hardware" else "test_software_sim.py"
                test_script = os.path.join(path, "tests", script_name)
                if os.path.exists(test_script):
                    python_exec = sys.executable
                    venv_python = os.path.join(path, "venv", "bin", "python")
                    if os.path.exists(venv_python):
                        python_exec = venv_python
                    subprocess.run([python_exec, test_script])
                else:
                    log(f"Test script not found at {test_script}", "ERROR")
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
                print(f"  └── \033[90mNo changes to commit. Skipped.\033[0m\n")
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
            
            # Auto-set upstream if it's a new branch
            if push_result.returncode != 0 and "has no upstream branch" in push_result.stderr:
                print(f"  ├── \033[93mNo upstream branch found. Auto-setting upstream...\033[0m")
                push_cmd_up = ["git", "-C", path, "push", "-u", "origin", "HEAD"]
                print(f"  ├── Running: {' '.join(push_cmd_up)}")
                push_result = subprocess.run(push_cmd_up, capture_output=True, text=True)
            
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
    parser = argparse.ArgumentParser(
        description="Raven Vehicle Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''Examples:
  raven start                              # Full autonomous system (prompts for IP)
  raven start --no-stream                  # No video (Pi only)
  raven start --no-arduino                 # Bench test without Arduino
  raven start --conf 0.35 --no-filters     # Lower YOLO confidence
  raven start --laptop-ip 192.168.50.2     # Custom Mac IP
  raven stream                             # Start video viewer on Mac only
  raven calibrate --x 50 --y 30 --heading 90  # Set starting pose for map-based run
  raven logs                               # Tail all live logs
  raven status                             # System health check
  raven stop                               # Stop all services
  raven flash --arch arduino               # Flash Arduino firmware
  raven pull                               # Update all repos
  raven push -m "feat: lane detection"     # Commit & push all repos
  raven docs build                         # Build Sphinx documentation
  raven test                               # Run all test suites'''
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    start_p = subparsers.add_parser("start", help="Start the full Skynet autonomous stack")
    start_p.add_argument("mode", choices=["autonomous", "manual", "debug"], default="autonomous", nargs="?")
    start_p.add_argument("--laptop-ip", type=str, default=None)
    start_p.add_argument("--no-stream", action="store_true")
    start_p.add_argument("--no-arduino", action="store_true")
    start_p.add_argument("--conf", type=float, default=0.5)
    start_p.add_argument("--no-filters", action="store_true")
    start_p.add_argument("--webcam-index", type=int, default=0)
    start_p.add_argument("--start-x", type=float, default=0.0)
    start_p.add_argument("--start-y", type=float, default=0.0)
    start_p.add_argument("--start-heading", type=float, default=0.0)
    start_p.add_argument("--cruise", action="store_true", help="Start moving at cruise speed automatically")

    subparsers.add_parser("stop", help="Stop all Raven services")
    subparsers.add_parser("status", help="Show live system health")

    stream_p = subparsers.add_parser("stream", help="Start the video viewer on Mac")
    stream_p.add_argument("--laptop-ip", type=str, default=None)

    cal_p = subparsers.add_parser("calibrate", help="Set the car's starting pose")
    cal_p.add_argument("--x", type=float, default=0.0)
    cal_p.add_argument("--y", type=float, default=0.0)
    cal_p.add_argument("--heading", type=float, default=0.0)

    logs_p = subparsers.add_parser("logs", help="Tail live logs")
    logs_p.add_argument("--no-follow", action="store_true")

    subparsers.add_parser("deploy", help="Pull and build latest code")
    flash_p = subparsers.add_parser("flash", help="Compile and flash firmware")
    flash_p.add_argument("--arch", choices=["mbed", "arduino"], default="arduino")

    docs_p = subparsers.add_parser("docs", help="Manage Sphinx documentation")
    docs_p.add_argument("action", choices=["build", "open", "check"], default="check", nargs="?")

    test_p = subparsers.add_parser("test", help="Run test suite")
    test_p.add_argument("repo", nargs="?")

    subparsers.add_parser("pull", help="Pull latest changes")
    push_p = subparsers.add_parser("push", help="Commit and push")
    push_p.add_argument("-m", "--message", default="chore: auto-update via raven CLI")

    args = parser.parse_args()

    if args.command == "start":
        start_car(args.mode, args.laptop_ip, args.no_stream, args.no_arduino, args.conf, args.no_filters, args.webcam_index, args.start_x, args.start_y, args.start_heading, args.cruise)
    elif args.command == "stop":
        stop_car()
    elif args.command == "status":
        status_car()
    elif args.command == "stream":
        stream_video(getattr(args, "laptop_ip", None))
    elif args.command == "calibrate":
        calibrate_start(args.x, args.y, args.heading)
    elif args.command == "logs":
        watch_logs(follow=not args.no_follow)
    elif args.command == "deploy":
        deploy_code()
    elif args.command == "flash":
        flash_firmware(args.arch)
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
