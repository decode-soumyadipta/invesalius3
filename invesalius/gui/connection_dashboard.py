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
from typing import Dict, List, Optional, Tuple

import wx
import wx.lib.agw.aui as aui
import wx.lib.agw.ultimatelistctrl as ulc
import wx.lib.newevent

import invesalius.constants as const
import invesalius.gui.dialogs as dlg
import invesalius.utils as utils
from invesalius.navigation.diagnostics import (
    DeviceMonitor,
    DeviceStatus,
    DeviceType,
    DiagnosticResult,
    ConnectionEvent,
    get_diagnostics_system,
    run_all_diagnostics
)
from invesalius.pubsub import pub as Publisher

try:
    from invesalius.error_handling import (
        NavigationError,
        ErrorCategory,
        ErrorSeverity,
        handle_errors,
        show_error_dialog
    )
    from invesalius.enhanced_logging import get_logger
    HAS_ERROR_HANDLING = True
except ImportError:
    HAS_ERROR_HANDLING = False

if HAS_ERROR_HANDLING:
    logger = get_logger("gui.connection_dashboard")
else:
    import logging
    logger = logging.getLogger("InVesalius.gui.connection_dashboard")

# Define custom events
DeviceStatusUpdatedEvent, EVT_DEVICE_STATUS_UPDATED = wx.lib.newevent.NewEvent()
DiagnosticResultAddedEvent, EVT_DIAGNOSTIC_RESULT_ADDED = wx.lib.newevent.NewEvent()


