#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import datetime
import os
import sys

import wx
import wx.lib.agw.aui as aui
import wx.lib.scrolledpanel as scrolled
from pubsub import pub

import invesalius.constants as const
from invesalius.navigation.diagnostics import (
    ConnectionEvent,
    DeviceStatus,
    DeviceType,
    DiagnosticResult,
    get_diagnostics_system,
)

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
    logger = get_logger("navigation.connection_dashboard")
else:
    import logging

    logger = logging.getLogger("InVesalius.navigation.connection_dashboard")


# Device status to color mapping
STATUS_COLORS = {
    DeviceStatus.UNKNOWN: "#808080",  # Gray
    DeviceStatus.DISCONNECTED: "#FF0000",  # Red
    DeviceStatus.CONNECTING: "#FFA500",  # Orange
    DeviceStatus.CONNECTED: "#00FF00",  # Green
    DeviceStatus.ERROR: "#FF0000",  # Red
    DeviceStatus.READY: "#00FF00",  # Green
}

# Device type to icon mapping (using wx.ART constants)
DEVICE_ICONS = {
    DeviceType.TRACKER: wx.ART_FIND,
    DeviceType.ROBOT: wx.ART_EXECUTABLE_FILE,
    DeviceType.SERIAL_PORT: wx.ART_NORMAL_FILE,
    DeviceType.PEDAL: wx.ART_HELP_SIDE_PANEL,
    DeviceType.NETWORKING: wx.ART_INFORMATION,
    DeviceType.TFUS: wx.ART_TIP,
}


