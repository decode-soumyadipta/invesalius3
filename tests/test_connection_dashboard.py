#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import os
import sys
import unittest
from unittest import mock

# Add the parent directory to the path so we can import invesalius
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from invesalius.navigation.diagnostics import (
    ConnectionEvent,
    DeviceMonitor,
    DeviceStatus,
    DeviceType,
    DiagnosticResult,
    DiagnosticsSystem,
    get_diagnostics_system,
)


class TestConnectionEvent(unittest.TestCase):
    """Test ConnectionEvent class."""

    def test_create_event(self):
        """Test creating a connection event."""
        event = ConnectionEvent(
            device_type=DeviceType.TRACKER,
            status=DeviceStatus.CONNECTED,
            message="Tracker connected",
            details={"tracker_id": 1},
        )

        self.assertEqual(event.device_type, DeviceType.TRACKER)
        self.assertEqual(event.status, DeviceStatus.CONNECTED)
        self.assertEqual(event.message, "Tracker connected")
        self.assertEqual(event.details, {"tracker_id": 1})

    def test_to_dict(self):
        """Test converting event to dictionary."""
        event = ConnectionEvent(
            device_type=DeviceType.TRACKER,
            status=DeviceStatus.CONNECTED,
            message="Tracker connected",
            details={"tracker_id": 1},
        )

        data = event.to_dict()

        self.assertEqual(data["device_type"], "TRACKER")
        self.assertEqual(data["status"], "CONNECTED")
        self.assertEqual(data["message"], "Tracker connected")
        self.assertEqual(data["details"], {"tracker_id": 1})

    def test_from_dict(self):
        """Test creating event from dictionary."""
        data = {
            "device_type": "TRACKER",
            "status": "CONNECTED",
            "message": "Tracker connected",
            "details": {"tracker_id": 1},
            "timestamp": "2023-01-01T12:00:00",
        }

        event = ConnectionEvent.from_dict(data)

        self.assertEqual(event.device_type, DeviceType.TRACKER)
        self.assertEqual(event.status, DeviceStatus.CONNECTED)
        self.assertEqual(event.message, "Tracker connected")
        self.assertEqual(event.details, {"tracker_id": 1})


class TestDiagnosticResult(unittest.TestCase):
    """Test DiagnosticResult class."""

    def test_create_result(self):
        """Test creating a diagnostic result."""
        result = DiagnosticResult(
            device_type=DeviceType.TRACKER,
            test_name="tracker_connection",
            passed=True,
            message="Tracker connection successful",
            details={"tracker_id": 1},
        )

        self.assertEqual(result.device_type, DeviceType.TRACKER)
        self.assertEqual(result.test_name, "tracker_connection")
        self.assertTrue(result.passed)
        self.assertEqual(result.message, "Tracker connection successful")
        self.assertEqual(result.details, {"tracker_id": 1})

    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = DiagnosticResult(
            device_type=DeviceType.TRACKER,
            test_name="tracker_connection",
            passed=True,
            message="Tracker connection successful",
            details={"tracker_id": 1},
        )

        data = result.to_dict()

        self.assertEqual(data["device_type"], "TRACKER")
        self.assertEqual(data["test_name"], "tracker_connection")
        self.assertEqual(data["passed"], True)
        self.assertEqual(data["message"], "Tracker connection successful")
        self.assertEqual(data["details"], {"tracker_id": 1})

    def test_from_dict(self):
        """Test creating result from dictionary."""
        data = {
            "device_type": "TRACKER",
            "test_name": "tracker_connection",
            "passed": True,
            "message": "Tracker connection successful",
            "details": {"tracker_id": 1},
            "timestamp": "2023-01-01T12:00:00",
        }

        result = DiagnosticResult.from_dict(data)

        self.assertEqual(result.device_type, DeviceType.TRACKER)
        self.assertEqual(result.test_name, "tracker_connection")
        self.assertTrue(result.passed)
        self.assertEqual(result.message, "Tracker connection successful")
        self.assertEqual(result.details, {"tracker_id": 1})