class DeviceStatusPanel(wx.Panel):
    """Panel showing the status of devices."""
    
    def __init__(self, parent):
        super(DeviceStatusPanel, self).__init__(parent)
        
        self.diagnostics = get_diagnostics_system()
        self.device_indicators = {}
        
        self._init_ui()
        self._bind_events()
        self._update_all_statuses()
        
    def _init_ui(self):
        """Initialize the UI."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self, -1, _("Device Status"))
        title.SetFont(wx.Font(12, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        main_sizer.Add(title, 0, wx.EXPAND | wx.ALL, 5)
        
        # Status grid
        grid_sizer = wx.FlexGridSizer(rows=len(DeviceType), cols=3, hgap=10, vgap=10)
        grid_sizer.AddGrowableCol(1)
        
        # Add device statuses
        for device_type in DeviceType:
            # Label
            device_label = wx.StaticText(self, -1, self._get_device_label(device_type))
            
            # Status indicator
            status_indicator = wx.StaticText(self, -1, "Unknown")
            status_indicator.SetFont(wx.Font(9, wx.DEFAULT, wx.NORMAL, wx.BOLD))
            self.device_indicators[device_type] = status_indicator
            
            # Action button
            action_btn = wx.Button(self, -1, _("Test"), size=(60, -1))
            action_btn.Bind(wx.EVT_BUTTON, lambda evt, dt=device_type: self._on_test_button(evt, dt))
            
            # Add to grid
            grid_sizer.Add(device_label, 0, wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
            grid_sizer.Add(status_indicator, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
            grid_sizer.Add(action_btn, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        
        main_sizer.Add(grid_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # Update button
        refresh_btn = wx.Button(self, -1, _("Refresh Status"))
        refresh_btn.Bind(wx.EVT_BUTTON, self._on_refresh)
        main_sizer.Add(refresh_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        # Test all button
        test_all_btn = wx.Button(self, -1, _("Test All Devices"))
        test_all_btn.Bind(wx.EVT_BUTTON, self._on_test_all)
        main_sizer.Add(test_all_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
        
    def _bind_events(self):
        """Bind events."""
        self.Bind(EVT_DEVICE_STATUS_UPDATED, self._on_device_status_updated)
        Publisher.subscribe(self._on_status_update, "Device status updated")
        
    def _get_device_label(self, device_type):
        """Get a readable label for a device type."""
        labels = {
            DeviceType.TRACKER: _("Tracking Device"),
            DeviceType.ROBOT: _("Robot Controller"),
            DeviceType.SERIAL_PORT: _("Serial Port"),
            DeviceType.PEDAL: _("Foot Pedal"),
            DeviceType.NETWORKING: _("Network Interface"),
            DeviceType.TFUS: _("Ultrasound Device")
        }
        return labels.get(device_type, device_type.name)
    
    def _get_status_color(self, status):
        """Get the color for a status."""
        colors = {
            DeviceStatus.UNKNOWN: wx.Colour(128, 128, 128),      # Gray
            DeviceStatus.DISCONNECTED: wx.Colour(128, 128, 128), # Gray
            DeviceStatus.CONNECTING: wx.Colour(255, 140, 0),     # Dark Orange
            DeviceStatus.CONNECTED: wx.Colour(0, 128, 0),        # Green
            DeviceStatus.ERROR: wx.Colour(255, 0, 0),            # Red
            DeviceStatus.READY: wx.Colour(0, 128, 0)             # Green
        }
        return colors.get(status, wx.Colour(0, 0, 0))
    
    def _update_all_statuses(self):
        """Update all device statuses."""
        summary = self.diagnostics.get_device_status_summary()
        
        for device_type in DeviceType:
            device_info = summary.get(device_type.name, {})
            status_name = device_info.get("status", "UNKNOWN")
            
            try:
                status = DeviceStatus[status_name]
                self._update_device_status(device_type, status)
            except KeyError:
                # Handle case where status name is not valid
                self._update_device_status(device_type, DeviceStatus.UNKNOWN)
    
    def _update_device_status(self, device_type, status):
        """Update a device status indicator."""
        indicator = self.device_indicators.get(device_type)
        if indicator:
            indicator.SetLabel(status.name)
            indicator.SetForegroundColour(self._get_status_color(status))
            
            # If status is ERROR, set the background to light red
            if status == DeviceStatus.ERROR:
                indicator.SetBackgroundColour(wx.Colour(255, 200, 200))
            else:
                indicator.SetBackgroundColour(wx.NullColour)
                
            indicator.Refresh()
    
    def _on_status_update(self, device_type, status, message, details):
        """Handle device status updates from Publisher."""
        wx.PostEvent(self, DeviceStatusUpdatedEvent(
            device_type=device_type,
            status=status,
            message=message,
            details=details
        ))
    
    def _on_device_status_updated(self, event):
        """Handle device status updated event."""
        self._update_device_status(event.device_type, event.status)
    
    def _on_test_button(self, event, device_type):
        """Handle test button click."""
        if device_type == DeviceType.TRACKER:
            self.diagnostics.run_tracker_diagnostics()
        elif device_type == DeviceType.ROBOT:
            self.diagnostics.run_robot_diagnostics()
        elif device_type == DeviceType.SERIAL_PORT:
            # Not implemented yet
            dlg.ShowInformation(_("Serial Port Test"), _("Serial port testing is not implemented yet."))
        elif device_type == DeviceType.PEDAL:
            # Not implemented yet
            dlg.ShowInformation(_("Pedal Test"), _("Foot pedal testing is not implemented yet."))
        elif device_type == DeviceType.NETWORKING:
            # Not implemented yet
            dlg.ShowInformation(_("Network Test"), _("Network testing is not implemented yet."))
        elif device_type == DeviceType.TFUS:
            # Not implemented yet
            dlg.ShowInformation(_("Ultrasound Test"), _("Ultrasound device testing is not implemented yet."))
            
        # Get parent to update diagnostics panel
        if isinstance(self.GetParent(), ConnectionDashboardDialog):
            self.GetParent().update_diagnostics_panel()
    
    def _on_refresh(self, event):
        """Handle refresh button click."""
        self._update_all_statuses()
    
    def _on_test_all(self, event):
        """Handle test all button click."""
        run_all_diagnostics()
        
        # Get parent to update diagnostics panel
        if isinstance(self.GetParent(), ConnectionDashboardDialog):
            self.GetParent().update_diagnostics_panel()


class DiagnosticsPanel(wx.Panel):
    """Panel showing diagnostics results."""
    
    def __init__(self, parent):
        super(DiagnosticsPanel, self).__init__(parent)
        
        self.diagnostics = get_diagnostics_system()
        
        self._init_ui()
        self._bind_events()
        self._update_diagnostics()
        
    def _init_ui(self):
        """Initialize the UI."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self, -1, _("Diagnostic Results"))
        title.SetFont(wx.Font(12, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        main_sizer.Add(title, 0, wx.EXPAND | wx.ALL, 5)
        
        # Results list
        self.results_list = ulc.UltimateListCtrl(
            self, -1, agwStyle=wx.LC_REPORT | wx.LC_VRULES | wx.LC_HRULES | ulc.ULC_HAS_VARIABLE_ROW_HEIGHT
        )
        
        self.results_list.InsertColumn(0, _("Time"), width=150)
        self.results_list.InsertColumn(1, _("Device"), width=150)
        self.results_list.InsertColumn(2, _("Test"), width=150)
        self.results_list.InsertColumn(3, _("Status"), width=80)
        self.results_list.InsertColumn(4, _("Message"), width=300)
        
        main_sizer.Add(self.results_list, 1, wx.EXPAND | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
        
    def _bind_events(self):
        """Bind events."""
        self.Bind(EVT_DIAGNOSTIC_RESULT_ADDED, self._on_diagnostic_result_added)
        Publisher.subscribe(self._on_diagnostic_result, "Diagnostic result added")
        
    def _update_diagnostics(self):
        """Update diagnostics list."""
        self.results_list.DeleteAllItems()
        
        # Get all diagnostic results
        results = self.diagnostics.get_diagnostic_history()
        
        # Add to list in reverse order (newest first)
        for result in reversed(results):
            self._add_diagnostic_result(result)
    
    def _add_diagnostic_result(self, result):
        """Add a diagnostic result to the list."""
        index = self.results_list.InsertStringItem(0, result.timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        
        self.results_list.SetStringItem(index, 1, self._get_device_label(result.device_type))
        self.results_list.SetStringItem(index, 2, result.test_name)
        
        status = _("PASSED") if result.passed else _("FAILED")
        self.results_list.SetStringItem(index, 3, status)
        self.results_list.SetStringItem(index, 4, result.message)
        
        # Set color based on status
        if result.passed:
            self.results_list.SetItemBackgroundColour(index, wx.Colour(230, 255, 230))  # Light green
        else:
            self.results_list.SetItemBackgroundColour(index, wx.Colour(255, 230, 230))  # Light red
    
    def _get_device_label(self, device_type):
        """Get a readable label for a device type."""
        labels = {
            DeviceType.TRACKER: _("Tracking Device"),
            DeviceType.ROBOT: _("Robot Controller"),
            DeviceType.SERIAL_PORT: _("Serial Port"),
            DeviceType.PEDAL: _("Foot Pedal"),
            DeviceType.NETWORKING: _("Network Interface"),
            DeviceType.TFUS: _("Ultrasound Device")
        }
        return labels.get(device_type, device_type.name)
    
    def _on_diagnostic_result(self, device_type, result):
        """Handle diagnostic result from Publisher."""
        wx.PostEvent(self, DiagnosticResultAddedEvent(result=result))
    
    def _on_diagnostic_result_added(self, event):
        """Handle diagnostic result added event."""
        self._add_diagnostic_result(event.result)


class ConnectionHistoryPanel(wx.Panel):
    """Panel showing connection history."""
    
    def __init__(self, parent):
        super(ConnectionHistoryPanel, self).__init__(parent)
        
        self.diagnostics = get_diagnostics_system()
        
        self._init_ui()
        self._bind_events()
        self._update_history()
        
    def _init_ui(self):
        """Initialize the UI."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self, -1, _("Connection History"))
        title.SetFont(wx.Font(12, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        main_sizer.Add(title, 0, wx.EXPAND | wx.ALL, 5)
        
        # Device filter
        filter_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        filter_label = wx.StaticText(self, -1, _("Filter by device:"))
        filter_sizer.Add(filter_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        
        self.device_filter = wx.Choice(self, -1)
        self.device_filter.Append(_("All Devices"), None)
        for device_type in DeviceType:
            self.device_filter.Append(self._get_device_label(device_type), device_type)
        self.device_filter.SetSelection(0)
        self.device_filter.Bind(wx.EVT_CHOICE, self._on_filter_changed)
        
        filter_sizer.Add(self.device_filter, 0, wx.ALIGN_CENTER_VERTICAL)
        
        main_sizer.Add(filter_sizer, 0, wx.ALL, 10)
        
        # History list
        self.history_list = ulc.UltimateListCtrl(
            self, -1, agwStyle=wx.LC_REPORT | wx.LC_VRULES | wx.LC_HRULES | ulc.ULC_HAS_VARIABLE_ROW_HEIGHT
        )
        
        self.history_list.InsertColumn(0, _("Time"), width=150)
        self.history_list.InsertColumn(1, _("Device"), width=150)
        self.history_list.InsertColumn(2, _("Status"), width=100)
        self.history_list.InsertColumn(3, _("Message"), width=400)
        
        main_sizer.Add(self.history_list, 1, wx.EXPAND | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
        
    def _bind_events(self):
        """Bind events."""
        Publisher.subscribe(self._on_device_status_update, "Device status updated")
        
    def _update_history(self):
        """Update connection history list."""
        self.history_list.DeleteAllItems()
        
        # Get selected device type
        selection = self.device_filter.GetSelection()
        selected_device = self.device_filter.GetClientData(selection)
        
        # Get connection history
        events = self.diagnostics.get_connection_history(selected_device)
        
        # Add to list in reverse order (newest first)
        for event in reversed(events):
            self._add_connection_event(event)
    
    def _add_connection_event(self, event):
        """Add a connection event to the list."""
        index = self.history_list.InsertStringItem(0, event.timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        
        self.history_list.SetStringItem(index, 1, self._get_device_label(event.device_type))
        self.history_list.SetStringItem(index, 2, event.status.name)
        self.history_list.SetStringItem(index, 3, event.message)
        
        # Set color based on status
        color = self._get_status_color(event.status)
        self.history_list.SetItemTextColour(index, color)
    
    def _get_device_label(self, device_type):
        """Get a readable label for a device type."""
        labels = {
            DeviceType.TRACKER: _("Tracking Device"),
            DeviceType.ROBOT: _("Robot Controller"),
            DeviceType.SERIAL_PORT: _("Serial Port"),
            DeviceType.PEDAL: _("Foot Pedal"),
            DeviceType.NETWORKING: _("Network Interface"),
            DeviceType.TFUS: _("Ultrasound Device")
        }
        return labels.get(device_type, device_type.name)
    
    def _get_status_color(self, status):
        """Get the color for a status."""
        colors = {
            DeviceStatus.UNKNOWN: wx.Colour(128, 128, 128),      # Gray
            DeviceStatus.DISCONNECTED: wx.Colour(128, 128, 128), # Gray
            DeviceStatus.CONNECTING: wx.Colour(255, 140, 0),     # Dark Orange
            DeviceStatus.CONNECTED: wx.Colour(0, 128, 0),        # Green
            DeviceStatus.ERROR: wx.Colour(255, 0, 0),            # Red
            DeviceStatus.READY: wx.Colour(0, 128, 0)             # Green
        }
        return colors.get(status, wx.Colour(0, 0, 0))
    
    def _on_filter_changed(self, event):
        """Handle filter change."""
        self._update_history()
    
    def _on_device_status_update(self, device_type, status, message, details):
        """Handle device status update."""
        wx.CallAfter(self._update_history)


class TroubleshootingPanel(wx.Panel):
    """Panel showing troubleshooting steps for common issues."""
    
    def __init__(self, parent):
        super(TroubleshootingPanel, self).__init__(parent)
        
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the UI."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(self, -1, _("Troubleshooting Guide"))
        title.SetFont(wx.Font(12, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        main_sizer.Add(title, 0, wx.EXPAND | wx.ALL, 5)
        
        # Create a scrolled panel for the content
        self.scrolled_panel = wx.ScrolledWindow(self, -1, style=wx.VSCROLL)
        self.scrolled_panel.SetScrollRate(0, 10)
        
        scrolled_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Add troubleshooting sections
        self._add_troubleshooting_section(
            scrolled_sizer,
            _("Tracker Connection Issues"),
            [
                _("Make sure the tracker is properly connected to power and USB/serial port."),
                _("Check if the tracker driver is installed on your system."),
                _("Try using a different USB port on your computer."),
                _("Restart the tracker device."),
                _("Make sure no other software is using the tracker."),
                _("Try restarting InVesalius.")
            ]
        )
        
        self._add_troubleshooting_section(
            scrolled_sizer,
            _("Robot Connection Issues"),
            [
                _("Verify the robot IP address is correct."),
                _("Ensure the robot controller is powered on and connected to the network."),
                _("Check network connectivity between your computer and the robot."),
                _("Verify firewall settings are not blocking the connection."),
                _("Make sure the robot control software is running."),
                _("Try restarting the robot controller.")
            ]
        )
        
        self._add_troubleshooting_section(
            scrolled_sizer,
            _("Serial Port Issues"),
            [
                _("Check if the serial device is properly connected."),
                _("Verify you have selected the correct COM port."),
                _("Make sure no other software is using the serial port."),
                _("Check if the correct drivers are installed."),
                _("Try a different USB port if using a USB-to-Serial adapter.")
            ]
        )
        
        self._add_troubleshooting_section(
            scrolled_sizer,
            _("Navigation Errors"),
            [
                _("Ensure the tracker can see all required markers."),
                _("Check that the reference marker is stable and not moving."),
                _("Recalibrate the system if the tracking seems inaccurate."),
                _("Verify all device connections before starting navigation."),
                _("Make sure the coil or probe is properly attached.")
            ]
        )
        
        self.scrolled_panel.SetSizer(scrolled_sizer)
        main_sizer.Add(self.scrolled_panel, 1, wx.EXPAND | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
        
    def _add_troubleshooting_section(self, sizer, title, steps):
        """Add a troubleshooting section."""
        # Title
        section_title = wx.StaticText(self.scrolled_panel, -1, title)
        section_title.SetFont(wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        sizer.Add(section_title, 0, wx.EXPAND | wx.ALL, 5)
        
        # Steps
        for i, step in enumerate(steps):
            step_text = wx.StaticText(self.scrolled_panel, -1, f"{i+1}. {step}")
            sizer.Add(step_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        
        # Add some space after the section
        sizer.Add(wx.StaticLine(self.scrolled_panel), 0, wx.EXPAND | wx.ALL, 10)


class ConnectionDashboardDialog(wx.Dialog):
    """Dialog for the Connection Status Dashboard."""
    
    def __init__(self, parent=None):
        super(ConnectionDashboardDialog, self).__init__(
            parent, 
            title=_("Connection Status Dashboard"),
            size=(800, 600),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX | wx.MINIMIZE_BOX
        )
        
        self._init_ui()
        self.Center()
        
    def _init_ui(self):
        """Initialize the UI."""
        # Create notebook for panels
        self.notebook = aui.AuiNotebook(self)
        
        # Add panels
        self.status_panel = DeviceStatusPanel(self.notebook)
        self.diagnostics_panel = DiagnosticsPanel(self.notebook)
        self.history_panel = ConnectionHistoryPanel(self.notebook)
        self.troubleshooting_panel = TroubleshootingPanel(self.notebook)
        
        self.notebook.AddPage(self.status_panel, _("Status"))
        self.notebook.AddPage(self.diagnostics_panel, _("Diagnostics"))
        self.notebook.AddPage(self.history_panel, _("History"))
        self.notebook.AddPage(self.troubleshooting_panel, _("Troubleshooting"))
        
        # Main sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        
        # Bottom buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Export button
        export_btn = wx.Button(self, -1, _("Export Data"))
        export_btn.Bind(wx.EVT_BUTTON, self._on_export)
        btn_sizer.Add(export_btn, 0, wx.ALL, 5)
        
        # Refresh button
        refresh_btn = wx.Button(self, -1, _("Refresh All"))
        refresh_btn.Bind(wx.EVT_BUTTON, self._on_refresh_all)
        btn_sizer.Add(refresh_btn, 0, wx.ALL, 5)
        
        btn_sizer.AddStretchSpacer()
        
        # Close button
        close_btn = wx.Button(self, wx.ID_CLOSE, _("Close"))
        close_btn.Bind(wx.EVT_BUTTON, self._on_close)
        btn_sizer.Add(close_btn, 0, wx.ALL, 5)
        
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        self.SetSizer(main_sizer)
        
    def update_diagnostics_panel(self):
        """Update the diagnostics panel."""
        self.diagnostics_panel._update_diagnostics()
        
    def _on_export(self, event):
        """Handle export button click."""
        # Create file dialog
        wildcard = "JSON files (*.json)|*.json"
        dialog = wx.FileDialog(
            self, 
            message=_("Save connection data"), 
            defaultDir=os.path.expanduser("~"),
            defaultFile="invesalius_connection_data.json",
            wildcard=wildcard,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )
        
        if dialog.ShowModal() == wx.ID_OK:
            path = dialog.GetPath()
            self._export_data(path)
            
        dialog.Destroy()
    
    def _export_data(self, path):
        """Export connection data to a file."""
        try:
            diagnostics = get_diagnostics_system()
            
            data = {
                "export_time": datetime.datetime.now().isoformat(),
                "device_status": diagnostics.get_device_status_summary(),
                "connection_history": [event.to_dict() for event in diagnostics.get_connection_history()],
                "diagnostic_history": [result.to_dict() for result in diagnostics.get_diagnostic_history()]
            }
            
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
                
            dlg.ShowInformation(
                _("Export Successful"),
                _("Connection data has been exported successfully.")
            )
            
        except Exception as e:
            if HAS_ERROR_HANDLING:
                logger.error(f"Failed to export connection data: {str(e)}", exc_info=True)
            else:
                print(f"Failed to export connection data: {str(e)}")
                
            dlg.ShowExceptionMessage(
                _("Export Failed"),
                _("Failed to export connection data:") + f" {str(e)}"
            )
    
    def _on_refresh_all(self, event):
        """Handle refresh all button click."""
        # Run all diagnostics
        run_all_diagnostics()
        
        # Update all panels
        self.status_panel._update_all_statuses()
        self.diagnostics_panel._update_diagnostics()
        self.history_panel._update_history()
    
    def _on_close(self, event):
        """Handle close button click."""
        self.EndModal(wx.ID_CLOSE)


def show_connection_dashboard(parent=None):
    """Show the connection status dashboard dialog."""
    dialog = ConnectionDashboardDialog(parent)
    dialog.ShowModal()
    dialog.Destroy() 