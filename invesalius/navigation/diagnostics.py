#!/usr/bin/env python3
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

"""
Module for monitoring and diagnostics of navigation devices.

This module provides functionality to:
1. Monitor the connection status of navigation devices
2. Run diagnostic tests on connected devices
3. Provide troubleshooting information and suggestions
4. Log connection events and statistics
"""

import datetime
import enum
import json
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import numpy as np

import invesalius.constants as const
import invesalius.data.coordinates as dco
import invesalius.data.tracker_connection as tc
import invesalius.session as ses
from invesalius.enhanced_logging import get_logger
from invesalius.error_handling import (
    ErrorCategory,
    ErrorSeverity,
    InVesaliusException,
    NavigationError
)
from invesalius.i18n import tr as _
from invesalius.pubsub import pub as Publisher
from invesalius.utils import Singleton

# Initialize a logger for the diagnostics module
logger = get_logger("navigation.diagnostics")

class DeviceType(enum.Enum):
    """Types of devices that can be monitored."""
    TRACKER = "tracker"
    ROBOT = "robot"
    STIMULATOR = "stimulator"
    SERIAL_PORT = "serial_port"
    TFUS = "tfus"  # Transcranial Focused Ultrasound

class ConnectionStatus(enum.Enum):
    """Connection status for devices."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    UNAVAILABLE = "unavailable"  # Device driver not available

class DiagnosticStatus(enum.Enum):
    """Status of diagnostic tests."""
    NOT_RUN = "not_run"
    RUNNING = "running"
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"

class ConnectionEvent:
    """Class to represent a connection event."""
    
    def __init__(
        self,
        device_type: DeviceType,
        status: ConnectionStatus,
        timestamp: Optional[datetime.datetime] = None,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None
    ):
        """
        Initialize a connection event.
        
        Parameters:
        -----------
        device_type : DeviceType
            The type of device this event is for
        status : ConnectionStatus
            The connection status
        timestamp : datetime, optional
            The timestamp of the event, defaults to current time
        details : dict, optional
            Additional details about the event
        error : Exception, optional
            Any error that occurred
        """
        self.device_type = device_type
        self.status = status
        self.timestamp = timestamp or datetime.datetime.now()
        self.details = details or {}
        self.error = error
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert the event to a dictionary for serialization."""
        return {
            "device_type": self.device_type.value,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "error": str(self.error) if self.error else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConnectionEvent":
        """Create an event from a dictionary."""
        return cls(
            device_type=DeviceType(data["device_type"]),
            status=ConnectionStatus(data["status"]),
            timestamp=datetime.datetime.fromisoformat(data["timestamp"]),
            details=data["details"],
            error=Exception(data["error"]) if data["error"] else None
        )

class DiagnosticTest:
    """Base class for diagnostic tests."""
    
    def __init__(self, device_type: DeviceType, name: str, description: str):
        """
        Initialize a diagnostic test.
        
        Parameters:
        -----------
        device_type : DeviceType
            The type of device this test is for
        name : str
            The name of the test
        description : str
            A description of what the test checks
        """
        self.device_type = device_type
        self.name = name
        self.description = description
        self.status = DiagnosticStatus.NOT_RUN
        self.results: Dict[str, Any] = {}
        self.error: Optional[Exception] = None
        self.recommendations: List[str] = []
        
    def run(self, device: Any) -> DiagnosticStatus:
        """
        Run the diagnostic test on the specified device.
        
        This is a base method that should be overridden by subclasses.
        
        Parameters:
        -----------
        device : Any
            The device to test
            
        Returns:
        --------
        DiagnosticStatus
            The status of the test after running
        """
        try:
            self.status = DiagnosticStatus.RUNNING
            # Subclasses should override this method
            self.status = DiagnosticStatus.PASSED
        except Exception as e:
            self.error = e
            self.status = DiagnosticStatus.FAILED
            logger.error(f"Diagnostic test {self.name} failed: {str(e)}", exc_info=True)
        
        return self.status
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the test to a dictionary for serialization."""
        return {
            "device_type": self.device_type.value,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "results": self.results,
            "error": str(self.error) if self.error else None,
            "recommendations": self.recommendations
        }

class TrackerConnectionTest(DiagnosticTest):
    """Test to check the connection to a tracker."""
    
    def __init__(self):
        super().__init__(
            device_type=DeviceType.TRACKER,
            name="Tracker Connection",
            description=_("Checks if the tracker can establish a connection")
        )
    
    def run(self, tracker: Any) -> DiagnosticStatus:
        """Run the tracker connection test."""
        try:
            self.status = DiagnosticStatus.RUNNING
            
            if not tracker.tracker_connection:
                self.status = DiagnosticStatus.FAILED
                self.results["message"] = _("No tracker connection object found")
                self.recommendations.append(_("Select a tracker type in the navigation settings"))
                return self.status
            
            if not tracker.tracker_connected:
                self.status = DiagnosticStatus.FAILED
                self.results["message"] = _("Tracker is not connected")
                self.recommendations.extend([
                    _("Check that the tracker device is powered on"),
                    _("Check that the tracker device is connected to the computer"),
                    _("Try a different USB port"),
                    _("Check that the correct tracker is selected in settings")
                ])
                return self.status
            
            # If we got here, the test passed
            self.status = DiagnosticStatus.PASSED
            self.results["message"] = _("Tracker is connected")
            self.results["tracker_id"] = tracker.tracker_id
            
            config = tracker.tracker_connection.GetConfiguration() if tracker.tracker_connection else None
            if config:
                self.results["configuration"] = config
            
        except Exception as e:
            self.error = e
            self.status = DiagnosticStatus.FAILED
            self.results["message"] = _("Error checking tracker connection")
            self.recommendations.append(_("Check the system logs for more information"))
            logger.error(f"Tracker connection test failed: {str(e)}", exc_info=True)
        
        return self.status

class TrackerFiducialTest(DiagnosticTest):
    """Test to check if tracker fiducials are properly set."""
    
    def __init__(self):
        super().__init__(
            device_type=DeviceType.TRACKER,
            name="Tracker Fiducials",
            description=_("Checks if tracker fiducials are properly set")
        )
    
    def run(self, tracker: Any) -> DiagnosticStatus:
        """Run the tracker fiducial test."""
        try:
            self.status = DiagnosticStatus.RUNNING
            
            if not tracker.AreTrackerFiducialsSet():
                self.status = DiagnosticStatus.WARNING
                self.results["message"] = _("Tracker fiducials are not fully set")
                
                # Check which fiducials are set and which are not
                set_fiducials = []
                unset_fiducials = []
                for i in range(3):
                    if tracker.IsTrackerFiducialSet(i):
                        set_fiducials.append(i)
                    else:
                        unset_fiducials.append(i)
                
                self.results["set_fiducials"] = set_fiducials
                self.results["unset_fiducials"] = unset_fiducials
                
                if len(set_fiducials) == 0:
                    self.recommendations.append(_("Complete the tracker registration process"))
                else:
                    self.recommendations.append(_("Set the remaining tracker fiducials"))
                
                return self.status
            
            # If we got here, the test passed
            self.status = DiagnosticStatus.PASSED
            self.results["message"] = _("All tracker fiducials are set")
            
            # Add fiducial coordinates
            fiducials, _ = tracker.GetTrackerFiducials()
            self.results["fiducials"] = fiducials.tolist()
            
        except Exception as e:
            self.error = e
            self.status = DiagnosticStatus.FAILED
            self.results["message"] = _("Error checking tracker fiducials")
            self.recommendations.append(_("Try resetting and reconfiguring the tracker fiducials"))
            logger.error(f"Tracker fiducial test failed: {str(e)}", exc_info=True)
        
        return self.status

class TrackerCoordinateTest(DiagnosticTest):
    """Test to check if tracker can provide valid coordinates."""
    
    def __init__(self):
        super().__init__(
            device_type=DeviceType.TRACKER,
            name="Tracker Coordinates",
            description=_("Checks if tracker provides valid coordinates")
        )
    
    def run(self, tracker: Any) -> DiagnosticStatus:
        """Run the tracker coordinate test."""
        try:
            self.status = DiagnosticStatus.RUNNING
            
            if not tracker.tracker_connected:
                self.status = DiagnosticStatus.FAILED
                self.results["message"] = _("Tracker is not connected")
                self.recommendations.append(_("Connect the tracker before testing coordinates"))
                return self.status
            
            # Try to get coordinates
            try:
                marker_visibilities, coord, coord_raw = tracker.GetTrackerCoordinates(
                    ref_mode_id=const.REFERENCE_MODE,
                    n_samples=1
                )
                
                # Check if any markers are visible
                if not any(marker_visibilities):
                    self.status = DiagnosticStatus.WARNING
                    self.results["message"] = _("No tracking markers are visible")
                    self.recommendations.extend([
                        _("Ensure tracking markers are in the tracker's field of view"),
                        _("Check that markers are not covered or damaged"),
                        _("Check that the room lighting is appropriate for the tracker")
                    ])
                    return self.status
                
                # Check for NaN or infinite values in coordinates
                if np.isnan(coord).any() or np.isinf(coord).any():
                    self.status = DiagnosticStatus.WARNING
                    self.results["message"] = _("Tracker returned invalid coordinates")
                    self.results["coord"] = coord.tolist()
                    self.recommendations.append(_("Try repositioning the tracking markers"))
                    return self.status
                
                # If we got here, the test passed
                self.status = DiagnosticStatus.PASSED
                self.results["message"] = _("Tracker is providing valid coordinates")
                self.results["marker_visibilities"] = marker_visibilities
                self.results["coord"] = coord.tolist()
                
            except Exception as e:
                self.status = DiagnosticStatus.FAILED
                self.error = e
                self.results["message"] = _("Error getting tracker coordinates")
                self.recommendations.append(_("Check that the tracker is properly connected and configured"))
                logger.error(f"Error getting tracker coordinates: {str(e)}", exc_info=True)
                return self.status
            
        except Exception as e:
            self.error = e
            self.status = DiagnosticStatus.FAILED
            self.results["message"] = _("Error testing tracker coordinates")
            self.recommendations.append(_("Check the system logs for more information"))
            logger.error(f"Tracker coordinate test failed: {str(e)}", exc_info=True)
        
        return self.status

class RobotConnectionTest(DiagnosticTest):
    """Test to check the connection to a robot."""
    
    def __init__(self):
        super().__init__(
            device_type=DeviceType.ROBOT,
            name="Robot Connection",
            description=_("Checks if the robot can establish a connection")
        )
    
    def run(self, robot: Any) -> DiagnosticStatus:
        """Run the robot connection test."""
        try:
            self.status = DiagnosticStatus.RUNNING
            
            if not robot.robot_ip:
                self.status = DiagnosticStatus.FAILED
                self.results["message"] = _("No robot IP address configured")
                self.recommendations.append(_("Configure the robot IP address in the navigation settings"))
                return self.status
            
            if not robot.is_robot_connected:
                self.status = DiagnosticStatus.FAILED
                self.results["message"] = _("Robot is not connected")
                self.recommendations.extend([
                    _("Check that the robot is powered on"),
                    _("Check network connectivity to the robot IP"),
                    _("Verify that the robot service is running"),
                    _("Check that the IP address is correct")
                ])
                return self.status
            
            # If we got here, the test passed
            self.status = DiagnosticStatus.PASSED
            self.results["message"] = _("Robot is connected")
            self.results["robot_ip"] = robot.robot_ip
            
            if robot.coil_name:
                self.results["coil_name"] = robot.coil_name
            
        except Exception as e:
            self.error = e
            self.status = DiagnosticStatus.FAILED
            self.results["message"] = _("Error checking robot connection")
            self.recommendations.append(_("Check the system logs for more information"))
            logger.error(f"Robot connection test failed: {str(e)}", exc_info=True)
        
        return self.status

class RobotRegistrationTest(DiagnosticTest):
    """Test to check if robot registration is properly set up."""
    
    def __init__(self):
        super().__init__(
            device_type=DeviceType.ROBOT,
            name="Robot Registration",
            description=_("Checks if robot registration is properly set up")
        )
    
    def run(self, robot: Any) -> DiagnosticStatus:
        """Run the robot registration test."""
        try:
            self.status = DiagnosticStatus.RUNNING
            
            if not robot.is_robot_connected:
                self.status = DiagnosticStatus.FAILED
                self.results["message"] = _("Robot is not connected")
                self.recommendations.append(_("Connect to the robot before checking registration"))
                return self.status
            
            if robot.matrix_tracker_to_robot is None:
                self.status = DiagnosticStatus.WARNING
                self.results["message"] = _("Robot registration matrix not set")
                self.recommendations.append(_("Complete the robot registration process"))
                return self.status
            
            # Check if the matrix is valid (not containing NaN or Inf)
            matrix = robot.matrix_tracker_to_robot
            if np.isnan(matrix).any() or np.isinf(matrix).any():
                self.status = DiagnosticStatus.WARNING
                self.results["message"] = _("Robot registration matrix contains invalid values")
                self.recommendations.append(_("Re-do the robot registration process"))
                return self.status
            
            # If we got here, the test passed
            self.status = DiagnosticStatus.PASSED
            self.results["message"] = _("Robot registration is properly set up")
            
        except Exception as e:
            self.error = e
            self.status = DiagnosticStatus.FAILED
            self.results["message"] = _("Error checking robot registration")
            self.recommendations.append(_("Check the system logs for more information"))
            logger.error(f"Robot registration test failed: {str(e)}", exc_info=True)
        
        return self.status

class DiagnosticsManager(metaclass=Singleton):
    """Manager for device diagnostics and connection monitoring."""
    
    def __init__(self):
        """Initialize the diagnostics manager."""
        self.status_history: Dict[DeviceType, List[ConnectionEvent]] = {
            device_type: [] for device_type in DeviceType
        }
        
        self.current_status: Dict[DeviceType, ConnectionStatus] = {
            device_type: ConnectionStatus.DISCONNECTED for device_type in DeviceType
        }
        
        self.diagnostic_tests: Dict[DeviceType, List[DiagnosticTest]] = {
            DeviceType.TRACKER: [
                TrackerConnectionTest(),
                TrackerFiducialTest(),
                TrackerCoordinateTest()
            ],
            DeviceType.ROBOT: [
                RobotConnectionTest(),
                RobotRegistrationTest()
            ],
            # Additional device types can be added here
        }
        
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitor_event = threading.Event()
        self.monitor_interval = 5.0  # seconds
        
        # Setup event bindings
        self._bind_events()
        
        # Load status history from session
        self._load_state()
    
    def _bind_events(self):
        """Bind to relevant events."""
        # Device connection events
        Publisher.subscribe(self.OnTrackerStatus, "Update tracker status")
        Publisher.subscribe(self.OnRobotStatus, "Robot to Neuronavigation: Robot connection status")
        
        # Session events
        Publisher.subscribe(self.OnCloseProject, "Close project")
    
    def _load_state(self):
        """Load diagnostics state from session."""
        try:
            session = ses.Session()
            state = session.GetState("diagnostics")
            
            if state is None:
                return
            
            # Load connection events history
            if "status_history" in state:
                for device_type_str, events_data in state["status_history"].items():
                    try:
                        device_type = DeviceType(device_type_str)
                        events = [ConnectionEvent.from_dict(event_data) for event_data in events_data]
                        self.status_history[device_type] = events
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Error loading diagnostics history for {device_type_str}: {str(e)}")
            
            logger.debug("Loaded diagnostics state from session")
            
        except Exception as e:
            logger.error(f"Error loading diagnostics state: {str(e)}", exc_info=True)
    
    def _save_state(self):
        """Save diagnostics state to session."""
        try:
            session = ses.Session()
            
            # Convert status history to serializable format
            status_history_dict = {}
            for device_type, events in self.status_history.items():
                status_history_dict[device_type.value] = [event.to_dict() for event in events]
            
            state = {
                "status_history": status_history_dict
            }
            
            session.SetState("diagnostics", state)
            logger.debug("Saved diagnostics state to session")
            
        except Exception as e:
            logger.error(f"Error saving diagnostics state: {str(e)}", exc_info=True)
    
    def start_monitoring(self):
        """Start the connection monitoring thread."""
        if self.monitor_thread is not None and self.monitor_thread.is_alive():
            return
        
        self.monitor_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_connections, name="DiagnosticsMonitor")
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info("Started connection monitoring thread")
    
    def stop_monitoring(self):
        """Stop the connection monitoring thread."""
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            return
        
        self.monitor_event.set()
        self.monitor_thread.join(timeout=2.0)
        self.monitor_thread = None
        logger.info("Stopped connection monitoring thread")
    
    def _monitor_connections(self):
        """Monitor the connection status of devices."""
        logger.debug("Connection monitoring thread started")
        
        while not self.monitor_event.is_set():
            # Request status updates from devices
            Publisher.sendMessage("Neuronavigation to Robot: Check connection robot")
            
            # Sleep for the monitoring interval
            self.monitor_event.wait(self.monitor_interval)
    
    def record_event(self, event: ConnectionEvent):
        """
        Record a connection event.
        
        Parameters:
        -----------
        event : ConnectionEvent
            The event to record
        """
        logger.debug(f"Recording {event.device_type.value} event: {event.status.value}")
        
        # Update current status
        self.current_status[event.device_type] = event.status
        
        # Add to history (limit to 100 events per device)
        self.status_history[event.device_type].append(event)
        if len(self.status_history[event.device_type]) > 100:
            self.status_history[event.device_type] = self.status_history[event.device_type][-100:]
        
        # Save the updated state
        self._save_state()
        
        # Notify subscribers
        Publisher.sendMessage(
            "Update device status",
            device_type=event.device_type,
            status=event.status,
            details=event.details
        )
    
    def run_diagnostic_tests(self, device_type: DeviceType, device: Any) -> List[DiagnosticTest]:
        """
        Run diagnostic tests for a specific device.
        
        Parameters:
        -----------
        device_type : DeviceType
            The type of device to test
        device : Any
            The device instance to test
            
        Returns:
        --------
        List[DiagnosticTest]
            The list of completed diagnostic tests
        """
        logger.info(f"Running diagnostic tests for {device_type.value}")
        
        tests = self.diagnostic_tests.get(device_type, [])
        for test in tests:
            try:
                test.run(device)
            except Exception as e:
                logger.error(f"Error running diagnostic test {test.name}: {str(e)}", exc_info=True)
                test.status = DiagnosticStatus.FAILED
                test.error = e
                test.results["message"] = _("Error running test")
        
        # Notify subscribers
        Publisher.sendMessage(
            "Diagnostic tests completed",
            device_type=device_type,
            tests=tests
        )
        
        return tests
    
    def get_connection_history(self, device_type: DeviceType) -> List[ConnectionEvent]:
        """
        Get the connection history for a device.
        
        Parameters:
        -----------
        device_type : DeviceType
            The type of device
            
        Returns:
        --------
        List[ConnectionEvent]
            The connection history events
        """
        return self.status_history.get(device_type, [])
    
    def get_current_status(self, device_type: DeviceType) -> ConnectionStatus:
        """
        Get the current connection status for a device.
        
        Parameters:
        -----------
        device_type : DeviceType
            The type of device
            
        Returns:
        --------
        ConnectionStatus
            The current connection status
        """
        return self.current_status.get(device_type, ConnectionStatus.DISCONNECTED)
    
    def OnTrackerStatus(self, status: bool):
        """
        Handle tracker status updates.
        
        Parameters:
        -----------
        status : bool
            True if connected, False otherwise
        """
        event_status = ConnectionStatus.CONNECTED if status else ConnectionStatus.DISCONNECTED
        
        event = ConnectionEvent(
            device_type=DeviceType.TRACKER,
            status=event_status,
            details={"connected": status}
        )
        
        self.record_event(event)
    
    def OnRobotStatus(self, status: str):
        """
        Handle robot status updates.
        
        Parameters:
        -----------
        status : str
            Connection status message
        """
        if status == "Connected":
            event_status = ConnectionStatus.CONNECTED
        else:
            event_status = ConnectionStatus.ERROR if "Error" in status else ConnectionStatus.DISCONNECTED
        
        event = ConnectionEvent(
            device_type=DeviceType.ROBOT,
            status=event_status,
            details={"status_message": status}
        )
        
        self.record_event(event)
    
    def OnCloseProject(self):
        """Handle project close event."""
        # Stop monitoring
        self.stop_monitoring()
        
        # Reset statuses
        for device_type in DeviceType:
            self.current_status[device_type] = ConnectionStatus.DISCONNECTED
            
            # Record disconnection event
            event = ConnectionEvent(
                device_type=device_type,
                status=ConnectionStatus.DISCONNECTED,
                details={"reason": "project_closed"}
            )
            self.record_event(event)

# Create a singleton instance
diagnostics_manager = DiagnosticsManager()

# Convenience functions
def run_diagnostic_tests(device_type: DeviceType, device: Any) -> List[DiagnosticTest]:
    """Run diagnostic tests for a device."""
    return diagnostics_manager.run_diagnostic_tests(device_type, device)

def get_connection_history(device_type: DeviceType) -> List[ConnectionEvent]:
    """Get connection history for a device."""
    return diagnostics_manager.get_connection_history(device_type)

def get_current_status(device_type: DeviceType) -> ConnectionStatus:
    """Get current connection status for a device."""
    return diagnostics_manager.get_current_status(device_type)

def start_monitoring():
    """Start connection monitoring."""
    diagnostics_manager.start_monitoring()

def stop_monitoring():
    """Stop connection monitoring."""
    diagnostics_manager.stop_monitoring() 