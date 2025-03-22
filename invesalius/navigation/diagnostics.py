# --------------------------------------------------------------------------
# Software:     InVesalius - Software de Reconstrucao 3D de Imagens Medicas
# Copyright:    (C) 2001  Centro de Pesquisas Renato Archer
# Homepage:     http://www.softwarepublico.gov.br
# Contact:      invesalius@cti.gov.br
# License:      GNU - GPL 2 (LICENSE.txt/LICENCA.txt)
# --------------------------------------------------------------------------
#    Este programa e software livre; voce pode redistribui-lo e/ou
#    modifica-lo sob os termos da Licenca Publica Geral GNU, conforme
#    publicada pela Free Software Foundation; de acordo com a versao 2
#    da Licenca.
#
#    Este programa eh distribuido na expectativa de ser util, mas SEM
#    QUALQUER GARANTIA; sem mesmo a garantia implicita de
#    COMERCIALIZACAO ou de ADEQUACAO A QUALQUER PROPOSITO EM
#    PARTICULAR. Consulte a Licenca Publica Geral GNU para obter mais
#    detalhes.
# --------------------------------------------------------------------------

import datetime
import enum
import json
import os
import time
from collections import deque
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import wx

import invesalius.constants as const
import invesalius.data.coregistration as dcr
import invesalius.data.tracker_connection as tc
import invesalius.gui.dialogs as dlg
import invesalius.session as ses
import invesalius.utils as utils
from invesalius.navigation.robot import Robot
from invesalius.navigation.tracker import Tracker
from invesalius.pubsub import pub as Publisher
from invesalius.utils import Singleton

try:
    from invesalius.enhanced_logging import get_logger
    from invesalius.error_handling import (
        ErrorCategory,
        ErrorSeverity,
        NavigationError,
        handle_errors,
        show_error_dialog,
    )

    HAS_ERROR_HANDLING = True
except ImportError:
    HAS_ERROR_HANDLING = False

if HAS_ERROR_HANDLING:
    logger = get_logger("navigation.diagnostics")
else:
    import logging

    logger = logging.getLogger("InVesalius.navigation.diagnostics")


class DeviceType(enum.Enum):
    """Enum for different device types."""

    TRACKER = 1
    ROBOT = 2
    SERIAL_PORT = 3
    PEDAL = 4
    NETWORKING = 5
    TFUS = 6


class DeviceStatus(enum.Enum):
    """Enum for device connection status."""

    UNKNOWN = 0
    DISCONNECTED = 1
    CONNECTING = 2
    CONNECTED = 3
    ERROR = 4
    READY = 5


