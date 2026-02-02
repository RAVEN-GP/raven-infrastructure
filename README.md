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
raven start [mode]   # Start the car stack
raven stop           # Stop all services
raven status         # Check system health
raven deploy         # Pull latest code for all repos
raven logs           # Tail logs from the brain
```

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