class ConnectionDashboard(wx.Dialog):
    """Connection Status Dashboard dialog."""

    def __init__(self, parent=None):
        super().__init__(
            parent,
            title="Connection Status Dashboard",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX | wx.MINIMIZE_BOX,
            size=(800, 600),
        )

        self.diagnostics = get_diagnostics_system()
        self._init_ui()
        self._bind_events()
        self._update_status_display()

    def _init_ui(self):
        """Initialize the user interface."""
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create notebook for tabs
        self.notebook = wx.Notebook(self)
        self.status_panel = StatusPanel(self.notebook)
        self.history_panel = HistoryPanel(self.notebook)
        self.diagnostics_panel = DiagnosticsPanel(self.notebook)

        self.notebook.AddPage(self.status_panel, "Status")
        self.notebook.AddPage(self.history_panel, "Connection History")
        self.notebook.AddPage(self.diagnostics_panel, "Diagnostics")

        self.main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)

        # Create button row
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.refresh_button = wx.Button(self, label="Refresh")
        self.refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh)

        self.run_all_diagnostics_button = wx.Button(self, label="Run All Diagnostics")
        self.run_all_diagnostics_button.Bind(wx.EVT_BUTTON, self.on_run_all_diagnostics)

        self.export_button = wx.Button(self, label="Export Log")
        self.export_button.Bind(wx.EVT_BUTTON, self.on_export_log)

        self.close_button = wx.Button(self, label="Close")
        self.close_button.Bind(wx.EVT_BUTTON, self.on_close)

        button_sizer.Add(self.refresh_button, 0, wx.RIGHT, 5)
        button_sizer.Add(self.run_all_diagnostics_button, 0, wx.RIGHT, 5)
        button_sizer.Add(self.export_button, 0, wx.RIGHT, 5)
        button_sizer.AddStretchSpacer()
        button_sizer.Add(self.close_button, 0)

        self.main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(self.main_sizer)
        self.Layout()

    def _bind_events(self):
        """Bind event handlers."""
        # Subscribe to pubsub messages
        pub.subscribe(self._on_device_status_updated, "Device status updated")
        pub.subscribe(self._on_diagnostic_result_added, "Diagnostic result added")

    def _on_device_status_updated(self, device_type, status, message, details):
        """Handle device status update event."""
        wx.CallAfter(self._update_status_display)

    def _on_diagnostic_result_added(self, device_type, result):
        """Handle diagnostic result added event."""
        wx.CallAfter(self._update_diagnostics_display)

    def _update_status_display(self):
        """Update the status display."""
        self.status_panel.update_display()

    def _update_diagnostics_display(self):
        """Update the diagnostics display."""
        self.diagnostics_panel.update_display()

    def on_refresh(self, event):
        """Handle refresh button click."""
        self._update_status_display()
        self.history_panel.update_display()
        self._update_diagnostics_display()

    def on_run_all_diagnostics(self, event):
        """Handle run all diagnostics button click."""
        dialog = wx.MessageDialog(
            self,
            "Running diagnostics on all devices. This may take a moment.",
            "Running Diagnostics",
            wx.OK | wx.ICON_INFORMATION,
        )
        dialog.ShowModal()
        dialog.Destroy()

        # Run diagnostics for each device type
        for device_type in DeviceType:
            try:
                self.diagnostics.run_diagnostics(device_type)
            except Exception as e:
                if HAS_ERROR_HANDLING:
                    handle_errors(
                        NavigationError(
                            message=f"Error running diagnostics for {device_type.name}",
                            details=str(e),
                            category=ErrorCategory.DEVICE_CONNECTION,
                            severity=ErrorSeverity.WARNING,
                        )
                    )
                else:
                    logger.error(f"Error running diagnostics for {device_type.name}: {str(e)}")

        self._update_diagnostics_display()

    def on_export_log(self, event):
        """Handle export log button click."""
        # Get the log file path
        log_path = self.diagnostics.log_file_path

        if not log_path or not os.path.exists(log_path):
            if HAS_ERROR_HANDLING:
                show_error_dialog(
                    title="Export Error",
                    message="Log file not found",
                    details="The connection log file could not be found.",
                )
            else:
                wx.MessageBox(
                    "The connection log file could not be found.",
                    "Export Error",
                    wx.OK | wx.ICON_ERROR,
                )
            return

        # Show save dialog
        with wx.FileDialog(
            self,
            "Save Connection Log",
            wildcard="Log files (*.log)|*.log",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return

            # Save the log file
            save_path = fileDialog.GetPath()
            try:
                import shutil

                shutil.copy2(log_path, save_path)

                wx.MessageBox(
                    f"Log file exported successfully to {save_path}",
                    "Export Successful",
                    wx.OK | wx.ICON_INFORMATION,
                )
            except Exception as e:
                if HAS_ERROR_HANDLING:
                    handle_errors(
                        NavigationError(
                            message="Error exporting log file",
                            details=str(e),
                            category=ErrorCategory.FILE_OPERATION,
                            severity=ErrorSeverity.WARNING,
                        )
                    )
                else:
                    wx.MessageBox(
                        f"Error exporting log file: {str(e)}", "Export Error", wx.OK | wx.ICON_ERROR
                    )

    def on_close(self, event):
        """Handle close button click."""
        self.Destroy()


class StatusPanel(wx.Panel):
    """Panel displaying the current status of all devices."""

    def __init__(self, parent):
        super().__init__(parent)
        self.diagnostics = get_diagnostics_system()
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Header
        header = wx.StaticText(self, label="Current Device Status")
        header.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.main_sizer.Add(header, 0, wx.ALL, 10)

        # Device status panel
        self.status_sizer = wx.FlexGridSizer(cols=3, hgap=10, vgap=10)
        self.status_sizer.AddGrowableCol(1)

        # Headers for the grid
        self.status_sizer.Add(wx.StaticText(self, label="Device"), 0, wx.ALIGN_LEFT)
        self.status_sizer.Add(wx.StaticText(self, label="Status"), 0, wx.ALIGN_LEFT)
        self.status_sizer.Add(wx.StaticText(self, label="Actions"), 0, wx.ALIGN_LEFT)

        # Create a status display for each device type
        self.device_displays = {}

        for device_type in DeviceType:
            name_label = wx.StaticText(self, label=device_type.name.replace("_", " ").title())

            # Status display with icon
            status_panel = wx.Panel(self)
            status_sizer = wx.BoxSizer(wx.HORIZONTAL)

            status_icon = wx.StaticBitmap(
                status_panel,
                bitmap=wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, size=wx.Size(16, 16)),
            )

            status_text = wx.StaticText(status_panel, label="Unknown")

            status_sizer.Add(status_icon, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
            status_sizer.Add(status_text, 0, wx.ALIGN_CENTER_VERTICAL)

            status_panel.SetSizer(status_sizer)

            # Action buttons
            action_panel = wx.Panel(self)
            action_sizer = wx.BoxSizer(wx.HORIZONTAL)

            diagnose_button = wx.Button(action_panel, label="Diagnose", size=(90, -1))
            diagnose_button.Bind(
                wx.EVT_BUTTON, lambda evt, dt=device_type: self.on_diagnose_device(evt, dt)
            )

            details_button = wx.Button(action_panel, label="Details", size=(90, -1))
            details_button.Bind(
                wx.EVT_BUTTON, lambda evt, dt=device_type: self.on_show_device_details(evt, dt)
            )

            action_sizer.Add(diagnose_button, 0, wx.RIGHT, 5)
            action_sizer.Add(details_button, 0)

            action_panel.SetSizer(action_sizer)

            # Add to sizer
            self.status_sizer.Add(name_label, 0, wx.ALIGN_CENTER_VERTICAL)
            self.status_sizer.Add(status_panel, 1, wx.EXPAND)
            self.status_sizer.Add(action_panel, 0, wx.ALIGN_CENTER_VERTICAL)

            # Store references for updating
            self.device_displays[device_type] = {
                "status_icon": status_icon,
                "status_text": status_text,
                "diagnose_button": diagnose_button,
                "details_button": details_button,
            }

        self.main_sizer.Add(self.status_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Summary section
        summary_box = wx.StaticBox(self, label="System Summary")
        summary_sizer = wx.StaticBoxSizer(summary_box, wx.VERTICAL)

        self.summary_text = wx.StaticText(
            summary_box, label="All systems nominal. No errors detected."
        )

        summary_sizer.Add(self.summary_text, 0, wx.ALL, 10)

        self.main_sizer.Add(summary_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Spacer to push everything to the top
        self.main_sizer.AddStretchSpacer()

        self.SetSizer(self.main_sizer)
        self.Layout()

    def update_display(self):
        """Update the status display with current information."""
        # Dictionary to store counts for summary
        status_counts = {
            DeviceStatus.UNKNOWN: 0,
            DeviceStatus.DISCONNECTED: 0,
            DeviceStatus.CONNECTING: 0,
            DeviceStatus.CONNECTED: 0,
            DeviceStatus.ERROR: 0,
            DeviceStatus.READY: 0,
        }

        # Update status display for each device
        for device_type, monitor in self.diagnostics.monitors.items():
            display = self.device_displays.get(device_type)
            if not display:
                continue

            status = monitor.status

            # Update icon and text
            icon_name = DEVICE_ICONS.get(device_type, wx.ART_INFORMATION)
            display["status_icon"].SetBitmap(
                wx.ArtProvider.GetBitmap(icon_name, size=wx.Size(16, 16))
            )

            # Set status text with color
            display["status_text"].SetLabel(status.name.replace("_", " ").title())
            display["status_text"].SetForegroundColour(STATUS_COLORS.get(status, "#000000"))

            # Update counts
            status_counts[status] += 1

        # Update summary text
        if status_counts[DeviceStatus.ERROR] > 0:
            summary = f"Warning: {status_counts[DeviceStatus.ERROR]} device(s) reporting errors."
            self.summary_text.SetForegroundColour(STATUS_COLORS[DeviceStatus.ERROR])
        elif status_counts[DeviceStatus.DISCONNECTED] > 0:
            summary = f"{status_counts[DeviceStatus.DISCONNECTED]} device(s) disconnected."
            self.summary_text.SetForegroundColour(STATUS_COLORS[DeviceStatus.DISCONNECTED])
        elif status_counts[DeviceStatus.UNKNOWN] == len(DeviceType):
            summary = "Device status unknown. Please refresh or run diagnostics."
            self.summary_text.SetForegroundColour(STATUS_COLORS[DeviceStatus.UNKNOWN])
        else:
            connected_count = (
                status_counts[DeviceStatus.CONNECTED] + status_counts[DeviceStatus.READY]
            )
            summary = f"{connected_count} device(s) connected and operational."
            self.summary_text.SetForegroundColour(STATUS_COLORS[DeviceStatus.CONNECTED])

        self.summary_text.SetLabel(summary)

        # Refresh layout
        self.Layout()

    def on_diagnose_device(self, event, device_type):
        """Handle diagnose device button click."""
        try:
            results = self.diagnostics.run_diagnostics(device_type)

            # Show results dialog
            result_summary = "\n".join([str(result) for result in results])

            with wx.MessageDialog(
                self,
                f"Diagnostic Results for {device_type.name}:\n\n{result_summary}",
                "Diagnostic Results",
                wx.OK | wx.ICON_INFORMATION,
            ) as dialog:
                dialog.ShowModal()

        except Exception as e:
            if HAS_ERROR_HANDLING:
                handle_errors(
                    NavigationError(
                        message=f"Error running diagnostics for {device_type.name}",
                        details=str(e),
                        category=ErrorCategory.DEVICE_CONNECTION,
                        severity=ErrorSeverity.WARNING,
                    )
                )
            else:
                wx.MessageBox(
                    f"Error running diagnostics for {device_type.name}: {str(e)}",
                    "Diagnostic Error",
                    wx.OK | wx.ICON_ERROR,
                )

        # Update the display
        self.update_display()

    def on_show_device_details(self, event, device_type):
        """Handle show device details button click."""
        monitor = self.diagnostics.monitors.get(device_type)
        if not monitor:
            return

        # Create modal dialog with device details
        with DeviceDetailsDialog(self, device_type, monitor) as dialog:
            dialog.ShowModal()


class HistoryPanel(scrolled.ScrolledPanel):
    """Panel displaying connection history for devices."""

    def __init__(self, parent):
        super().__init__(parent)
        self.diagnostics = get_diagnostics_system()
        self._init_ui()
        self.update_display()

    def _init_ui(self):
        """Initialize the user interface."""
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Header
        header = wx.StaticText(self, label="Connection Event History")
        header.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.main_sizer.Add(header, 0, wx.ALL, 10)

        # Filter controls
        filter_box = wx.StaticBox(self, label="Filters")
        filter_sizer = wx.StaticBoxSizer(filter_box, wx.HORIZONTAL)

        # Device type filter
        self.device_filter = wx.Choice(
            filter_box, choices=["All Devices"] + [dt.name for dt in DeviceType]
        )
        self.device_filter.SetSelection(0)
        self.device_filter.Bind(wx.EVT_CHOICE, self.on_filter_changed)

        # Status filter
        self.status_filter = wx.Choice(
            filter_box, choices=["All Statuses"] + [ds.name for ds in DeviceStatus]
        )
        self.status_filter.SetSelection(0)
        self.status_filter.Bind(wx.EVT_CHOICE, self.on_filter_changed)

        filter_sizer.Add(
            wx.StaticText(filter_box, label="Device Type:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        filter_sizer.Add(self.device_filter, 0, wx.RIGHT, 20)
        filter_sizer.Add(
            wx.StaticText(filter_box, label="Status:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5
        )
        filter_sizer.Add(self.status_filter, 0)

        self.main_sizer.Add(filter_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Event list
        list_box = wx.StaticBox(self, label="Events")
        list_sizer = wx.StaticBoxSizer(list_box, wx.VERTICAL)

        self.event_list = wx.ListCtrl(
            list_box, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN
        )

        # Add columns
        self.event_list.InsertColumn(0, "Time", width=150)
        self.event_list.InsertColumn(1, "Device", width=100)
        self.event_list.InsertColumn(2, "Status", width=100)
        self.event_list.InsertColumn(3, "Message", width=300)

        list_sizer.Add(self.event_list, 1, wx.EXPAND)

        self.main_sizer.Add(list_sizer, 1, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(self.main_sizer)
        self.SetupScrolling()

    def update_display(self):
        """Update the event list display."""
        # Clear the list
        self.event_list.DeleteAllItems()

        # Get filter values
        device_filter = self.device_filter.GetSelection()
        status_filter = self.status_filter.GetSelection()

        selected_device = (
            None if device_filter == 0 else DeviceType[self.device_filter.GetString(device_filter)]
        )
        selected_status = (
            None
            if status_filter == 0
            else DeviceStatus[self.status_filter.GetString(status_filter)]
        )

        # Collect events from all monitors
        all_events = []
        for device_type, monitor in self.diagnostics.monitors.items():
            # Skip if filtered by device
            if selected_device and device_type != selected_device:
                continue

            for event in monitor.connection_history:
                # Skip if filtered by status
                if selected_status and event.status != selected_status:
                    continue

                all_events.append(event)

        # Sort events by timestamp, newest first
        all_events.sort(key=lambda e: e.timestamp, reverse=True)

        # Add to list
        for i, event in enumerate(all_events):
            time_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            index = self.event_list.InsertItem(i, time_str)
            self.event_list.SetItem(index, 1, event.device_type.name)
            self.event_list.SetItem(index, 2, event.status.name)
            self.event_list.SetItem(index, 3, event.message)

            # Set item data for reference
            self.event_list.SetItemData(index, i)

            # Set item color based on status
            if event.status == DeviceStatus.ERROR:
                self.event_list.SetItemTextColour(index, STATUS_COLORS[DeviceStatus.ERROR])
            elif event.status == DeviceStatus.DISCONNECTED:
                self.event_list.SetItemTextColour(index, STATUS_COLORS[DeviceStatus.DISCONNECTED])
            elif event.status == DeviceStatus.CONNECTED or event.status == DeviceStatus.READY:
                self.event_list.SetItemTextColour(index, STATUS_COLORS[DeviceStatus.CONNECTED])

    def on_filter_changed(self, event):
        """Handle filter selection changed."""
        self.update_display()


class DiagnosticsPanel(scrolled.ScrolledPanel):
    """Panel displaying diagnostic test results for devices."""

    def __init__(self, parent):
        super().__init__(parent)
        self.diagnostics = get_diagnostics_system()
        self._init_ui()
        self.update_display()

    def _init_ui(self):
        """Initialize the user interface."""
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Header
        header = wx.StaticText(self, label="Diagnostic Test Results")
        header.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.main_sizer.Add(header, 0, wx.ALL, 10)

        # Filter controls
        filter_box = wx.StaticBox(self, label="Filters")
        filter_sizer = wx.StaticBoxSizer(filter_box, wx.HORIZONTAL)

        # Device type filter
        self.device_filter = wx.Choice(
            filter_box, choices=["All Devices"] + [dt.name for dt in DeviceType]
        )
        self.device_filter.SetSelection(0)
        self.device_filter.Bind(wx.EVT_CHOICE, self.on_filter_changed)

        # Result filter
        self.result_filter = wx.Choice(filter_box, choices=["All Results", "Passed", "Failed"])
        self.result_filter.SetSelection(0)
        self.result_filter.Bind(wx.EVT_CHOICE, self.on_filter_changed)

        filter_sizer.Add(
            wx.StaticText(filter_box, label="Device Type:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        filter_sizer.Add(self.device_filter, 0, wx.RIGHT, 20)
        filter_sizer.Add(
            wx.StaticText(filter_box, label="Result:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5
        )
        filter_sizer.Add(self.result_filter, 0)

        self.main_sizer.Add(filter_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Diagnostic results list
        list_box = wx.StaticBox(self, label="Test Results")
        list_sizer = wx.StaticBoxSizer(list_box, wx.VERTICAL)

        self.result_list = wx.ListCtrl(
            list_box, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN
        )

        # Add columns
        self.result_list.InsertColumn(0, "Time", width=150)
        self.result_list.InsertColumn(1, "Device", width=100)
        self.result_list.InsertColumn(2, "Test", width=150)
        self.result_list.InsertColumn(3, "Result", width=80)
        self.result_list.InsertColumn(4, "Message", width=300)

        list_sizer.Add(self.result_list, 1, wx.EXPAND)

        self.main_sizer.Add(list_sizer, 1, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(self.main_sizer)
        self.SetupScrolling()

    def update_display(self):
        """Update the diagnostic results display."""
        # Clear the list
        self.result_list.DeleteAllItems()

        # Get filter values
        device_filter = self.device_filter.GetSelection()
        result_filter = self.result_filter.GetSelection()

        selected_device = (
            None if device_filter == 0 else DeviceType[self.device_filter.GetString(device_filter)]
        )
        passed_filter = None if result_filter == 0 else (result_filter == 1)

        # Collect results from all monitors
        all_results = []
        for device_type, monitor in self.diagnostics.monitors.items():
            # Skip if filtered by device
            if selected_device and device_type != selected_device:
                continue

            for result in monitor.diagnostic_history:
                # Skip if filtered by result
                if passed_filter is not None and result.passed != passed_filter:
                    continue

                all_results.append(result)

        # Sort results by timestamp, newest first
        all_results.sort(key=lambda r: r.timestamp, reverse=True)

        # Add to list
        for i, result in enumerate(all_results):
            time_str = result.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            index = self.result_list.InsertItem(i, time_str)
            self.result_list.SetItem(index, 1, result.device_type.name)
            self.result_list.SetItem(index, 2, result.test_name)
            self.result_list.SetItem(index, 3, "Passed" if result.passed else "Failed")
            self.result_list.SetItem(index, 4, result.message)

            # Set item data for reference
            self.result_list.SetItemData(index, i)

            # Set item color based on result
            if result.passed:
                self.result_list.SetItemTextColour(index, STATUS_COLORS[DeviceStatus.CONNECTED])
            else:
                self.result_list.SetItemTextColour(index, STATUS_COLORS[DeviceStatus.ERROR])

    def on_filter_changed(self, event):
        """Handle filter selection changed."""
        self.update_display()


class DeviceDetailsDialog(wx.Dialog):
    """Dialog displaying detailed information about a device."""

    def __init__(self, parent, device_type, monitor):
        super().__init__(
            parent,
            title=f"{device_type.name} Details",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=(600, 500),
        )

        self.device_type = device_type
        self.monitor = monitor
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Device info section
        info_box = wx.StaticBox(self, label="Device Information")
        info_sizer = wx.StaticBoxSizer(info_box, wx.VERTICAL)

        grid = wx.FlexGridSizer(cols=2, vgap=5, hgap=10)
        grid.AddGrowableCol(1)

        # Add device info
        grid.Add(wx.StaticText(info_box, label="Device Type:"), 0, wx.ALIGN_RIGHT)
        grid.Add(wx.StaticText(info_box, label=self.device_type.name), 0, wx.EXPAND)

        grid.Add(wx.StaticText(info_box, label="Current Status:"), 0, wx.ALIGN_RIGHT)
        status_text = wx.StaticText(info_box, label=self.monitor.status.name)
        status_text.SetForegroundColour(STATUS_COLORS.get(self.monitor.status, "#000000"))
        grid.Add(status_text, 0, wx.EXPAND)

        grid.Add(wx.StaticText(info_box, label="Last Updated:"), 0, wx.ALIGN_RIGHT)
        grid.Add(
            wx.StaticText(info_box, label=self.monitor.last_update.strftime("%Y-%m-%d %H:%M:%S")),
            0,
            wx.EXPAND,
        )

        grid.Add(wx.StaticText(info_box, label="Error Count:"), 0, wx.ALIGN_RIGHT)
        grid.Add(wx.StaticText(info_box, label=str(self.monitor.error_count)), 0, wx.EXPAND)

        # Add device-specific info if available
        if self.monitor.device_info:
            for key, value in self.monitor.device_info.items():
                grid.Add(wx.StaticText(info_box, label=f"{key}:"), 0, wx.ALIGN_RIGHT)
                grid.Add(wx.StaticText(info_box, label=str(value)), 0, wx.EXPAND)

        info_sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 10)
        self.main_sizer.Add(info_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Event history
        history_box = wx.StaticBox(self, label="Recent Connection Events")
        history_sizer = wx.StaticBoxSizer(history_box, wx.VERTICAL)

        self.event_list = wx.ListCtrl(
            history_box, style=wx.LC_REPORT | wx.BORDER_SUNKEN, size=(-1, 150)
        )

        # Add columns
        self.event_list.InsertColumn(0, "Time", width=150)
        self.event_list.InsertColumn(1, "Status", width=100)
        self.event_list.InsertColumn(2, "Message", width=300)

        # Add events
        for i, event in enumerate(list(self.monitor.connection_history)[-10:]):
            time_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            index = self.event_list.InsertItem(i, time_str)
            self.event_list.SetItem(index, 1, event.status.name)
            self.event_list.SetItem(index, 2, event.message)

            # Set item color based on status
            if event.status == DeviceStatus.ERROR:
                self.event_list.SetItemTextColour(index, STATUS_COLORS[DeviceStatus.ERROR])
            elif event.status == DeviceStatus.DISCONNECTED:
                self.event_list.SetItemTextColour(index, STATUS_COLORS[DeviceStatus.DISCONNECTED])
            elif event.status == DeviceStatus.CONNECTED or event.status == DeviceStatus.READY:
                self.event_list.SetItemTextColour(index, STATUS_COLORS[DeviceStatus.CONNECTED])

        history_sizer.Add(self.event_list, 1, wx.EXPAND | wx.ALL, 5)
        self.main_sizer.Add(history_sizer, 1, wx.EXPAND | wx.ALL, 10)

        # Diagnostic history
        diag_box = wx.StaticBox(self, label="Recent Diagnostic Results")
        diag_sizer = wx.StaticBoxSizer(diag_box, wx.VERTICAL)

        self.diag_list = wx.ListCtrl(
            diag_box, style=wx.LC_REPORT | wx.BORDER_SUNKEN, size=(-1, 150)
        )

        # Add columns
        self.diag_list.InsertColumn(0, "Time", width=150)
        self.diag_list.InsertColumn(1, "Test", width=150)
        self.diag_list.InsertColumn(2, "Result", width=80)
        self.diag_list.InsertColumn(3, "Message", width=300)

        # Add diagnostic results
        for i, result in enumerate(list(self.monitor.diagnostic_history)[-10:]):
            time_str = result.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            index = self.diag_list.InsertItem(i, time_str)
            self.diag_list.SetItem(index, 1, result.test_name)
            self.diag_list.SetItem(index, 2, "Passed" if result.passed else "Failed")
            self.diag_list.SetItem(index, 3, result.message)

            # Set item color based on result
            if result.passed:
                self.diag_list.SetItemTextColour(index, STATUS_COLORS[DeviceStatus.CONNECTED])
            else:
                self.diag_list.SetItemTextColour(index, STATUS_COLORS[DeviceStatus.ERROR])

        diag_sizer.Add(self.diag_list, 1, wx.EXPAND | wx.ALL, 5)
        self.main_sizer.Add(diag_sizer, 1, wx.EXPAND | wx.ALL, 10)

        # Close button
        button_sizer = wx.StdDialogButtonSizer()
        close_button = wx.Button(self, wx.ID_CLOSE)
        close_button.Bind(wx.EVT_BUTTON, self.on_close)
        button_sizer.AddButton(close_button)
        button_sizer.Realize()

        self.main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        self.SetSizer(self.main_sizer)
        self.Layout()

    def on_close(self, event):
        """Handle close button click."""
        self.EndModal(wx.ID_CLOSE)


# Function to show the dashboard
def show_connection_dashboard(parent=None):
    """Show the connection status dashboard."""
    try:
        dashboard = ConnectionDashboard(parent)
        dashboard.Show()
        return dashboard
    except Exception as e:
        if HAS_ERROR_HANDLING:
            handle_errors(
                NavigationError(
                    message="Error showing connection dashboard",
                    details=str(e),
                    category=ErrorCategory.UI,
                    severity=ErrorSeverity.WARNING,
                )
            )
        else:
            import traceback

            logger.error(f"Error showing connection dashboard: {str(e)}\n{traceback.format_exc()}")
        return None
