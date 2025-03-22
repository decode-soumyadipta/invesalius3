import time
import wx

from invesalius.i18n import tr as _

class ConnectionLogsDialog(wx.Dialog):
    """Dialog for displaying connection logs and history for devices."""
    
    def __init__(self, parent, device_name, connection_history):
        """
        Initialize the dialog to display connection logs.
        
        Parameters:
        -----------
        parent : wx.Window
            The parent window
        device_name : str
            The name of the device
        connection_history : List
            List of ConnectionEvent objects containing the connection history
        """
        super().__init__(
            parent,
            -1,
            _("Connection History for {}").format(device_name),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=(600, 400)
        )
        
        self.device_name = device_name
        self.connection_history = connection_history
        
        self._init_gui()
        self._populate_logs()
        
    def _init_gui(self):
        """Initialize the GUI components."""
        # Main sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Add description text
        description = wx.StaticText(self, -1, _("Connection events for {}:").format(self.device_name))
        main_sizer.Add(description, 0, wx.ALL, 5)
        
        # Create list control for connection events
        self.list_ctrl = wx.ListCtrl(
            self, -1, style=wx.LC_REPORT | wx.BORDER_SUNKEN | wx.LC_HRULES | wx.LC_VRULES
        )
        
        # Add columns
        self.list_ctrl.InsertColumn(0, _("Time"), width=160)
        self.list_ctrl.InsertColumn(1, _("Status"), width=120)
        self.list_ctrl.InsertColumn(2, _("Message"), width=280)
        
        main_sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        
        # Add export button
        export_button = wx.Button(self, -1, _("Export Logs"))
        export_button.Bind(wx.EVT_BUTTON, self.OnExportLogs)
        
        # Add close button
        close_button = wx.Button(self, wx.ID_CLOSE, _("Close"))
        close_button.Bind(wx.EVT_BUTTON, self.OnClose)
        
        # Create button sizer
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.Add(export_button, 0, wx.RIGHT, 5)
        button_sizer.Add(close_button, 0)
        
        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        
        self.SetSizer(main_sizer)
        self.Layout()
        
    def _populate_logs(self):
        """Populate the list control with connection logs."""
        # Sort events by timestamp (newest first)
        sorted_events = sorted(
            self.connection_history, 
            key=lambda event: event.timestamp,
            reverse=True
        )
        
        # Add each event to the list
        for i, event in enumerate(sorted_events):
            # Format timestamp
            time_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            # Add to list control
            index = self.list_ctrl.InsertItem(i, time_str)
            self.list_ctrl.SetItem(index, 1, event.status.name)
            self.list_ctrl.SetItem(index, 2, event.message)
            
            # Set item background color based on status
            if event.status.name == "CONNECTED" or event.status.name == "READY":
                self.list_ctrl.SetItemBackgroundColour(index, wx.Colour(240, 255, 240))  # Light green
            elif event.status.name == "DISCONNECTED":
                self.list_ctrl.SetItemBackgroundColour(index, wx.Colour(255, 240, 240))  # Light red
            elif event.status.name == "CONNECTING":
                self.list_ctrl.SetItemBackgroundColour(index, wx.Colour(255, 255, 240))  # Light yellow
    
    def OnExportLogs(self, evt):
        """Export connection logs to CSV file."""
        # Get the timestamp for filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        default_filename = f"connection_logs_{self.device_name}_{timestamp}.csv"
        
        # Show file dialog
        with wx.FileDialog(
            self,
            message=_("Export connection logs as..."),
            defaultFile=default_filename,
            wildcard="CSV files (*.csv)|*.csv",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            
            # Save logs to the file
            filepath = file_dialog.GetPath()
            try:
                with open(filepath, 'w', newline='') as csvfile:
                    # Write header
                    csvfile.write("Timestamp,Status,Message,Device Info\n")
                    
                    # Sort events chronologically (oldest first)
                    sorted_events = sorted(
                        self.connection_history, 
                        key=lambda event: event.timestamp
                    )
                    
                    # Write each event
                    for event in sorted_events:
                        time_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                        device_info = str(event.device_info).replace(',', ';')
                        message = event.message.replace(',', ' ')
                        csvfile.write(f"{time_str},{event.status.name},{message},{device_info}\n")
                
                wx.MessageBox(
                    _("Connection logs exported successfully."),
                    _("Export Complete"),
                    wx.OK | wx.ICON_INFORMATION
                )
            except Exception as e:
                wx.MessageBox(
                    _("Failed to export logs: {}").format(str(e)),
                    _("Export Error"),
                    wx.OK | wx.ICON_ERROR
                )
    
    def OnClose(self, evt):
        """Close the dialog."""
        self.EndModal(wx.ID_CLOSE) 