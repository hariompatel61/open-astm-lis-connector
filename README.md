# COCOHOSPITALS LIS — Analyzer Connector

A robust, enterprise-grade laboratory instrument integration software designed for hospitals and diagnostic centers. It interfaces with medical laboratory analyzers (such as **ERBA**, **MultiXL**, etc.) over **ASTM TCP/IP** and automatically transmits structured lab results to the **COCOHOSPITALS LIS (Laboratory Information System)** REST API.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [System Requirements](#system-requirements)
- [Installation & Deployment](#installation--deployment)
- [Configuration Guide](#configuration-guide)
- [Continuous 24/7 Operation & Reconnection](#continuous-247-operation--reconnection)
- [Project Structure](#project-structure)
- [Developer Guide & Build Instructions](#developer-guide--build-instructions)
- [File & Log Locations](#file--log-locations)
- [Troubleshooting & Diagnostics](#troubleshooting--diagnostics)

---

## Overview

In diagnostic laboratories, instruments generate test results and transmit them via standard medical protocols (ASTM E1381 / E1394). The **COCOHOSPITALS LIS Analyzer Connector** acts as a reliable host listener and bridge:

1. **Listens** continuously on a designated TCP port for incoming instrument connections.
2. **Performs ASTM Handshakes**: Handles `ENQ`, `ACK`, `NAK`, and frame checksum verifications.
3. **Parses & Extracts**: Converts raw ASTM frames into structured JSON payloads (Sample IDs, Patient info, Test Codes, Parameters, Units, Flags).
4. **Safely Persists**: Writes exact raw frames and structured JSON to local disk for audit trails.
5. **Delivers to LIS**: Posts the payload securely to the COCOHOSPITALS LIS webhook endpoint.

```text
┌───────────────────────┐
│  Laboratory Analyzer  │
│  (ERBA / MultiXL / …) │
└──────────┬────────────┘
           │
           │ ASTM E1381 TCP/IP (e.g., Port 5002)
           ▼
┌─────────────────────────────────────────────────────────────┐
│             COCOHOSPITALS LIS Analyzer Connector            │
│                                                             │
│  ┌───────────────────────┐       ┌───────────────────────┐  │
│  │   Desktop UI (PyQt)   │◀─────▶│ TCP Listener Engine   │  │
│  │ • Real-time Logs      │ (IPC) │ • ASTM Frame Handler  │  │
│  │ • Status Indicator    │       │ • Checksum Validator  │  │
│  │ • Interface Config    │       │ • JSON Message Parser │  │
│  │ • Single Instance Lock│       │ • 24/7 Auto-Reconnect │  │
│  └───────────────────────┘       └───────────┬───────────┘  │
└──────────────────────────────────────────────│──────────────┘
                                               │
                                               │ HTTPS / REST API POST
                                               ▼
                                ┌─────────────────────────────┐
                                │      COCOHOSPITALS LIS      │
                                │   (Laboratory Webhook API)  │
                                └─────────────────────────────┘
```

---

## Key Features

- **Universal Windows Compatibility**: Fully compatible with both **32-bit (x86)** and **64-bit (x64 / AMD64)** Windows systems. Built as a pure 32-bit x86 binary set that runs natively on 32-bit Windows and seamlessly on 64-bit Windows via WOW64.
- **Automatic Startup on Windows Boot**: Starts automatically whenever the PC boots or a user logs on via an elevated Windows Scheduled Task (`schtasks` / `Register-ScheduledTask`) and a per-machine Registry `Run` entry.
- **Zero-Touch Auto-Connect**: Automatically initializes configuration and starts listening on the configured TCP port immediately after launching. No manual click of "CONNECT" is required after a reboot.
- **24/7 Persistent Operation & Auto-Reconnection**:
  - **Socket & Network Recovery**: If the socket closes, network drops, or interface resets, the listener retries with exponential backoff (2s up to 60s) until restored.
  - **Process Crash Recovery**: If the background listener engine is terminated or crashes, the parent UI detects it and automatically relaunches it with exponential backoff.
  - **Remote LIS Webhook Retries**: If the hospital server is temporarily down, restarting, or unreachable, outbound result posts retry automatically with exponential backoff instead of dropping data.
- **Single-Instance Protection**: Uses named Windows Mutexes (`Global\` and `Local\`) to prevent duplicate applications, duplicate listeners, or duplicate result processing.
- **Port Exclusivity (`SO_EXCLUSIVEADDRUSE`)**: Prevents socket hijacking or zombie processes from stealing incoming analyzer transmissions.
- **Non-Admin Writable Storage**: Directs all runtime logs, temporary files, and configs to `%LOCALAPPDATA%`, preventing `PermissionError: [Errno 13]` when installed under `C:\Program Files\` or `C:\Program Files (x86)\`.

---

## System Requirements

- **Operating System**: Windows 7 SP1, Windows 8.1, Windows 10, Windows 11, or Windows Server (2012 R2 or newer).
- **Architecture**: 32-bit (x86) or 64-bit (x64).
- **RAM**: Minimum 512 MB (1 GB+ recommended).
- **Disk Space**: ~100 MB free space.
- **Network**: Static IP or fixed local network subnet for communication with laboratory instruments over TCP/IP, and internet access for LIS API delivery.

---

## Installation & Deployment

### Quick Install (Production)

1. Obtain the installer: **`COCOHOSPITALS-LIS.exe`** from the `installer-output/` folder.
2. Right-click **`COCOHOSPITALS-LIS.exe`** and select **Run as administrator**.
3. Follow the on-screen installation wizard:
   - On **32-bit Windows**, it installs to:  
     `C:\Program Files\COCOHOSPITALS\LIS Analyzer Connector`
   - On **64-bit Windows**, it installs to:  
     `C:\Program Files (x86)\COCOHOSPITALS\LIS Analyzer Connector`
4. The installer automatically:
   - Configures the Windows Scheduled Task to launch on logon with highest privileges.
   - Adds the per-machine Registry startup entry.
   - Creates Desktop and Start Menu shortcuts.
   - Launches the connector immediately upon setup completion.

### Clean Uninstall

- Uninstall via **Windows Settings > Apps & Features** (or **Control Panel > Programs and Features**) -> **COCOHOSPITALS LIS**.
- The uninstaller automatically removes the scheduled task, registry keys, desktop icons, and temporary files cleanly.

---

## Configuration Guide

When opened, the connector presents an intuitive user interface:

| Field | Description | Example |
| :--- | :--- | :--- |
| **Analyzer IP** | IP address assigned to the physical analyzer instrument | `10.10.14.249` |
| **TCP Port** | Local TCP port the connector listens on for ASTM data | `5002` |
| **Source Device** | Device identifier sent with webhook payloads to the LIS | `ERRBA7689` / `ERBA 360` |
| **API Endpoint** | The full HTTPS webhook URL on COCOHOSPITALS LIS | `https://rims.admin.cocohospitals.com/api/v1/hospital/rims/analyzer-webhook` |

### Modifying Configuration
1. Click **EDIT CONFIGURATION**. The current listener safely shuts down and releases the TCP port.
2. Enter the new values.
3. Click **TEST API** to verify internet reachability to the LIS endpoint.
4. Click **SAVE CONFIGURATION**. The changes are stored, and the listener starts listening automatically with the updated parameters.

---

## Continuous 24/7 Operation & Reconnection

The connector is built specifically for hospital environments where machines remain on for months:

```text
[Windows Boot / Login]
         │
         ▼
[Auto-Start via Scheduled Task]
         │
         ▼
[Single-Instance Mutex Check] ────(Already running)────▶ [Exit cleanly with code 0]
         │ (First instance)
         ▼
[Initialize Config from %LOCALAPPDATA%]
         │
         ▼
[Auto-Start ASTM Listener (Port 5002)]
         │
         ├──▶ Bind Failed (Port busy/network init) ──▶ Wait (exponential backoff) ──▶ Retry Bind
         │
         ▼
[Status: CONNECTED (Green)]
         │
         ├──▶ Analyzer Connection Dropped ──▶ Close connection cleanly ──▶ Keep listening
         │
         ├──▶ Listener Process Crashed ──▶ Schedule auto-restart with backoff ──▶ Recovered
         │
         └──▶ LIS Webhook API Unavailable ──▶ Local disk saved ──▶ Retry API with backoff
```

- **Backoff Schedule**: Retries begin at 2.0 seconds, scaling exponentially ($2s \to 4s \to 8s \to 16s \to 32s \to 60s \text{ max}$) to prevent CPU throttling or network flooding.
- **Backoff Reset**: Whenever a connection succeeds or a message successfully delivers, the backoff timer resets back to 2.0 seconds.

---

## Project Structure

```text
analyser-listener/
├── build_universal_32bit.ps1       # Automated universal 32-bit build pipeline
├── COCOHOSPITALS_LIS_Analyzer_Connector.iss # Inno Setup installer script
├── logo.ico                        # Application & installer icon
├── README.md                       # Comprehensive documentation
├── requirements.txt                # Root Python dependencies
│
├── desktop-app/                    # Desktop GUI (PyQt5 / PySide6)
│   ├── app.py                      # Main UI application & subprocess supervisor
│   ├── erba_connector_config.json  # Default fallback configuration
│   ├── source_devices.json         # Supported instrument dropdown list
│   ├── test_sender.py              # Mock ASTM sender for verification/QA
│   └── dist/                       # PyInstaller build output
│
├── py-script/                      # ASTM Network Engine
│   ├── erba_listener.py            # High-performance TCP ASTM listener & API client
│   └── erba_parser.py              # ASTM E1381/E1394 message framing & record parser
│
└── installer-output/               # Output distribution directory
    └── COCOHOSPITALS-LIS.exe       # Production-ready universal installer
```

---

## Developer Guide & Build Instructions

If you make modifications to the source code, follow these steps to build the universal installer:

### Prerequisites

1. **Python 3.11 32-bit (x86)**:
   Installed at `%LOCALAPPDATA%\Programs\Python\Python311-32\python.exe` (or install via `winget install --id Python.Python.3.11 --architecture x86`).
2. **Inno Setup 6**:
   Install via `winget install --id JRSoftware.InnoSetup` or from [jrsoftware.org](https://jrsoftware.org/).
3. **Python Libraries (32-bit environment)**:
   ```powershell
   & "$env:LOCALAPPDATA\Programs\Python\Python311-32\python.exe" -m pip install requests python-dotenv pyinstaller PyQt5 pillow
   ```

### Running the One-Click Build

Execute the build script in PowerShell from the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_universal_32bit.ps1
```

The script automatically:
1. Compiles `py-script/erba_listener.py` into a standalone 32-bit console executable (`dist-listener/erba_listener.exe`).
2. Compiles `desktop-app/app.py` into a windowed 32-bit application folder (`desktop-app/dist/...`).
3. Syncs icons, configs, and device lists into the distribution directory.
4. Compiles the Inno Setup universal installer (`installer-output/COCOHOSPITALS-LIS-Analyzer-Connector-Setup.exe`).
5. Performs binary PE header analysis, verifying that all output files are 32-bit x86 binaries.

---

## File & Log Locations

To ensure zero permission conflicts on standard user accounts, runtime data is located in `%LOCALAPPDATA%`:

- **Application Logs**:  
  `%LOCALAPPDATA%\COCOHOSPITALS\LIS Analyzer Connector\erba_connector.log`
- **Listener Logs**:  
  `%LOCALAPPDATA%\COCOHOSPITALS\LIS Analyzer Connector\logs\erba_listener.log`
- **Raw Received ASTM Messages**:  
  `%LOCALAPPDATA%\COCOHOSPITALS\LIS Analyzer Connector\logs\messages\erba_*.txt`
- **Parsed JSON Records**:  
  `%LOCALAPPDATA%\COCOHOSPITALS\LIS Analyzer Connector\logs\json\erba_*.json`
- **Active Configuration**:  
  `%LOCALAPPDATA%\COCOHOSPITALS\LIS Analyzer Connector\erba_connector_config.json`

---

## Troubleshooting & Diagnostics

### 1. Port 5002 Already in Use
If the connector reports that the TCP port could not be bound:
1. Check what process is holding the port in PowerShell:
   ```powershell
   netstat -ano | findstr :5002
   ```
2. If an orphaned process is holding it, kill it by PID:
   ```powershell
   Stop-Process -Id <PID> -Force
   ```
3. Restart the connector.

### 2. Windows Firewall Prompt
When the connector runs for the first time, Windows Firewall may ask to allow network traffic:
- Ensure you check **Private networks** (and **Domain networks** if applicable in a hospital AD environment).
- If needed, create an inbound firewall rule in PowerShell:
  ```powershell
  New-NetFirewallRule -DisplayName "COCOHOSPITALS ASTM Listener" -Direction Inbound -LocalPort 5002 -Protocol TCP -Action Allow
  ```

### 3. Testing Local Transmission Without Analyzer Hardware
You can simulate an ASTM analyzer transmission locally using the included test sender:
```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python311-32\python.exe" desktop-app\test_sender.py
```
Check the **Activity Log** in the GUI to verify that the message was received, parsed, and posted to the LIS webhook.