class TestDeviceMonitor(unittest.TestCase):
    """Test DeviceMonitor class."""

    def test_create_monitor(self):
        """Test creating a device monitor."""
        monitor = DeviceMonitor(DeviceType.TRACKER)

        self.assertEqual(monitor.device_type, DeviceType.TRACKER)
        self.assertEqual(monitor.status, DeviceStatus.UNKNOWN)
        self.assertEqual(len(monitor.connection_history), 0)
        self.assertEqual(len(monitor.diagnostic_history), 0)

    @mock.patch("invesalius.pubsub.pub.sendMessage")
    def test_update_status(self, mock_send_message):
        """Test updating device status."""
        monitor = DeviceMonitor(DeviceType.TRACKER)

        monitor.update_status(DeviceStatus.CONNECTED, "Tracker connected", {"tracker_id": 1})

        self.assertEqual(monitor.status, DeviceStatus.CONNECTED)
        self.assertEqual(len(monitor.connection_history), 1)

        event = monitor.connection_history[0]
        self.assertEqual(event.device_type, DeviceType.TRACKER)
        self.assertEqual(event.status, DeviceStatus.CONNECTED)
        self.assertEqual(event.message, "Tracker connected")
        self.assertEqual(event.details, {"tracker_id": 1})

        # Check that the message was sent
        mock_send_message.assert_called_once_with(
            "Device status updated",
            device_type=DeviceType.TRACKER,
            status=DeviceStatus.CONNECTED,
            message="Tracker connected",
            details={"tracker_id": 1},
        )

    @mock.patch("invesalius.pubsub.pub.sendMessage")
    def test_add_diagnostic_result(self, mock_send_message):
        """Test adding a diagnostic result."""
        monitor = DeviceMonitor(DeviceType.TRACKER)

        result = DiagnosticResult(
            device_type=DeviceType.TRACKER,
            test_name="tracker_connection",
            passed=True,
            message="Tracker connection successful",
            details={"tracker_id": 1},
        )

        monitor.add_diagnostic_result(result)

        self.assertEqual(len(monitor.diagnostic_history), 1)
        self.assertEqual(monitor.last_diagnostic, result)

        # Check that the message was sent
        mock_send_message.assert_called_once_with(
            "Diagnostic result added", device_type=DeviceType.TRACKER, result=result
        )


class TestDiagnosticsSystem(unittest.TestCase):
    """Test DiagnosticsSystem class."""

    def setUp(self):
        """Set up for tests."""
        # Create a mock for the DiagnosticsSystem singleton
        patcher = mock.patch("invesalius.navigation.diagnostics.DiagnosticsSystem", autospec=True)
        self.mock_diagnostics_class = patcher.start()
        self.addCleanup(patcher.stop)

        # Create a mock instance
        self.mock_diagnostics = mock.MagicMock()
        self.mock_diagnostics_class.return_value = self.mock_diagnostics

    def test_get_diagnostics_system(self):
        """Test getting the diagnostics system."""
        diagnostics = get_diagnostics_system()

        # Check that the singleton was called
        self.mock_diagnostics_class.assert_called_once()

        # Check that we got the mock instance
        self.assertEqual(diagnostics, self.mock_diagnostics)

    def test_update_device_status(self):
        """Test updating device status."""
        # Setup the mock monitor
        mock_monitor = mock.MagicMock()
        self.mock_diagnostics.monitors = {DeviceType.TRACKER: mock_monitor}

        # Call the method
        self.mock_diagnostics.update_device_status(
            DeviceType.TRACKER, DeviceStatus.CONNECTED, "Tracker connected", {"tracker_id": 1}
        )

        # Check that the monitor's update_status was called
        mock_monitor.update_status.assert_called_once_with(
            DeviceStatus.CONNECTED, "Tracker connected", {"tracker_id": 1}
        )

    def test_add_diagnostic_result(self):
        """Test adding a diagnostic result."""
        # Setup the mock monitor
        mock_monitor = mock.MagicMock()
        self.mock_diagnostics.monitors = {DeviceType.TRACKER: mock_monitor}

        # Create a result
        result = DiagnosticResult(
            device_type=DeviceType.TRACKER,
            test_name="tracker_connection",
            passed=True,
            message="Tracker connection successful",
            details={"tracker_id": 1},
        )

        # Call the method
        self.mock_diagnostics.add_diagnostic_result(result)

        # Check that the monitor's add_diagnostic_result was called
        mock_monitor.add_diagnostic_result.assert_called_once_with(result)


if __name__ == "__main__":
    unittest.main()
