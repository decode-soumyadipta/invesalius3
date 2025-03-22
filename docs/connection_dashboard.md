# Connection Status Dashboard

## Overview

The Connection Status Dashboard is a diagnostic tool in InVesalius that provides real-time monitoring and troubleshooting capabilities for hardware devices connected to the system. This feature helps users identify and resolve connection issues with navigation trackers, cameras, and other peripheral devices.

## Features

- **Real-time Status Monitoring**: View the current connection status of all devices.
- **Connection History**: Track connection and disconnection events with timestamps.
- **Diagnostic Tests**: Run tests to verify proper device functioning.
- **Detailed Error Information**: Receive specific error messages to help diagnose issues.
- **Event Logging**: Review a chronological log of all device-related events.

## Accessing the Dashboard

There are several ways to access the Connection Status Dashboard:

1. **From the Tools Menu**: Select `Tools > Connection Status Dashboard`
2. **When Connection Issues Occur**: The dashboard may appear automatically when a connection problem is detected.
3. **Programmatically**: Developers can access the dashboard through the diagnostics API.

## Using the Dashboard

### Device Status Panel

The main panel displays all connected devices with their current status:

- **Connected** (Green): Device is properly connected and functioning.
- **Disconnected** (Red): Device is not connected or has been disconnected.
- **Error** (Orange): Device is connected but experiencing issues.
- **Unknown** (Gray): Device status cannot be determined.

### Running Diagnostics

To troubleshoot a device:

1. Select the device from the list
2. Click the "Run Diagnostics" button
3. The system will perform a series of tests and display the results
4. Follow any recommended actions to resolve issues

### Connection History

The connection history tab shows all connection events:

- When devices were connected or disconnected
- Any errors or warnings that occurred
- Timestamps for each event

This information can be useful for identifying patterns in connection issues.

## Integration with Error Handling System

The Connection Status Dashboard is integrated with the centralized error handling system in InVesalius. When a device-related error occurs:

1. The error is logged in the system log
2. The dashboard is updated with the error information
3. The user is notified through the appropriate channel
4. Diagnostic information is collected to help resolve the issue

## For Developers

### Diagnostics API

Developers can use the diagnostics API to integrate their components with the monitoring system:

```python
from invesalius.navigation.diagnostics import (
    DeviceType, 
    DeviceStatus,
    DiagnosticResult,
    get_diagnostics_system
)

# Update device status
diagnostics = get_diagnostics_system()
diagnostics.update_device_status(
    DeviceType.TRACKER,
    DeviceStatus.CONNECTED,
    "Tracker connected successfully",
    {"tracker_id": 1}
)

# Add diagnostic result
result = DiagnosticResult(
    device_type=DeviceType.TRACKER,
    test_name="communication_test",
    passed=True,
    message="Communication test passed",
    details={"latency_ms": 15}
)
diagnostics.add_diagnostic_result(result)
```

### Running Programmatic Tests

To run diagnostic tests programmatically:

```python
from invesalius.navigation.diagnostics import DeviceType, get_diagnostics_system

diagnostics = get_diagnostics_system()
results = diagnostics.run_diagnostics(DeviceType.TRACKER)

for result in results:
    print(f"Test: {result.test_name}, Passed: {result.passed}, Message: {result.message}")
```

## Troubleshooting Common Issues

| Issue | Possible Cause | Solution |
|-------|----------------|----------|
| Device not detected | Driver not installed | Install the latest device drivers |
| Intermittent connection | USB cable issue | Replace the USB cable, check for damage |
| Error after OS update | Driver compatibility | Update to the latest device drivers |
| Slow response time | Interference or CPU load | Move device away from interference sources, check system resources |
| Configuration errors | Incorrect settings | Reset to default settings and reconfigure |

## Further Assistance

If you continue to experience issues after using the Dashboard:

1. Export the diagnostic log from the dashboard
2. Contact technical support with the log file
3. Include details of your system configuration and the steps to reproduce the issue 