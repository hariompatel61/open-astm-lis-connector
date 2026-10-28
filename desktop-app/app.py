import os
import sys
import json
import logging
import site
import traceback
from pathlib import Path

import requests
try:
    from PyQt5.QtWidgets import (
        QApplication, QWidget, QLabel, QLineEdit, QPushButton, QComboBox,
        QVBoxLayout, QHBoxLayout, QGridLayout, QTextEdit, QFrame,
        QMessageBox,
    )
    from PyQt5.QtCore import QProcess, QProcessEnvironment, Qt, QTimer
except ImportError:
    from PySide6.QtWidgets import (
        QApplication, QWidget, QLabel, QLineEdit, QPushButton, QComboBox,
        QVBoxLayout, QHBoxLayout, QGridLayout, QTextEdit, QFrame,
        QMessageBox,
    )
    from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, QTimer


# ============================================================
# ERBA / MultiXL Connector - Desktop UI
# ============================================================

# Resolve files relative to the folder containing the EXE when frozen.
# In development, use the desktop-app source directory.
import shutil

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    DATA_DIR = Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))) / "COCOHOSPITALS" / "LIS Analyzer Connector"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
else:
    BASE_DIR = Path(__file__).resolve().parent
    DATA_DIR = BASE_DIR

# The production build ships erba_listener.exe beside the GUI EXE.
LISTENER_DIR = BASE_DIR
LISTENER_FILE = LISTENER_DIR / "erba_listener.exe"

LISTENER_STOP_FILE = DATA_DIR / "_listener_stop.flag"
LISTENER_TEMP_DIR = DATA_DIR / "_listener_temp"

CONFIG_FILE = DATA_DIR / "erba_connector_config.json"
DEVICE_OPTIONS_FILE = DATA_DIR / "source_devices.json"

# Copy default config from BASE_DIR to DATA_DIR if missing
if getattr(sys, "frozen", False):
    if not CONFIG_FILE.exists() and (BASE_DIR / "erba_connector_config.json").exists():
        shutil.copy2(BASE_DIR / "erba_connector_config.json", CONFIG_FILE)
    if not DEVICE_OPTIONS_FILE.exists() and (BASE_DIR / "source_devices.json").exists():
        shutil.copy2(BASE_DIR / "source_devices.json", DEVICE_OPTIONS_FILE)

CONFIG_KEYS = (
    "analyzer_ip",
    "tcp_port",
    "source_device",
    "api_endpoint",
)