class ConnectionEvent:
    """Record of a device connection event."""

    def __init__(
        self,
        device_type: DeviceType,
        status: DeviceStatus,
        message: str = "",
        details: Dict = None,
        timestamp: Optional[datetime.datetime] = None,
    ):
        self.device_type = device_type
        self.status = status
        self.message = message
        self.details = details or {}
        self.timestamp = timestamp or datetime.datetime.now()

    def to_dict(self) -> Dict:
        """Convert event to dictionary for serialization."""
        return {
            "device_type": self.device_type.name,
            "status": self.status.name,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ConnectionEvent":
        """Create event from dictionary."""
        return cls(
            device_type=DeviceType[data["device_type"]],
            status=DeviceStatus[data["status"]],
            message=data["message"],
            details=data["details"],
            timestamp=datetime.datetime.fromisoformat(data["timestamp"]),
        )

    def __str__(self) -> str:
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {self.device_type.name}: {self.status.name} - {self.message}"


class DiagnosticResult:
    """Result of a diagnostic test."""

    def __init__(
        self,
        device_type: DeviceType,
        test_name: str,
        passed: bool,
        message: str,
        details: Dict = None,
        timestamp: Optional[datetime.datetime] = None,
    ):
        self.device_type = device_type
        self.test_name = test_name
        self.passed = passed
        self.message = message
        self.details = details or {}
        self.timestamp = timestamp or datetime.datetime.now()

    def to_dict(self) -> Dict:
        """Convert result to dictionary for serialization."""
        return {
            "device_type": self.device_type.name,
            "test_name": self.test_name,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DiagnosticResult":
        """Create result from dictionary."""
        return cls(
            device_type=DeviceType[data["device_type"]],
            test_name=data["test_name"],
            passed=data["passed"],
            message=data["message"],
            details=data["details"],
            timestamp=datetime.datetime.fromisoformat(data["timestamp"]),
        )

    def __str__(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {self.device_type.name} - {self.test_name}: {status} - {self.message}"


class DeviceMonitor:
    """Monitor a specific device type."""

    def __init__(self, device_type: DeviceType, max_history: int = 100):
        self.device_type = device_type
        self.status = DeviceStatus.UNKNOWN
        self.last_update = datetime.datetime.now()
        self.connection_history = deque(maxlen=max_history)
        self.diagnostic_history = deque(maxlen=max_history)
        self.device_info = {}
        self.error_count = 0
        self.last_error = None
        self.last_diagnostic = None

    def update_status(self, status: DeviceStatus, message: str = "", details: Dict = None) -> None:
        """Update the device status and record the event."""
        self.status = status
        self.last_update = datetime.datetime.now()

        event = ConnectionEvent(
            device_type=self.device_type, status=status, message=message, details=details
        )

        self.connection_history.append(event)
        if status == DeviceStatus.ERROR:
            self.error_count += 1
            self.last_error = event

        # Log the event
        if HAS_ERROR_HANDLING:
            if status == DeviceStatus.ERROR:
                logger.error(f"{self.device_type.name} status update: {status.name} - {message}")
            else:
                logger.info(f"{self.device_type.name} status update: {status.name} - {message}")
        else:
            print(f"{self.device_type.name} status update: {status.name} - {message}")

        # Publish event for other components
        Publisher.sendMessage(
            "Device status updated",
            device_type=self.device_type,
            status=status,
            message=message,
            details=details,
        )

    def add_diagnostic_result(self, result: DiagnosticResult) -> None:
        """Add a diagnostic test result."""
        self.diagnostic_history.append(result)
        self.last_diagnostic = result

        # Log the result
        if HAS_ERROR_HANDLING:
            if result.passed:
                logger.info(f"Diagnostic {result.test_name} PASSED: {result.message}")
            else:
                logger.warning(f"Diagnostic {result.test_name} FAILED: {result.message}")
        else:
            status = "PASSED" if result.passed else "FAILED"
            print(f"Diagnostic {result.test_name} {status}: {result.message}")

        # Publish result for other components
        Publisher.sendMessage(
            "Diagnostic result added", device_type=self.device_type, result=result
        )


class DiagnosticsSystem(metaclass=Singleton):
    """Central system for device diagnostics and monitoring."""

    def __init__(self):
        self.monitors = {device_type: DeviceMonitor(device_type) for device_type in DeviceType}

        self.session_start_time = datetime.datetime.now()
        self.navigation_start_time = None
        self.is_navigation_active = False

        # Device references
        self.tracker = None
        self.robot = None

        self.log_file_path = self._setup_log_file()

        self._bind_events()

    def _setup_log_file(self) -> str:
        """Setup the log file for connection events."""
        try:
            # Get user's home directory and create InVesalius folder if it doesn't exist
            home_dir = os.path.expanduser("~")
            invesalius_dir = os.path.join(home_dir, ".invesalius")
            diagnostics_dir = os.path.join(invesalius_dir, "diagnostics")

            if not os.path.exists(diagnostics_dir):
                os.makedirs(diagnostics_dir)

            # Create log file with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(diagnostics_dir, f"connection_log_{timestamp}.json")

            # Initialize the log file with basic session info
            with open(log_file, "w") as f:
                json.dump(
                    {
                        "session_start": self.session_start_time.isoformat(),
                        "system_info": self._get_system_info(),
                        "events": [],
                    },
                    f,
                    indent=2,
                )

            return log_file

        except Exception as e:
            if HAS_ERROR_HANDLING:
                logger.error(f"Failed to setup log file: {str(e)}", exc_info=True)
            else:
                print(f"Failed to setup log file: {str(e)}")
            return None

    def _get_system_info(self) -> Dict:
        """Get system information for diagnostics."""
        info = {}

        try:
            import platform

            info["os"] = platform.platform()
            info["python"] = platform.python_version()

            session = ses.Session()
            info["invesalius_version"] = session.GetConfig("version")

            import psutil

            info["memory_total"] = psutil.virtual_memory().total
            info["cpu_count"] = psutil.cpu_count()

        except Exception as e:
            info["error"] = str(e)

        return info

    def _bind_events(self) -> None:
        """Bind to Publisher events."""
        # Navigation events
        Publisher.subscribe(self.on_navigation_start, "Start navigation")
        Publisher.subscribe(self.on_navigation_stop, "Stop navigation")

        # Tracker events
        Publisher.subscribe(self.on_tracker_connection, "Tracker changed")
        Publisher.subscribe(self.on_tracker_disconnect, "Disconnect tracker")

        # Robot events
        Publisher.subscribe(
            self.on_robot_status, "Robot to Neuronavigation: Robot connection status"
        )

        # Serial port events
        Publisher.subscribe(self.on_serial_connection, "Serial port connection")

        # Initialize device references
        self.tracker = Tracker()
        self.robot = Robot(self.tracker, None, None)  # Note: Navigation will be None here

    def update_device_status(
        self, device_type: DeviceType, status: DeviceStatus, message: str = "", details: Dict = None
    ) -> None:
        """Update the status of a device."""
        monitor = self.monitors[device_type]
        monitor.update_status(status, message, details)

        # Log the event to file
        self._log_event_to_file(monitor.connection_history[-1])

    def add_diagnostic_result(self, result: DiagnosticResult) -> None:
        """Add a diagnostic test result."""
        device_type = result.device_type
        monitor = self.monitors.get(device_type)
        if monitor:
            monitor.add_diagnostic_result(result)

    def run_diagnostics(self, device_type: DeviceType) -> List[DiagnosticResult]:
        """Run diagnostics on the specified device type.

        Args:
            device_type: The type of device to run diagnostics on

        Returns:
            List of diagnostic results
        """
        results = []

        if HAS_ERROR_HANDLING:
            logger.info(f"Running diagnostics for {device_type.name}")

        try:
            # Run common diagnostics based on device type
            if device_type == DeviceType.TRACKER:
                results.extend(self._run_tracker_diagnostics())
            elif device_type == DeviceType.ROBOT:
                results.extend(self._run_robot_diagnostics())
            elif device_type == DeviceType.SERIAL_PORT:
                results.extend(self._run_serial_diagnostics())
            elif device_type == DeviceType.NETWORKING:
                results.extend(self._run_network_diagnostics())
            elif device_type == DeviceType.PEDAL:
                results.extend(self._run_pedal_diagnostics())
            elif device_type == DeviceType.TFUS:
                results.extend(self._run_tfus_diagnostics())

            # Add a generic connectivity test result if no specific tests were run
            if not results:
                status = self.monitors[device_type].status

                result = DiagnosticResult(
                    device_type=device_type,
                    test_name="connectivity_check",
                    passed=(status == DeviceStatus.CONNECTED or status == DeviceStatus.READY),
                    message=f"Device is {status.name.lower()}.",
                    details={"status": status.name},
                )
                results.append(result)
                self.add_diagnostic_result(result)

        except Exception as e:
            # Add error result
            error_result = DiagnosticResult(
                device_type=device_type,
                test_name="diagnostic_system",
                passed=False,
                message=f"Error running diagnostics: {str(e)}",
                details={"error": str(e)},
            )
            results.append(error_result)
            self.add_diagnostic_result(error_result)

            if HAS_ERROR_HANDLING:
                logger.error(f"Error running diagnostics for {device_type.name}: {str(e)}")

        return results

    def _run_tracker_diagnostics(self) -> List[DiagnosticResult]:
        """Run diagnostics on the tracker device."""
        results = []

        # Check if tracker instance exists
        tracker_check = DiagnosticResult(
            device_type=DeviceType.TRACKER,
            test_name="tracker_instance",
            passed=self.tracker is not None,
            message="Tracker instance check" if self.tracker else "No tracker instance found",
            details={"tracker_instance": bool(self.tracker)},
        )
        results.append(tracker_check)
        self.add_diagnostic_result(tracker_check)

        # If no tracker instance, we can't run more tests
        if not tracker_check.passed:
            return results

        # Check if tracker is connected
        connected = False
        try:
            connected = self.tracker.IsTrackerConnected()
        except Exception as e:
            pass

        connection_check = DiagnosticResult(
            device_type=DeviceType.TRACKER,
            test_name="tracker_connection",
            passed=connected,
            message="Tracker is connected" if connected else "Tracker is not connected",
            details={"connected": connected},
        )
        results.append(connection_check)
        self.add_diagnostic_result(connection_check)

        # If not connected, we can't run more tests
        if not connected:
            return results

        # Try to get the number of tools
        try:
            num_tools = self.tracker.GetNumberOfTools()
            tool_check = DiagnosticResult(
                device_type=DeviceType.TRACKER,
                test_name="tracker_tools",
                passed=True,
                message=f"Tracker has {num_tools} tool(s)",
                details={"num_tools": num_tools},
            )
        except Exception as e:
            tool_check = DiagnosticResult(
                device_type=DeviceType.TRACKER,
                test_name="tracker_tools",
                passed=False,
                message=f"Error getting number of tools: {str(e)}",
                details={"error": str(e)},
            )

        results.append(tool_check)
        self.add_diagnostic_result(tool_check)

        return results

    def _run_robot_diagnostics(self) -> List[DiagnosticResult]:
        """Run diagnostics on the robot device."""
        results = []

        # Check if robot instance exists
        robot_check = DiagnosticResult(
            device_type=DeviceType.ROBOT,
            test_name="robot_instance",
            passed=self.robot is not None,
            message="Robot instance check" if self.robot else "No robot instance found",
            details={"robot_instance": bool(self.robot)},
        )
        results.append(robot_check)
        self.add_diagnostic_result(robot_check)

        # If no robot instance, we can't run more tests
        if not robot_check.passed:
            return results

        # Check if robot is connected
        connected = False
        try:
            connected = self.robot.IsConnected()
        except Exception as e:
            pass

        connection_check = DiagnosticResult(
            device_type=DeviceType.ROBOT,
            test_name="robot_connection",
            passed=connected,
            message="Robot is connected" if connected else "Robot is not connected",
            details={"connected": connected},
        )
        results.append(connection_check)
        self.add_diagnostic_result(connection_check)

        return results

    def _run_serial_diagnostics(self) -> List[DiagnosticResult]:
        """Run diagnostics on serial port connections."""
        # Simple check if any serial port connections are available
        results = []

        try:
            import serial.tools.list_ports

            ports = list(serial.tools.list_ports.comports())

            port_check = DiagnosticResult(
                device_type=DeviceType.SERIAL_PORT,
                test_name="available_ports",
                passed=len(ports) > 0,
                message=f"Found {len(ports)} serial port(s)" if ports else "No serial ports found",
                details={"ports": [port.device for port in ports]},
            )
        except Exception as e:
            port_check = DiagnosticResult(
                device_type=DeviceType.SERIAL_PORT,
                test_name="available_ports",
                passed=False,
                message=f"Error checking serial ports: {str(e)}",
                details={"error": str(e)},
            )

        results.append(port_check)
        self.add_diagnostic_result(port_check)

        return results

    def _run_network_diagnostics(self) -> List[DiagnosticResult]:
        """Run diagnostics on network connectivity."""
        results = []

        # Check if we can connect to common URLs
        urls = ["google.com", "github.com"]
        for url in urls:
            try:
                import socket

                socket.gethostbyname(url)
                result = DiagnosticResult(
                    device_type=DeviceType.NETWORKING,
                    test_name=f"connection_{url}",
                    passed=True,
                    message=f"Successfully connected to {url}",
                    details={"url": url},
                )
            except Exception as e:
                result = DiagnosticResult(
                    device_type=DeviceType.NETWORKING,
                    test_name=f"connection_{url}",
                    passed=False,
                    message=f"Failed to connect to {url}: {str(e)}",
                    details={"url": url, "error": str(e)},
                )

            results.append(result)
            self.add_diagnostic_result(result)

        return results

    def _run_pedal_diagnostics(self) -> List[DiagnosticResult]:
        """Run diagnostics on pedal device."""
        # Simple check if pedal is connected (to be implemented with actual pedal logic)
        result = DiagnosticResult(
            device_type=DeviceType.PEDAL,
            test_name="pedal_connection",
            passed=False,
            message="Pedal diagnostics not implemented yet",
            details={},
        )

        self.add_diagnostic_result(result)
        return [result]

    def _run_tfus_diagnostics(self) -> List[DiagnosticResult]:
        """Run diagnostics on TFUS device."""
        # Simple check if TFUS is connected (to be implemented with actual TFUS logic)
        result = DiagnosticResult(
            device_type=DeviceType.TFUS,
            test_name="tfus_connection",
            passed=False,
            message="TFUS diagnostics not implemented yet",
            details={},
        )

        self.add_diagnostic_result(result)
        return [result]

    def _log_event_to_file(self, event: ConnectionEvent) -> None:
        """Log a connection event to the log file."""
        if not self.log_file_path:
            return

        try:
            # Read existing data
            with open(self.log_file_path, "r") as f:
                data = json.load(f)

            # Add new event
            data["events"].append({"type": "connection_event", "data": event.to_dict()})

            # Write back to file
            with open(self.log_file_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            if HAS_ERROR_HANDLING:
                logger.error(f"Failed to log event to file: {str(e)}", exc_info=True)
            else:
                print(f"Failed to log event to file: {str(e)}")

    def _log_diagnostic_to_file(self, result: DiagnosticResult) -> None:
        """Log a diagnostic result to the log file."""
        if not self.log_file_path:
            return

        try:
            # Read existing data
            with open(self.log_file_path, "r") as f:
                data = json.load(f)

            # Add new diagnostic
            data["events"].append({"type": "diagnostic_result", "data": result.to_dict()})

            # Write back to file
            with open(self.log_file_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            if HAS_ERROR_HANDLING:
                logger.error(f"Failed to log diagnostic to file: {str(e)}", exc_info=True)
            else:
                print(f"Failed to log diagnostic to file: {str(e)}")

    # Navigation event handlers
    def on_navigation_start(self) -> None:
        """Handle navigation start event."""
        self.navigation_start_time = datetime.datetime.now()
        self.is_navigation_active = True

        message = "Navigation session started"
        self._check_device_readiness()

        # Log the navigation start for all devices
        for device_type, monitor in self.monitors.items():
            if monitor.status == DeviceStatus.CONNECTED:
                self.update_device_status(device_type, DeviceStatus.READY, message=message)

    def on_navigation_stop(self) -> None:
        """Handle navigation stop event."""
        self.is_navigation_active = False

        duration = None
        if self.navigation_start_time:
            duration = (datetime.datetime.now() - self.navigation_start_time).total_seconds()

        message = (
            f"Navigation session ended (duration: {duration:.1f}s)"
            if duration
            else "Navigation session ended"
        )

        # Log the navigation stop for all devices
        for device_type, monitor in self.monitors.items():
            if monitor.status in [DeviceStatus.READY, DeviceStatus.CONNECTED]:
                self.update_device_status(device_type, DeviceStatus.CONNECTED, message=message)

    # Tracker event handlers
    def on_tracker_connection(self) -> None:
        """Handle tracker connection event."""
        if self.tracker.IsTrackerInitialized():
            device_info = {
                "tracker_id": self.tracker.tracker_id,
                "tracker_type": tc.GetTrackerType(self.tracker.tracker_id),
            }

            self.monitors[DeviceType.TRACKER].device_info = device_info

            self.update_device_status(
                DeviceType.TRACKER,
                DeviceStatus.CONNECTED,
                message=f"Connected to tracker: {device_info['tracker_type']}",
                details=device_info,
            )

            # Run diagnostic tests
            self.run_diagnostics(DeviceType.TRACKER)
        else:
            self.update_device_status(
                DeviceType.TRACKER,
                DeviceStatus.DISCONNECTED,
                message="Tracker disconnected or not initialized",
            )

    def on_tracker_disconnect(self) -> None:
        """Handle tracker disconnect event."""
        self.update_device_status(
            DeviceType.TRACKER, DeviceStatus.DISCONNECTED, message="Tracker disconnected"
        )

    # Robot event handlers
    def on_robot_status(self, data) -> None:
        """Handle robot status event."""
        if data == "Connected":
            device_info = {"robot_ip": self.robot.robot_ip, "coil_name": self.robot.coil_name}

            self.monitors[DeviceType.ROBOT].device_info = device_info

            self.update_device_status(
                DeviceType.ROBOT,
                DeviceStatus.CONNECTED,
                message=f"Connected to robot at IP: {self.robot.robot_ip}",
                details=device_info,
            )

            # Run diagnostic tests
            self.run_diagnostics(DeviceType.ROBOT)
        else:
            self.update_device_status(
                DeviceType.ROBOT,
                DeviceStatus.DISCONNECTED,
                message=f"Robot connection status: {data}",
            )

    # Serial port event handlers
    def on_serial_connection(self, state) -> None:
        """Handle serial port connection event."""
        if state:
            self.update_device_status(
                DeviceType.SERIAL_PORT, DeviceStatus.CONNECTED, message="Serial port connected"
            )
        else:
            self.update_device_status(
                DeviceType.SERIAL_PORT,
                DeviceStatus.DISCONNECTED,
                message="Serial port disconnected",
            )

    def _check_device_readiness(self) -> None:
        """Check if all required devices are ready for navigation."""
        # Check tracker
        if not self.tracker.IsTrackerInitialized():
            self.update_device_status(
                DeviceType.TRACKER,
                DeviceStatus.ERROR,
                message="Tracker is required for navigation but not initialized",
                details={"fix": "Connect a tracker device in the preferences panel"},
            )

    def get_device_status_summary(self) -> Dict:
        """Get a summary of the status of all devices."""
        summary = {}

        for device_type, monitor in self.monitors.items():
            summary[device_type.name] = {
                "status": monitor.status.name,
                "last_update": monitor.last_update.isoformat(),
                "error_count": monitor.error_count,
                "device_info": monitor.device_info,
            }

            if monitor.last_error:
                summary[device_type.name]["last_error"] = {
                    "message": monitor.last_error.message,
                    "timestamp": monitor.last_error.timestamp.isoformat(),
                }

            if monitor.last_diagnostic:
                summary[device_type.name]["last_diagnostic"] = {
                    "test_name": monitor.last_diagnostic.test_name,
                    "passed": monitor.last_diagnostic.passed,
                    "message": monitor.last_diagnostic.message,
                    "timestamp": monitor.last_diagnostic.timestamp.isoformat(),
                }

        return summary

    def get_connection_history(self, device_type: DeviceType = None) -> List[ConnectionEvent]:
        """Get the connection history for a device or all devices."""
        if device_type:
            return list(self.monitors[device_type].connection_history)

        # Gather all events and sort by timestamp
        all_events = []
        for monitor in self.monitors.values():
            all_events.extend(list(monitor.connection_history))

        return sorted(all_events, key=lambda e: e.timestamp)

    def get_diagnostic_history(self, device_type: DeviceType = None) -> List[DiagnosticResult]:
        """Get the diagnostic history for a device or all devices."""
        if device_type:
            return list(self.monitors[device_type].diagnostic_history)

        # Gather all diagnostics and sort by timestamp
        all_diagnostics = []
        for monitor in self.monitors.values():
            all_diagnostics.extend(list(monitor.diagnostic_history))

        return sorted(all_diagnostics, key=lambda d: d.timestamp)


# Helper function to get the diagnostics system
def get_diagnostics_system() -> DiagnosticsSystem:
    """Get the singleton instance of the diagnostics system.

    Returns:
        DiagnosticsSystem: The singleton instance of the diagnostics system
    """
    return DiagnosticsSystem()


def update_device_status(
    device_type: DeviceType, status: DeviceStatus, message: str = "", details: Dict = None
) -> None:
    """Update the status of a device."""
    get_diagnostics_system().update_device_status(device_type, status, message, details)


def add_diagnostic_result(result: DiagnosticResult) -> None:
    """Add a diagnostic test result."""
    get_diagnostics_system().add_diagnostic_result(result)


def run_all_diagnostics() -> List[DiagnosticResult]:
    """Run all diagnostic tests and return the results."""
    return get_diagnostics_system().run_all_diagnostics()


def get_device_status_summary() -> Dict:
    """Get a summary of the status of all devices."""
    return get_diagnostics_system().get_device_status_summary()
