# COCOHOSPITALS LIS — Analyzer Connector

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%2832--bit%20%2F%2064--bit%29-brightgreen.svg)](https://microsoft.com/windows)
[![Protocol](https://img.shields.io/badge/protocol-ASTM%20E1381%20%2F%20E1394-red.svg)](#astm-protocol-support)
[![UI Framework](https://img.shields.io/badge/GUI-PyQt5%20%2F%20PySide6-informational.svg)](https://www.riverbankcomputing.com/software/pyqt/)

An open-source, enterprise-grade laboratory instrument bridge and interface connector. Built for diagnostic centers, hospitals, and clinical pathology laboratories, this software connects to automated medical analyzers (such as **ERBA**, **MultiXL**, etc.) over **ASTM TCP/IP**, validates and parses clinical test frames in real time, and automatically forwards structured patient results to hospital LIS (Laboratory Information System) REST API webhooks.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Quick Start: Running from Source](#quick-start-running-from-source)
  - [1. Prerequisites](#1-prerequisites)
  - [2. Clone the Repository](#2-clone-the-repository)
  - [3. Set Up Virtual Environment](#3-set-up-virtual-environment)
  - [4. Install Dependencies](#4-install-dependencies)
  - [5. Run the Desktop Application](#5-run-the-desktop-application)
  - [6. Run the Standalone CLI Listener](#6-run-the-standalone-cli-listener)
  - [7. Test with Simulated Analyzer](#7-test-with-simulated-analyzer)
- [Building the Universal Windows Installer](#building-the-universal-windows-installer)
  - [One-Click Build Command](#one-click-build-command)
  - [How the Build Works](#how-the-build-works)
- [Installation & Deployment](#installation--deployment)
- [Configuration Guide](#configuration-guide)
- [24/7 Resilience & Reconnection Logic](#247-resilience--reconnection-logic)
- [ASTM Protocol Specification](#astm-protocol-specification)
- [Directory Structure](#directory-structure)
- [Logging & Diagnostics](#logging--diagnostics)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Clinical laboratory analyzers typically transmit diagnostic data over serial RS232 or TCP/IP connections using ASTM standard protocols (ASTM E1381 Physical/Data Link and ASTM E1394 Message Content).

The **COCOHOSPITALS LIS Analyzer Connector** serves as a robust middleware host:
1. **TCP/IP Server**: Listens on a dedicated local port (e.g., `5002`) for analyzer connections.
2. **ASTM Protocol Engine**: Handles low-level transmission control characters (`<ENQ>`, `<ACK>`, `<NAK>`, `<STX>`, `<ETX>`, `<EOT>`) and validates frame checksums.
3. **Data Parser**: Extracts Patient Demographics (P-records), Order information (O-records), and Test Results (R-records with parameters, values, units, reference ranges, and abnormal flags).
4. **Persistent Logging & Audit**: Stores raw frames and parsed JSON records on local disk before transmission.
5. **LIS Webhook Delivery**: Dispatches HTTP/HTTPS POST payloads directly to hospital LIS servers with automatic exponential-backoff retries.

---

## Key Features

- **Universal Windows Architecture**: Runs natively on **32-bit Windows (x86)** and seamlessly on **64-bit Windows (x64 / AMD64)** via WOW64.
- **Zero-Touch Automatic Startup**: Configured via Windows Scheduled Task (`TASK_TRIGGER_LOGON`) and Registry `Run` keys with highest privileges to run automatically on machine boot without requiring user interaction.
- **Auto-Connect on Boot**: Automatically initializes stored settings and opens the TCP listener socket immediately upon application launch.
- **24/7 Persistent Operation**:
  - Socket resets and disconnects trigger auto-reconnection with exponential backoff (2s up to 60s max).
  - Outbound LIS API outages retry automatically with backoff to prevent packet loss.
  - Subprocess engine crashes are detected by the supervisor UI and restarted automatically.
- **Single-Instance Protection**: Enforces a named system Mutex (`Global\` and `Local\`) to prevent multiple instances from conflicting over ports or duplicating records.
- **Port Exclusivity (`SO_EXCLUSIVEADDRUSE`)**: Prevents zombie processes or unauthorized local applications from hijacking the analyzer port.
- **Modern Compact UI**: Clean, space-efficient medical software interface with real-time connection status indicators, 2-row configuration layout, and live activity logging.
- **Non-Admin `%LOCALAPPDATA%` Storage**: Saves logs, messages, and configurations in user application data, eliminating Windows UAC file permission errors.

---

## System Architecture

```text
┌─────────────────────────────────┐
│       Laboratory Analyzer       │
│    (ERBA XL, Chem 5X, etc.)     │
└────────────────┬────────────────┘
                 │
                 │ ASTM E1381 TCP/IP (Port 5002)
                 ▼
┌───────────────────────────────────────────────────────────────┐
│             COCOHOSPITALS LIS Analyzer Connector              │
│                                                               │
│   ┌─────────────────────────┐       ┌──────────────────────┐  │
│   │    Desktop GUI (PyQt)   │◀─────▶│  ASTM TCP Listener   │  │
│   │ • Live Activity Log     │ (IPC) │ • Socket Manager     │  │
│   │ • Connection Status     │       │ • Checksum Validator │  │
│   │ • Compact Configuration │       │ • JSON Formatter     │  │
│   │ • Process Supervisor    │       │ • 24/7 Auto-Retry    │  │
│   └─────────────────────────┘       └──────────┬───────────┘  │
└────────────────────────────────────────────────│──────────────┘
                                                 │
                                                 │ HTTPS POST (JSON)
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │      COCOHOSPITALS LIS      │
                                  │    (Hospital Webhook API)   │
                                  └─────────────────────────────┘
```

---

## Quick Start: Running from Source

Follow these steps to run the application locally on your development machine.

### 1. Prerequisites

- **Python**: Python 3.10 or 3.11 (32-bit or 64-bit).
- **Git**: Installed and available in PATH.
- **Operating System**: Windows 7/8/10/11 or Windows Server.

### 2. Clone the Repository

```bash
git clone https://github.com/hariompatel61/analyser-listener.git
cd analyser-listener
```

### 3. Set Up Virtual Environment

Open PowerShell or Command Prompt:

```powershell
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# In PowerShell:
.\venv\Scripts\Activate.ps1
# Or in Command Prompt (cmd.exe):
.\venv\Scripts\activate.bat
```

### 4. Install Dependencies

Install all core dependencies from `requirements.txt`:

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Run the Desktop Application

Launch the full graphical desktop application (UI with background process supervisor):

```powershell
python desktop-app\app.py
```

The GUI will open in a compact 940×500 px window, initialize your local configuration, and start listening on the configured TCP port.

### 6. Run the Standalone CLI Listener

If you prefer to run only the background ASTM TCP listener engine without the GUI:

```powershell
python py-script\erba_listener.py
```

### 7. Test with Simulated Analyzer

To test the application without physical analyzer hardware:

1. Keep the application running (listening on port `5002`).
2. Open a second terminal window and run:
   ```powershell
   python desktop-app\test_sender.py
   ```
3. The script sends valid ASTM-formatted sample records (`<ENQ>`, Frame records, `<EOT>`).
4. Look at the **Activity Log** in the GUI to verify that the message is received, parsed into JSON, and posted to the LIS webhook.

---

## Building the Universal Windows Installer

The project contains an automated build script (`build_universal_32bit.ps1`) that packages the entire application into a single production installer: `COCOHOSPITALS-LIS.exe`.

### Build Prerequisites

1. **Python 3.11 (32-bit x86)**:
   ```powershell
   winget install --id Python.Python.3.11 --architecture x86
   ```
   Installed at `%LOCALAPPDATA%\Programs\Python\Python311-32\python.exe`.
2. **Inno Setup 6**:
   ```powershell
   winget install --id JRSoftware.InnoSetup
   ```

### One-Click Build Command

Run the automated build script from the root repository directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_universal_32bit.ps1
```

### How the Build Works

1. **Builds `erba_listener.exe`**: Compiles `py-script/erba_listener.py` into a 32-bit standalone binary in `dist-listener/`.
2. **Builds GUI Application**: Compiles `desktop-app/app.py` with PyInstaller into `desktop-app/dist/COCOHOSPITALS-LIS-Analyzer-Connector/`.
3. **Bundles Assets**: Copies icons (`logo.ico`), configurations, and device lists into the bundle.
4. **Compiles Installer**: Invokes Inno Setup (`ISCC.exe`) with `COCOHOSPITALS_LIS_Analyzer_Connector.iss`.
5. **Architecture Verification**: Automatically verifies the PE headers of all output binaries to confirm pure 32-bit x86 compatibility (`IMAGE_FILE_MACHINE_I386` / `0x014C`).
6. **Output**: The ready-to-distribute installer is saved at:
   ```text
   installer-output\COCOHOSPITALS-LIS.exe
   ```

---

## Installation & Deployment

For end-user clinical deployment:

1. Copy **`installer-output\COCOHOSPITALS-LIS.exe`** to the target Windows machine.
2. Right-click and choose **Run as Administrator**.
3. Installation defaults:
   - **32-bit Windows**: `C:\Program Files\COCOHOSPITALS\LIS Analyzer Connector`
   - **64-bit Windows**: `C:\Program Files (x86)\COCOHOSPITALS\LIS Analyzer Connector`
4. The installer automatically registers:
   - Windows Scheduled Task for boot logon startup.
   - Registry Run key for fallback auto-start.
   - Desktop and Start Menu shortcuts.
5. Launches automatically upon completion.

---

## Configuration Guide

The connector interface exposes four primary parameters:

| Field | Description | Default Example |
| :--- | :--- | :--- |
| **Analyzer IP** | IP address assigned to the physical instrument | `10.10.11.2` |
| **TCP Port** | Port the connector binds to for incoming data | `5002` |
| **Source Device** | Analyzer model / identifier sent in the payload | `ERRBA7689` / `ERBA 360` |
| **API Endpoint** | Full HTTPS webhook URL of your LIS server | `https://rims.admin.cocohospitals.com/api/v1/hospital/rims/analyzer-webhook` |

### To update configuration:
- Click **EDIT CONFIGURATION** (the active listener socket is safely closed).
- Modify the values.
- Click **TEST API** to test connectivity to your hospital endpoint.
- Click **SAVE CONFIGURATION** (the settings persist to `%LOCALAPPDATA%` and the listener starts immediately).

---

## 24/7 Resilience & Reconnection Logic

Designed for mission-critical hospital environments that operate continuously:

```text
[Windows Boot / Login]
         │
         ▼
[Auto-Start via Scheduled Task]
         │
         ▼
[Single-Instance Mutex Check] ────(Already running)────▶ [Focus existing & Exit]
         │ (First instance)
         ▼
[Load Config from %LOCALAPPDATA%]
         │
         ▼
[Start TCP Listener (Port 5002)]
         │
         ├──▶ Port Busy / Network Not Ready ──▶ Exponential Backoff (2s → 60s) ──▶ Retry
         │
         ▼
[Status: CONNECTED (Green)]
         │
         ├──▶ Remote Connection Drops ──▶ Graceful cleanup ──▶ Keep listening
         ├──▶ Subprocess Crashes ──▶ Automatic restart with exponential backoff
         └──▶ LIS Webhook Down ──▶ Data saved locally ──▶ Retry delivery
```

---

## ASTM Protocol Specification

The connector adheres strictly to ASTM E1381 framing:

- **Handshake Phase**:
  - Analyzer sends `<ENQ>` (`0x05`).
  - Connector replies `<ACK>` (`0x06`).
- **Data Transmission Phase**:
  - Analyzer sends `<STX> [Frame#] [Data] [ETB/ETX] [Checksum] <CR><LF>`.
  - Connector validates the modulo-256 checksum and replies `<ACK>`.
- **Termination Phase**:
  - Analyzer sends `<EOT>` (`0x04`).
  - Connector finalizes the message, converts records (`H`, `P`, `O`, `R`, `L`) into structured JSON, saves to local disk, and dispatches to the webhook.

---

## Directory Structure

```text
analyser-listener/
├── build_universal_32bit.ps1       # Automated universal 32-bit build pipeline
├── COCOHOSPITALS_LIS_Analyzer_Connector.iss # Inno Setup installer script
├── LICENSE                         # MIT License
├── logo.ico                        # Application & installer icon
├── README.md                       # Documentation & instructions
├── requirements.txt                # Python package dependencies
│
├── desktop-app/                    # Desktop GUI (PyQt5 / PySide6)
│   ├── app.py                      # Main compact GUI & process supervisor
│   ├── erba_connector_config.json  # Default fallback configuration
│   ├── source_devices.json         # Supported instrument dropdown list
│   └── test_sender.py              # Mock ASTM sender for verification/QA
│
├── py-script/                      # Core ASTM Engine
│   ├── erba_listener.py            # High-performance TCP ASTM listener & API client
│   └── erba_parser.py              # ASTM E1381/E1394 frame & record parser
│
└── installer-output/               # Output distribution directory
    └── COCOHOSPITALS-LIS.exe       # Production-ready universal installer
```

---

## Logging & Diagnostics

Runtime files are located in `%LOCALAPPDATA%\COCOHOSPITALS\LIS Analyzer Connector`:

- **GUI Logs**: `erba_connector.log`
- **Listener Logs**: `logs/erba_listener.log`
- **Raw Received ASTM Frames**: `logs/messages/erba_<timestamp>.txt`
- **Parsed JSON Records**: `logs/json/erba_<timestamp>.json`
- **Active Configuration**: `erba_connector_config.json`

To view live logs in PowerShell:
```powershell
Get-Content "$env:LOCALAPPDATA\COCOHOSPITALS\LIS Analyzer Connector\logs\erba_listener.log" -Wait -Tail 30
```

---

## Contributing

Contributions, bug reports, and pull requests are welcome!

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/analyzer-support`).
3. Commit your changes (`git commit -m "Add support for new analyzer model"`).
4. Push to your branch (`git push origin feature/analyzer-support`).
5. Open a Pull Request.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

*COCOHOSPITALS LIS Analyzer Connector is built for reliable healthcare diagnostic automation.*