logging.basicConfig(
    filename=str(DATA_DIR / "erba_connector.log"),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("ERBAConnector")


class ERBAConnector(QWidget):

    def __init__(self):
        super().__init__()

        self.connected = False
        self.listener_process = None
        self.loading_config = False
        self.edit_mode = False
        self.was_connected_before_edit = False
        self.stopping_listener = False
        self.config = self.load_config()

        # Continuous 24/7 background operation & reconnection
        self.auto_reconnect_enabled = True
        self.reconnect_delay = 2.0
        self.min_reconnect_delay = 2.0
        self.max_reconnect_delay = 60.0
        self.reconnect_attempts = 0

        # Make the local folders used by the listener deterministic and writable.
        try:
            LISTENER_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            logger.exception("Unable to create listener temp directory")

        try:
            self.setWindowTitle("COCOHOSPITALS LIS - Analyzer Connector")
            self.resize(940, 500)
            self.setMinimumSize(820, 440)
            self.create_ui()
            self.log_message("Application started successfully.")
            self.log_message(f"Listener: {LISTENER_FILE}")

            if not LISTENER_FILE.exists():
                self.log_message(
                    f"WARNING: Listener not found: {LISTENER_FILE}",
                    "WARNING",
                )
            else:
                # Automatically connect on boot / startup for 24/7 background operation
                QTimer.singleShot(1000, self.auto_start_connection)
        except Exception as exc:
            logger.exception("Application initialization failed")
            self.show_error("Application Error", str(exc))

    # ========================================================
    # UI
    # ========================================================

    def create_ui(self):
        main = QVBoxLayout()
        main.setContentsMargins(16, 12, 16, 12)
        main.setSpacing(8)

        self.setStyleSheet("""
            QWidget {
                background: #f1f5f9;
                color: #0f172a;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            }
            QLabel { background: transparent; }
        """)

        # ----------------------------------------------------
        # 1. Compact Header
        # ----------------------------------------------------
        header = QFrame()
        header.setObjectName("Header")
        header.setStyleSheet("""
            #Header {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
            }
            QLabel { background: transparent; border: 0; }
            #BrandBadge {
                background: #e0f2fe;
                border: 1px solid #bae6fd;
                border-radius: 4px;
                color: #0369a1;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 800;
                letter-spacing: 0.5px;
            }
        """)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 8, 14, 8)
        hl.setSpacing(12)

        title_stack = QVBoxLayout()
        title_stack.setSpacing(1)

        title = QLabel("COCOHOSPITALS LIS - Analyzer Connector")
        title.setStyleSheet(
            "color: #0f2f4f; font-size: 16px; font-weight: 800;"
        )
        subtitle = QLabel(
            "Laboratory Instrument Interface | ASTM TCP/IP"
        )
        subtitle.setStyleSheet(
            "color: #64748b; font-size: 11px; font-weight: 600;"
        )
        brand_badge = QLabel("COCOHOSPITALS LIS")
        brand_badge.setObjectName("BrandBadge")
        brand_badge.setAlignment(Qt.AlignCenter)

        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        hl.addLayout(title_stack)
        hl.addStretch()
        hl.addWidget(brand_badge)
        main.addWidget(header)

        # ----------------------------------------------------
        # 2. Compact Interface Configuration (2 Rows x 2 Columns)
        # ----------------------------------------------------
        card = QFrame()
        card.setObjectName("ConfigCard")
        card.setStyleSheet("""
            #ConfigCard {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
            }
            QLabel {
                color: #334155;
                font-size: 12px;
                font-weight: 700;
                border: 0;
                background: transparent;
            }
            QLineEdit {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 13px;
                color: #0f172a;
                min-height: 26px;
                max-height: 28px;
            }
            QLineEdit:focus {
                border: 1px solid #0284c7;
                background: #f8fafc;
            }
            QLineEdit[readOnly="true"] {
                background: #f8fafc;
                color: #475569;
                border: 1px solid #e2e8f0;
            }
            QComboBox {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 13px;
                font-weight: 600;
                color: #0f172a;
                min-height: 26px;
                max-height: 28px;
            }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #0f172a;
                selection-background-color: #0284c7;
                selection-color: #ffffff;
                font-size: 13px;
                font-weight: 600;
                outline: 0;
                border: 1px solid #cbd5e1;
            }
            QComboBox:focus {
                border: 1px solid #0284c7;
                background: #f8fafc;
            }
            QComboBox:disabled {
                background: #f8fafc;
                color: #475569;
                border: 1px solid #e2e8f0;
            }
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 8, 14, 10)
        cl.setSpacing(6)

        ct = QLabel("Interface Configuration")
        ct.setStyleSheet(
            "font-size: 13px; font-weight: 800; color: #0f2f4f; border: 0;"
        )
        cl.addWidget(ct)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(0, 2, 0, 0)

        self.loading_config = True

        self.ip_input = QLineEdit(self.config["analyzer_ip"])
        self.ip_input.setObjectName("ip_input")
        self.ip_input.setPlaceholderText("e.g. 10.10.11.2")

        self.port_input = QLineEdit(self.config["tcp_port"])
        self.port_input.setObjectName("port_input")
        self.port_input.setPlaceholderText("e.g. 5002")

        self.source_device_input = QComboBox()
        self.source_device_input.setObjectName("source_device_input")
        self.source_device_input.setEditable(True)
        self.source_device_input.setInsertPolicy(QComboBox.NoInsert)
        self.load_source_device_options()

        self.api_input = QLineEdit(self.config["api_endpoint"])
        self.api_input.setObjectName("api_input")
        self.api_input.setPlaceholderText("https://...")

        self.loading_config = False

        ip_lbl = QLabel("Analyzer IP:")
        ip_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        port_lbl = QLabel("TCP Port:")
        port_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        source_lbl = QLabel("Source Device:")
        source_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        api_lbl = QLabel("API Endpoint:")
        api_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Row 1: Analyzer IP | TCP Port
        grid.addWidget(ip_lbl, 0, 0)
        grid.addWidget(self.ip_input, 0, 1)
        grid.addWidget(port_lbl, 0, 2)
        grid.addWidget(self.port_input, 0, 3)

        # Row 2: Source Device | API Endpoint
        grid.addWidget(source_lbl, 1, 0)
        grid.addWidget(self.source_device_input, 1, 1)
        grid.addWidget(api_lbl, 1, 2)
        grid.addWidget(self.api_input, 1, 3)

        # Stretch: Give right column (API Endpoint) more horizontal width
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 0)
        grid.setColumnStretch(3, 5)

        cl.addLayout(grid)
        main.addWidget(card)

        # ----------------------------------------------------
        # 3. Smaller Action Buttons (Single Row)
        # ----------------------------------------------------
        buttons = QHBoxLayout()
        buttons.setSpacing(8)

        self.test_button = QPushButton("TEST API")
        self.edit_button = QPushButton("EDIT CONFIGURATION")
        self.connection_button = QPushButton("CONNECT")

        for b in (self.test_button, self.edit_button, self.connection_button):
            b.setMinimumHeight(36)
            b.setMaximumHeight(38)

        self.test_button.setStyleSheet("""
            QPushButton {
                background: #155f8c;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 700;
                padding: 6px 12px;
            }
            QPushButton:hover { background: #0f4d73; }
            QPushButton:disabled { background: #94a3b8; color: #f1f5f9; }
        """)

        self.edit_button.setStyleSheet("""
            QPushButton {
                background: #ffffff;
                color: #0f2f4f;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 700;
                padding: 6px 12px;
            }
            QPushButton:hover { background: #f8fafc; border-color: #94a3b8; }
            QPushButton:disabled { color: #94a3b8; background: #f1f5f9; border-color: #e2e8f0; }
        """)

        self.connection_button.setStyleSheet("""
            QPushButton {
                background: #157f4f;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 700;
                padding: 6px 12px;
            }
            QPushButton:hover { background: #116840; }
            QPushButton:disabled { background: #94a3b8; color: #f1f5f9; }
        """)

        buttons.addWidget(self.test_button)
        buttons.addWidget(self.edit_button)
        buttons.addWidget(self.connection_button)
        main.addLayout(buttons)

        # ----------------------------------------------------
        # 4. Compact Connection Status Bar
        # ----------------------------------------------------
        status_card = QFrame()
        status_card.setObjectName("StatusCard")
        status_card.setStyleSheet("""
            #StatusCard {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
            }
            QLabel { background: transparent; border: 0; }
        """)
        sl = QHBoxLayout(status_card)
        sl.setContentsMargins(10, 4, 10, 4)
        sl.setSpacing(6)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #64748b; font-size: 14px; border: 0;")
        self.status_label = QLabel("Disconnected")
        self.status_label.setObjectName("status_label")
        self.status_label.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #475569; border: 0;"
        )

        sl.addWidget(self.status_dot)
        sl.addWidget(self.status_label)
        sl.addStretch()
        main.addWidget(status_card)

        # ----------------------------------------------------
        # 5. Activity Log (Compact)
        # ----------------------------------------------------
        log_header = QHBoxLayout()
        log_header.setContentsMargins(0, 2, 0, 0)
        log_title = QLabel("Activity Log")
        log_title.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #0f2f4f;"
        )
        log_header.addWidget(log_title)
        log_header.addStretch()
        main.addLayout(log_header)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(150)
        self.log_box.setStyleSheet("""
            QTextEdit {
                background: #0f172a;
                color: #e2e8f0;
                border: 1px solid #1e293b;
                border-radius: 4px;
                padding: 6px 8px;
                font-family: Consolas, "Liberation Mono", Menlo, Courier, monospace;
                font-size: 12px;
            }
        """)
        main.addWidget(self.log_box)

        self.setLayout(main)

        self.test_button.clicked.connect(self.test_api)
        self.edit_button.clicked.connect(self.edit_configuration)
        self.connection_button.clicked.connect(self.toggle_connection)

        # IMPORTANT: configuration is saved only when the user presses
        # SAVE CONFIGURATION. Do not restart the listener while typing.
        self.set_config_edit_mode(False)

    # ========================================================
    # CONFIGURATION STORAGE
    # ========================================================

    def config_text_fields(self):
        return (
            self.ip_input,
            self.port_input,
            self.api_input,
        )

    def load_source_device_options(self):
        configured_source = self.normalize_source_device(
            self.config["source_device"]
        )
        options = []

        try:
            if DEVICE_OPTIONS_FILE.exists():
                with DEVICE_OPTIONS_FILE.open("r", encoding="utf-8") as file:
                    saved_options = json.load(file)

                if isinstance(saved_options, list):
                    for option in saved_options:
                        option = self.normalize_source_device(option)
                        if option and option not in options:
                            options.append(option)
        except Exception:
            logger.exception("Unable to load source device options")

        if configured_source and configured_source not in options:
            options.append(configured_source)

        self.source_device_input.addItems(options)

        if configured_source:
            self.source_device_input.setEditText(configured_source)
        else:
            self.source_device_input.setEditText("")

    def save_source_device_option(self):
        source = self.normalize_source_device(
            self.source_device_input.currentText()
        )

        if not source:
            return

        self.source_device_input.setEditText(source)

        options = []

        try:
            if DEVICE_OPTIONS_FILE.exists():
                with DEVICE_OPTIONS_FILE.open("r", encoding="utf-8") as file:
                    saved_options = json.load(file)

                if isinstance(saved_options, list):
                    for option in saved_options:
                        option = self.normalize_source_device(option)
                        if option and option not in options:
                            options.append(option)
        except Exception:
            logger.exception("Unable to read source device options")

        if source not in options:
            options.append(source)

            try:
                temp_file = DEVICE_OPTIONS_FILE.with_suffix(".tmp")
                with temp_file.open("w", encoding="utf-8") as file:
                    json.dump(options, file, indent=2)
                    file.write("\n")

                temp_file.replace(DEVICE_OPTIONS_FILE)
                self.source_device_input.addItem(source)
            except Exception:
                logger.exception("Unable to save source device option")
                self.log_message(
                    "Unable to save source device option.",
                    "ERROR",
                )

    def load_config(self):
        config = {key: "" for key in CONFIG_KEYS}

        try:
            if CONFIG_FILE.exists():
                with CONFIG_FILE.open("r", encoding="utf-8") as file:
                    saved_config = json.load(file)

                if isinstance(saved_config, dict):
                    for key in CONFIG_KEYS:
                        value = saved_config.get(key)
                        if isinstance(value, str):
                            config[key] = value

                logger.info("Loaded saved configuration from %s", CONFIG_FILE)
        except Exception:
            logger.exception("Unable to load saved configuration")

        return config

    def current_config(self):
        return {
            "analyzer_ip": self.ip_input.text(),
            "tcp_port": self.port_input.text(),
            "source_device": self.normalize_source_device(
                self.source_device_input.currentText()
            ),
            "api_endpoint": self.api_input.text(),
        }

    def save_config(self):
        try:
            source = self.current_config()["source_device"]
            self.source_device_input.setEditText(source)

            temp_file = CONFIG_FILE.with_suffix(".tmp")
            with temp_file.open("w", encoding="utf-8") as file:
                json.dump(self.current_config(), file, indent=2)
                file.write("\n")

            temp_file.replace(CONFIG_FILE)
        except Exception:
            logger.exception("Unable to save configuration")
            self.log_message(
                "Unable to save configuration changes.",
                "ERROR",
            )

    def normalize_source_device(self, value):
        return str(value or "").strip().upper()

    def configuration_changed(self):
        # Kept for backward compatibility with older signal connections.
        # Current UI intentionally does not auto-save while typing.
        return

    def set_config_edit_mode(self, editing):
        self.edit_mode = editing

        for field in self.config_text_fields():
            field.setReadOnly(not editing)
            field.setProperty("readOnly", not editing)
            field.style().unpolish(field)
            field.style().polish(field)

        self.source_device_input.setEnabled(editing)

        if editing:
            self.edit_button.setText("SAVE CONFIGURATION")
        else:
            self.edit_button.setText("EDIT CONFIGURATION")

    def edit_configuration(self):
        if self.edit_mode:
            try:
                # Validate the NEW configuration before writing it.
                self.validate_configuration()

                self.save_source_device_option()
                self.save_config()
                self.set_config_edit_mode(False)

                self.log_message("Configuration saved successfully.", "SUCCESS")

                # If the listener was previously running, restart it with
                # the new configuration. This is the important part that
                # allows IP A -> IP B -> IP A without manual restart.
                if self.was_connected_before_edit:
                    self.log_message(
                        "Restarting ASTM listener with new configuration..."
                    )
                    self.connect()
                else:
                    self.set_disconnected_ui()

            except ValueError as exc:
                self.log_message(str(exc), "ERROR")
                self.show_error("Invalid Configuration", str(exc))
            except Exception as exc:
                logger.exception("Configuration save failed")
                self.log_message(
                    f"Configuration save failed: {exc}",
                    "ERROR",
                )
                self.set_disconnected_ui()
            return

        # Enter edit mode. Stop the listener first, but remember whether it
        # was running so SAVE can automatically start it again.
        self.was_connected_before_edit = (
            self.connected or
            (self.listener_process is not None and
             self.listener_process.state() != QProcess.NotRunning)
        )

        if self.was_connected_before_edit:
            self.log_message(
                "Editing configuration: stopping current listener...",
                "WARNING",
            )
            if not self.stop_listener(wait_ms=5000):
                self.show_error(
                    "Listener Stop Failed",
                    "The current ASTM listener could not be stopped safely. "
                    "Configuration editing was cancelled.",
                )
                return

        self.set_config_edit_mode(True)
        self.edit_button.setEnabled(True)
        self.connection_button.setEnabled(False)
        self.test_button.setEnabled(False)
        self.ip_input.setFocus()
        self.log_message(
            "Configuration edit mode enabled. Change values and press SAVE CONFIGURATION."
        )

    # ========================================================
    # LOGGING
    # ========================================================

    def log_message(self, message, level="INFO"):
        try:
            self.log_box.append(f"[{level}] {message}")
            self.log_box.ensureCursorVisible()

            if level == "ERROR":
                logger.error(message)
            elif level == "WARNING":
                logger.warning(message)
            else:
                logger.info(message)
        except Exception:
            pass

    def detect_level(self, line):
        u = line.upper()
        if "ERROR" in u or "EXCEPTION" in u or "TRACEBACK" in u:
            return "ERROR"
        if "WARNING" in u or "WARN" in u:
            return "WARNING"
        if "SUCCESS" in u:
            return "SUCCESS"
        return "INFO"

    def show_error(self, title, message):
        try:
            QMessageBox.critical(self, title, message)
        except Exception:
            pass

    # ========================================================
    # VALIDATION
    # ========================================================

    def validate_configuration(self):
        ip = self.ip_input.text().strip()
        port = self.port_input.text().strip()
        source = self.source_device_input.currentText().strip()
        api = self.api_input.text().strip()

        if not ip:
            raise ValueError("Analyzer IP is required.")
        if not port:
            raise ValueError("TCP port is required.")
        if not source:
            raise ValueError("Source device is required.")
        if not api:
            raise ValueError("API endpoint is required.")
        if not api.startswith(("http://", "https://")):
            raise ValueError(
                "API endpoint must start with http:// or https://"
            )

        try:
            port_number = int(port)
        except ValueError:
            raise ValueError("TCP port must be a number.")

        if not 1 <= port_number <= 65535:
            raise ValueError("TCP port must be between 1 and 65535.")

        return ip, port_number, source, api

    # ========================================================
    # API TEST
    # ========================================================

    def test_api(self):
        self.test_button.setEnabled(False)
        try:
            api = self.api_input.text().strip()
            if not api:
                raise ValueError("API endpoint is empty.")

            self.status_label.setText("Testing API...")
            self.log_message(f"Testing API: {api}")

            response = requests.head(
                api, timeout=10, allow_redirects=True
            )

            self.log_message(
                f"API HTTP status: {response.status_code}"
            )

            if response.status_code < 500:
                self.status_label.setText("API reachable")
                self.log_message("API endpoint is reachable.", "SUCCESS")
                QMessageBox.information(
                    self,
                    "API Test",
                    f"API endpoint is reachable.\n\n"
                    f"HTTP Status: {response.status_code}",
                )
            else:
                raise RuntimeError(
                    f"Server returned HTTP {response.status_code}"
                )

        except requests.Timeout:
            self.log_message("API request timed out.", "ERROR")
            self.status_label.setText("API Timeout")
            self.show_error(
                "API Timeout",
                "The API did not respond within 10 seconds.",
            )
        except requests.ConnectionError as exc:
            self.log_message(f"API connection failed: {exc}", "ERROR")
            self.status_label.setText("API Connection Failed")
            self.show_error("API Connection Failed", str(exc))
        except requests.RequestException as exc:
            self.log_message(f"API request error: {exc}", "ERROR")
            self.status_label.setText("API Error")
            self.show_error("API Request Error", str(exc))
        except Exception as exc:
            logger.exception("API test failed")
            self.log_message(f"API test failed: {exc}", "ERROR")
            self.status_label.setText("API Test Failed")
            self.show_error("API Test Failed", str(exc))
        finally:
            self.test_button.setEnabled(True)

    # ========================================================
    # CONNECTION TOGGLE
    # ========================================================

    def toggle_connection(self):
        if self.connected:
            self.disconnect()
        else:
            self.connect()

    def split_api_endpoint(self, endpoint):
        endpoint = endpoint.strip().rstrip("/")
        marker = "/api/"
        pos = endpoint.find(marker)

        if pos == -1:
            return endpoint, "/"

        return endpoint[:pos].rstrip("/"), endpoint[pos:]

    def auto_start_connection(self):
        if self.connected or self.edit_mode:
            return
        self.log_message("Initializing automatic connection for 24/7 background operation...")
        self.connect()

    def schedule_reconnect(self):
        if self.edit_mode or self.connected or not self.auto_reconnect_enabled:
            return
        if self.listener_process is not None and self.listener_process.state() != QProcess.NotRunning:
            return

        self.reconnect_attempts += 1
        delay = self.reconnect_delay
        self.reconnect_delay = min(self.reconnect_delay * 2.0, self.max_reconnect_delay)

        self.status_dot.setStyleSheet(
            "color:#d97706;font-size:14px;border:0;background:transparent;"
        )
        self.status_label.setText(
            f"Disconnected — Reconnecting in {int(delay)}s (attempt {self.reconnect_attempts})..."
        )
        self.status_label.setStyleSheet(
            "font-size:12px;font-weight:700;color:#b45309;border:0;background:transparent;"
        )
        self.log_message(
            f"Automatic reconnection scheduled in {int(delay)}s (attempt {self.reconnect_attempts})...",
            "WARNING",
        )
        QTimer.singleShot(int(delay * 1000), self._do_reconnect)

    def _do_reconnect(self):
        if self.edit_mode or self.connected or not self.auto_reconnect_enabled:
            return
        if self.listener_process is not None and self.listener_process.state() != QProcess.NotRunning:
            return
        self.log_message(f"Attempting automatic reconnection (attempt {self.reconnect_attempts})...")
        self.connect()

    def connect(self):
        self.auto_reconnect_enabled = True
        try:
            ip, port, source, api = self.validate_configuration()

            if self.listener_process is not None:
                if self.listener_process.state() != QProcess.NotRunning:
                    self.log_message(
                        "Listener is already running.",
                        "WARNING",
                    )
                    return
                self.listener_process = None

            if not LISTENER_FILE.exists():
                raise FileNotFoundError(
                    "ASTM listener executable not found.\n\n"
                    f"Expected:\n{LISTENER_FILE}\n\n"
                    "Build erba_listener.exe and place it in the same "
                    "folder as COCOHOSPITALS-LIS-Analyzer-Connector.exe."
                )

            # A previous stop request must never affect the next listener.
            try:
                if LISTENER_STOP_FILE.exists():
                    LISTENER_STOP_FILE.unlink()
            except Exception:
                logger.exception("Unable to clear listener stop flag")

            LISTENER_TEMP_DIR.mkdir(parents=True, exist_ok=True)

            self.log_message("Validating configuration...")
            self.log_message(f"Analyzer IP: {ip}")
            self.log_message(f"TCP Port: {port}")
            self.log_message(f"Source Device: {source}")
            self.log_message(f"API Endpoint: {api}")
            self.log_message("Configuration validation successful.")
            self.log_message("Starting ASTM listener...")

            self.connection_button.setText("STARTING...")
            self.connection_button.setEnabled(False)
            self.test_button.setEnabled(False)
            self.edit_button.setEnabled(False)
            self.set_config_edit_mode(False)

            self.listener_process = QProcess(self)
            self.listener_process.setWorkingDirectory(str(LISTENER_DIR))

            env = self.listener_process.processEnvironment()
            if env.isEmpty():
                env = QProcessEnvironment.systemEnvironment()
            env.insert("LISTEN_HOST", "0.0.0.0")
            env.insert("LISTEN_PORT", str(port))
            env.insert("SOURCE_DEVICE", source)
            env.insert("API_ENABLED", "true")
            env.insert("LOG_DIR", str(DATA_DIR / "logs"))
            env.insert("LISTENER_STOP_FILE", str(LISTENER_STOP_FILE))

            # PyInstaller --onefile needs a writable extraction/temp directory.
            env.insert("TEMP", str(LISTENER_TEMP_DIR))
            env.insert("TMP", str(LISTENER_TEMP_DIR))

            api_base, api_path = self.split_api_endpoint(api)
            env.insert("API_BASE_URL", api_base)
            env.insert("API_PATH_TEMPLATE", api_path)

            self.listener_process.setProcessEnvironment(env)

            self.listener_process.readyReadStandardOutput.connect(
                self.read_listener_output
            )
            self.listener_process.readyReadStandardError.connect(
                self.read_listener_error
            )
            self.listener_process.started.connect(
                self.listener_started
            )
            self.listener_process.errorOccurred.connect(
                self.listener_error
            )
            self.listener_process.finished.connect(
                self.listener_finished
            )

            # Production always launches the dedicated listener EXE.
            self.listener_process.start(
                str(LISTENER_FILE),
                [],
            )

        except ValueError as exc:
            self.log_message(str(exc), "ERROR")
            self.show_error("Invalid Configuration", str(exc))
            self.set_disconnected_ui()
        except Exception as exc:
            logger.exception("Connect operation failed")
            self.log_message(f"Connection error: {exc}", "ERROR")
            self.set_disconnected_ui()
            self.show_error("Connection Error", str(exc))

    # ========================================================
    # LISTENER OUTPUT -> GUI
    # ========================================================

    def listener_started(self):
        # Process started != TCP listener successfully bound.
        # Actual CONNECTED state is set by read_listener_output() after the
        # listener prints LISTENING SUCCESSFULLY.
        port = self.port_input.text().strip()
        self.status_dot.setStyleSheet(
            "color:#d97706;font-size:14px;border:0;background:transparent;"
        )
        self.status_label.setText(
            f"Starting — Opening TCP {port}..."
        )
        self.status_label.setStyleSheet(
            "font-size:12px;font-weight:700;color:#b45309;border:0;background:transparent;"
        )
        self.log_message(
            "Listener process started; waiting for TCP bind confirmation..."
        )

    def read_listener_output(self):
        if not self.listener_process:
            return

        data = self.listener_process.readAllStandardOutput()
        text = bytes(data).decode("utf-8", errors="replace")

        for line in text.splitlines():
            line = line.rstrip()
            if not line:
                continue

            level = self.detect_level(line)
            self.log_message(line, level)

            if "LISTENING SUCCESSFULLY ON TCP" in line.upper():
                self.listener_ready()

    def listener_ready(self):
        self.connected = True
        port = self.port_input.text().strip()

        if self.reconnect_attempts > 0:
            self.log_message(
                "Connection restored successfully. Resetting retry delay.",
                "SUCCESS",
            )
        self.reconnect_delay = self.min_reconnect_delay
        self.reconnect_attempts = 0

        self.status_dot.setStyleSheet(
            "color:#16a34a;font-size:14px;border:0;background:transparent;"
        )
        self.status_label.setText(
            f"Connected — Listening on TCP {port}"
        )
        self.status_label.setStyleSheet(
            "font-size:12px;font-weight:700;color:#15803d;border:0;background:transparent;"
        )
        self.connection_button.setText("DISCONNECT")
        self.connection_button.setEnabled(True)
        self.test_button.setEnabled(True)
        self.edit_button.setEnabled(True)
        self.set_config_edit_mode(False)
        self.log_message(
            f"Listener is READY and listening on TCP {port}.",
            "SUCCESS",
        )
        self.log_message("Waiting for ASTM data from analyzer...")

    def read_listener_error(self):
        if not self.listener_process:
            return

        data = self.listener_process.readAllStandardError()
        text = bytes(data).decode("utf-8", errors="replace")

        for line in text.splitlines():
            line = line.rstrip()
            if line:
                self.log_message(line, "ERROR")

    def listener_error(self, error):
        names = {
            QProcess.FailedToStart: "Listener process failed to start.",
            QProcess.Crashed: "Listener process crashed.",
            QProcess.Timedout: "Listener process timed out.",
            QProcess.WriteError: "Listener process write error.",
            QProcess.ReadError: "Listener process read error.",
            QProcess.UnknownError: "Unknown listener process error.",
        }
        message = names.get(error, f"Listener process error: {error}")

        # During a normal stop/restart, QProcess can report a transient
        # process error. Do not treat an intentional stop as a connection
        # failure. The finished() handler will complete the transition.
        if getattr(self, "stopping_listener", False):
            logger.info("Intentional listener stop: %s", message)
            return

        logger.error(message)
        self.log_message(message, "ERROR")
        self.listener_process = None
        self.set_disconnected_ui()
        if not self.edit_mode and self.auto_reconnect_enabled:
            self.schedule_reconnect()

    def listener_finished(self, exit_code, exit_status):
        intentional = (
            getattr(self, "stopping_listener", False) or
            self.edit_mode or
            not self.auto_reconnect_enabled
        )

        if intentional:
            self.log_message(
                f"Listener stopped cleanly for restart. Exit code: {exit_code}."
            )
        elif exit_code == 0:
            self.log_message(
                f"Listener stopped. Exit code: {exit_code}."
            )
        else:
            self.log_message(
                f"Listener stopped unexpectedly. "
                f"Exit code: {exit_code}, status: {exit_status}.",
                "ERROR",
            )

        self.listener_process = None
        self.connected = False

        if not intentional:
            self.set_disconnected_ui()
            self.schedule_reconnect()

    # ========================================================
    # DISCONNECT / LISTENER STOP
    # ========================================================

    def stop_listener(self, wait_ms=5000):
        """Request a graceful listener shutdown using the stop flag."""
        process = self.listener_process

        if process is None or process.state() == QProcess.NotRunning:
            self.listener_process = None
            return True

        self.stopping_listener = True

        try:
            LISTENER_STOP_FILE.parent.mkdir(parents=True, exist_ok=True)
            LISTENER_STOP_FILE.touch()

            self.log_message(
                "Stop signal sent to ASTM listener; waiting for process to exit..."
            )

            if process.waitForFinished(wait_ms):
                self.listener_process = None
                self.connected = False
                return True

            # Safety fallback: if the listener did not react to the stop flag,
            # terminate the process so the TCP port cannot remain occupied.
            self.log_message(
                "Listener did not stop within timeout; terminating process.",
                "WARNING",
            )
            process.kill()
            process.waitForFinished(2000)
            self.listener_process = None
            self.connected = False
            return True

        except Exception:
            logger.exception("Listener stop failed")
            return False
        finally:
            self.stopping_listener = False

    def disconnect(self):
        try:
            self.auto_reconnect_enabled = False  # User explicitly requested disconnection
            self.log_message("Stopping ASTM listener...")
            self.connection_button.setText("STOPPING...")
            self.connection_button.setEnabled(False)
            self.edit_button.setEnabled(False)
            self.test_button.setEnabled(False)

            if not self.stop_listener(wait_ms=5000):
                raise RuntimeError("Listener could not be stopped safely.")

            try:
                if LISTENER_STOP_FILE.exists():
                    LISTENER_STOP_FILE.unlink()
            except Exception:
                logger.exception("Unable to remove listener stop flag")

            self.set_disconnected_ui()
            self.log_message("Disconnected.", "SUCCESS")

        except Exception as exc:
            logger.exception("Disconnect failed")
            self.log_message(f"Disconnect error: {exc}", "ERROR")
            self.listener_process = None
            self.stopping_listener = False
            self.set_disconnected_ui()

    def set_disconnected_ui(self):
        self.connected = False
        self.status_dot.setStyleSheet(
            "color:#64748b;font-size:14px;border:0;background:transparent;"
        )
        self.status_label.setText("Disconnected")
        self.status_label.setStyleSheet(
            "font-size:12px;font-weight:700;color:#475569;border:0;background:transparent;"
        )
        self.connection_button.setText("CONNECT")
        self.connection_button.setEnabled(True)
        self.test_button.setEnabled(True)
        self.edit_button.setEnabled(True)
        self.set_config_edit_mode(False)

    # ========================================================
    # EXCEPTIONS / CLOSE
    # ========================================================

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(
                exc_type, exc_value, exc_traceback
            )
            return

        error_text = "".join(
            traceback.format_exception(
                exc_type, exc_value, exc_traceback
            )
        )
        logger.error("UNHANDLED EXCEPTION:\n%s", error_text)

        try:
            self.log_message(
                f"Unexpected error: {exc_value}",
                "ERROR",
            )
            self.show_error("Unexpected Error", str(exc_value))
        except Exception:
            pass

    def closeEvent(self, event):
        try:
            self.log_message("Application closing...")
            self.save_config()

            if self.listener_process is not None:
                self.stop_listener(wait_ms=5000)

            try:
                if LISTENER_STOP_FILE.exists():
                    LISTENER_STOP_FILE.unlink()
            except Exception:
                pass

            logger.info("Application closed.")
        except Exception:
            logger.exception("Application close failed")

        event.accept()


_single_instance_mutex = None


def acquire_single_instance_lock():
    global _single_instance_mutex
    if os.name != "nt":
        return True

    import ctypes
    ERROR_ALREADY_EXISTS = 183
    ERROR_ACCESS_DENIED = 5

    kernel32 = ctypes.windll.kernel32
    for prefix in ("Global\\", "Local\\"):
        mutex_name = f"{prefix}COCOHOSPITALS_LIS_Connector_SingleInstance"
        mutex = kernel32.CreateMutexW(None, False, mutex_name)
        err = kernel32.GetLastError()
        if err == ERROR_ALREADY_EXISTS:
            if mutex:
                kernel32.CloseHandle(mutex)
            return False
        if mutex:
            _single_instance_mutex = mutex
            return True
        if err != ERROR_ACCESS_DENIED:
            break
    return True


def main():
    if not acquire_single_instance_lock():
        logger.warning(
            "Another instance of COCOHOSPITALS LIS Analyzer Connector is already running. Exiting cleanly."
        )
        print("Another instance is already running. Exiting cleanly.")
        if os.name == "nt":
            try:
                import ctypes
                user32 = getattr(ctypes.windll, "user32", None)
                if user32:
                    hwnd = user32.FindWindowW(None, "COCOHOSPITALS LIS - Analyzer Connector")
                    if hwnd:
                        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                        user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
        return 0

    app = QApplication(sys.argv)
    window = ERBAConnector()
    sys.excepthook = window.handle_exception
    window.show()
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        logger.exception("Fatal application error")
        print("FATAL ERROR:", exc)
        sys.exit(1)
