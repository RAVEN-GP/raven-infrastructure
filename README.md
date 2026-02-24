# RAVEN - Infrastructure ("The Launchpad")

![Raven Infra](https://img.shields.io/badge/Component-Infrastructure-black) ![Status](https://img.shields.io/badge/Status-Beta-yellow)

The **Infrastructure** repository is the glue that holds the Raven system together. It provides the tools to deploy, configure, and launch the vehicle software stack with a single command.

## 🚀 The `raven` CLI
We provide a unified command-line tool to manage the car. No more remembering complex ROS launch commands!

### Installation
```bash
# From the root of this repo
./install.sh
```

### Usage
```bash
raven start [mode]   # Start the car stack (autonomous/manual/debug)
raven stop           # Stop all services
raven flash [--arch] # Compile and Flash firmware (arch: arduino/mbed)
raven status         # Check system health
raven deploy         # Pull latest code for all repos
raven pull           # Pull latest changes for all Raven repositories
raven push [-m msg]  # Add, commit, and push all Raven repositories
raven logs           # Tail logs from the brain
raven docs [action]  # Manage docs (check/build/open)
raven test [repo]    # Run test suite (all or specific repo)
```

## 🧪 Testing & Verification

We support both bulk testing and targeted repository testing to ensure 98%+ code coverage.

### Bulk Testing (All Repos)
Run the full CI/CD test suite across the entire stack:
```bash
raven test
```

### Targeted Testing
Test a specific repository in isolation:
```bash
raven test raven-brain-stack
raven test raven-embedded-control
```

## 📚 Documentation Management

Keep the knowledge base healthy with our smart doc tools:

- `raven docs check`: Verify that all new feature code is documented.
- `raven docs build`: Compile the Sphinx documentation locally.
- `raven docs open`: Serve the documentation on a local web server.

## 📂 Structure
- **`cli/`**: Python-based CLI tool source code.
- **`ansible/`**: Playbooks to provision the Raspberry Pi from scratch (install ROS, OpenCV, dependencies).
- **`systemd/`**: Service files to auto-start the Raven stack on boot.
- **`docker/`**: (Optional) Container definitions for isolated environments.

## ⚡ Quick Start (Manual)
To run the setup script on a fresh Raspberry Pi:
```bash
sudo ./scripts/setup_pi.sh
```
