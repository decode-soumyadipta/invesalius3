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
# -------------------------------------------------------------------------

"""
Module for enhanced logging in InVesalius.

This module provides a comprehensive logging system for InVesalius,
including:
- Structured logging with different levels
- Log rotation
- Log filtering
- Log viewing GUI
- Integration with the error handling system
"""

import json
import logging
import logging.config
import logging.handlers
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import wx
import wx.grid
import wx.lib.agw.aui as aui

import invesalius.constants as const
from invesalius import inv_paths
from invesalius.i18n import tr as _
from invesalius.pubsub import pub as Publisher
from invesalius.utils import deep_merge_dict

# Constants
LOG_CONFIG_PATH = os.path.join(inv_paths.USER_INV_DIR, "log_config.json")
DEFAULT_LOGFILE = os.path.join(
    inv_paths.USER_LOG_DIR, datetime.now().strftime("invlog-%Y_%m_%d-%I_%M_%S_%p.log")
)

# Default logging configuration
DEFAULT_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s"
        },
        "simple": {
            "format": "%(asctime)s - %(levelname)s - %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "simple",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": DEFAULT_LOGFILE,
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf8"
        }
    },
    "loggers": {
        "invesalius": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": False
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "file"],
        "propagate": True
    }
}

class LogRecord:
    """Class to represent a log record for the GUI."""
    
    def __init__(
        self, 
        timestamp: str, 
        level: str, 
        name: str, 
        message: str,
        pathname: Optional[str] = None,
        lineno: Optional[int] = None,
        exc_info: Optional[str] = None
    ):
        self.timestamp = timestamp
        self.level = level
        self.name = name
        self.message = message
        self.pathname = pathname
        self.lineno = lineno
        self.exc_info = exc_info
    
    @classmethod
    def from_record(cls, record: logging.LogRecord) -> 'LogRecord':
        """Create a LogRecord from a logging.LogRecord."""
        exc_info = None
        if record.exc_info:
            import traceback
            exc_info = ''.join(traceback.format_exception(*record.exc_info))
        
        return cls(
            timestamp=datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S,%f')[:-3],
            level=record.levelname,
            name=record.name,
            message=record.getMessage(),
            pathname=record.pathname,
            lineno=record.lineno,
            exc_info=exc_info
        )

class InMemoryHandler(logging.Handler):
    """Logging handler that keeps records in memory for the GUI."""
    
    def __init__(self, capacity: int = 1000):
        super().__init__()
        self.capacity = capacity
        self.records = []
        self.formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s"
        )
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record."""
        self.records.append(LogRecord.from_record(record))
        if len(self.records) > self.capacity:
            self.records.pop(0)
    
    def get_records(self, level: Optional[str] = None) -> List[LogRecord]:
        """Get records, optionally filtered by level."""
        if level is None:
            return self.records
        
        return [r for r in self.records if r.level == level]
    
    def clear(self) -> None:
        """Clear all records."""
        self.records = []

class LogViewerFrame(wx.Frame):
    """Frame for viewing logs."""
    
    def __init__(
        self, 
        parent: Optional[wx.Window], 
        in_memory_handler: InMemoryHandler
    ):
        """Initialize the log viewer frame."""
        super().__init__(
            parent,
            title=_("InVesalius Log Viewer"),
            size=(800, 600),
            style=wx.DEFAULT_FRAME_STYLE | wx.RESIZE_BORDER
        )
        
        self.in_memory_handler = in_memory_handler
        
        # Create the UI
        self._create_ui()
        
        # Center the frame on the screen
        self.Centre()
        
        # Bind events
        self.Bind(wx.EVT_CLOSE, self._on_close)
        
        # Set up a timer to refresh the log view
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_timer, self.timer)
        self.timer.Start(1000)  # Refresh every second
    
    def _create_ui(self) -> None:
        """Create the UI."""
        # Create the main panel
        panel = wx.Panel(self)
        
        # Create the main sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create the toolbar
        toolbar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Add the level filter
        level_label = wx.StaticText(panel, label=_("Level:"))
        toolbar_sizer.Add(level_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        
        self.level_choice = wx.Choice(
            panel,
            choices=["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        )
        self.level_choice.SetSelection(0)
        self.level_choice.Bind(wx.EVT_CHOICE, self._on_level_changed)
        toolbar_sizer.Add(self.level_choice, 0, wx.ALL, 5)
        
        # Add a spacer
        toolbar_sizer.Add((0, 0), 1, wx.EXPAND)
        
        # Add the refresh button
        refresh_button = wx.Button(panel, label=_("Refresh"))
        refresh_button.Bind(wx.EVT_BUTTON, self._on_refresh)
        toolbar_sizer.Add(refresh_button, 0, wx.ALL, 5)
        
        # Add the clear button
        clear_button = wx.Button(panel, label=_("Clear"))
        clear_button.Bind(wx.EVT_BUTTON, self._on_clear)
        toolbar_sizer.Add(clear_button, 0, wx.ALL, 5)
        
        # Add the save button
        save_button = wx.Button(panel, label=_("Save"))
        save_button.Bind(wx.EVT_BUTTON, self._on_save)
        toolbar_sizer.Add(save_button, 0, wx.ALL, 5)
        
        main_sizer.Add(toolbar_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Create the log grid
        self.grid = wx.grid.Grid(panel)
        self.grid.CreateGrid(0, 4)
        
        # Set up the grid columns
        self.grid.SetColLabelValue(0, _("Time"))
        self.grid.SetColLabelValue(1, _("Level"))
        self.grid.SetColLabelValue(2, _("Source"))
        self.grid.SetColLabelValue(3, _("Message"))
        
        # Set column widths
        self.grid.SetColSize(0, 150)
        self.grid.SetColSize(1, 80)
        self.grid.SetColSize(2, 150)
        self.grid.SetColSize(3, 400)
        
        # Enable auto-sizing
        self.grid.AutoSizeColumns()
        
        # Add the grid to the sizer
        main_sizer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 5)
        
        # Create the details panel
        details_panel = wx.Panel(panel)
        details_sizer = wx.BoxSizer(wx.VERTICAL)
        
        details_label = wx.StaticText(details_panel, label=_("Details:"))
        details_sizer.Add(details_label, 0, wx.ALL, 5)
        
        self.details_text = wx.TextCtrl(
            details_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
        )
        details_sizer.Add(self.details_text, 1, wx.EXPAND | wx.ALL, 5)
        
        details_panel.SetSizer(details_sizer)
        
        # Add the details panel to the sizer
        main_sizer.Add(details_panel, 1, wx.EXPAND | wx.ALL, 5)
        
        # Set up the panel sizer
        panel.SetSizer(main_sizer)
        
        # Bind grid events
        self.grid.Bind(wx.grid.EVT_GRID_SELECT_CELL, self._on_cell_selected)
        
        # Populate the grid
        self._populate_grid()
    
    def _populate_grid(self) -> None:
        """Populate the grid with log records."""
        # Get the selected level
        level_idx = self.level_choice.GetSelection()
        level = None
        if level_idx > 0:
            level = self.level_choice.GetString(level_idx)
        
        # Get the records
        records = self.in_memory_handler.get_records(level)
        
        # Clear the grid
        if self.grid.GetNumberRows() > 0:
            self.grid.DeleteRows(0, self.grid.GetNumberRows())
        
        # Add the records to the grid
        for i, record in enumerate(records):
            self.grid.AppendRows(1)
            self.grid.SetCellValue(i, 0, record.timestamp)
            self.grid.SetCellValue(i, 1, record.level)
            self.grid.SetCellValue(i, 2, record.name)
            self.grid.SetCellValue(i, 3, record.message)
            
            # Set the cell background color based on the level
            if record.level == "DEBUG":
                self.grid.SetCellBackgroundColour(i, 1, wx.Colour(200, 200, 200))
            elif record.level == "INFO":
                self.grid.SetCellBackgroundColour(i, 1, wx.Colour(200, 255, 200))
            elif record.level == "WARNING":
                self.grid.SetCellBackgroundColour(i, 1, wx.Colour(255, 255, 200))
            elif record.level == "ERROR":
                self.grid.SetCellBackgroundColour(i, 1, wx.Colour(255, 200, 200))
            elif record.level == "CRITICAL":
                self.grid.SetCellBackgroundColour(i, 1, wx.Colour(255, 150, 150))
        
        # Auto-size the grid
        self.grid.AutoSizeColumns()
    
    def _on_cell_selected(self, event: wx.grid.GridEvent) -> None:
        """Handle cell selection."""
        row = event.GetRow()
        
        # Get the selected level
        level_idx = self.level_choice.GetSelection()
        level = None
        if level_idx > 0:
            level = self.level_choice.GetString(level_idx)
        
        # Get the records
        records = self.in_memory_handler.get_records(level)
        
        # Get the selected record
        if row < len(records):
            record = records[row]
            
            # Update the details text
            details = []
            details.append(f"Time: {record.timestamp}")
            details.append(f"Level: {record.level}")
            details.append(f"Source: {record.name}")
            details.append(f"File: {record.pathname}")
            details.append(f"Line: {record.lineno}")
            details.append(f"Message: {record.message}")
            
            if record.exc_info:
                details.append("\nException:")
                details.append(record.exc_info)
            
            self.details_text.SetValue('\n'.join(details))
        
        event.Skip()
    
    def _on_level_changed(self, event: wx.CommandEvent) -> None:
        """Handle level change."""
        self._populate_grid()
    
    def _on_refresh(self, event: wx.CommandEvent) -> None:
        """Handle refresh button click."""
        self._populate_grid()
    
    def _on_clear(self, event: wx.CommandEvent) -> None:
        """Handle clear button click."""
        # Show a confirmation dialog
        dlg = wx.MessageDialog(
            self,
            _("Are you sure you want to clear the log?"),
            _("Confirm Clear"),
            wx.YES_NO | wx.ICON_QUESTION
        )
        
        if dlg.ShowModal() == wx.ID_YES:
            self.in_memory_handler.clear()
            self._populate_grid()
        
        dlg.Destroy()
    
    def _on_save(self, event: wx.CommandEvent) -> None:
        """Handle save button click."""
        # Show a file dialog
        with wx.FileDialog(
            self,
            _("Save Log"),
            wildcard="Log files (*.log)|*.log",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            
            # Save the log
            path = file_dialog.GetPath()
            self._save_log(path)
    
    def _save_log(self, path: str) -> None:
        """Save the log to a file."""
        # Get the selected level
        level_idx = self.level_choice.GetSelection()
        level = None
        if level_idx > 0:
            level = self.level_choice.GetString(level_idx)
        
        # Get the records
        records = self.in_memory_handler.get_records(level)
        
        # Write the records to the file
        with open(path, 'w') as f:
            for record in records:
                f.write(f"{record.timestamp} - {record.level} - {record.name} - {record.message}\n")
                if record.exc_info:
                    f.write(f"{record.exc_info}\n")
        
        # Show a success message
        wx.MessageBox(
            _("Log saved successfully."),
            _("Save Log"),
            wx.OK | wx.ICON_INFORMATION
        )
    
    def _on_close(self, event: wx.CloseEvent) -> None:
        """Handle frame close."""
        # Stop the timer
        self.timer.Stop()
        
        # Hide the frame instead of closing it
        self.Hide()
    
    def _on_timer(self, event: wx.TimerEvent) -> None:
        """Handle timer event."""
        # Refresh the grid
        self._populate_grid()

class EnhancedLogger:
    """Enhanced logger for InVesalius."""
    
    def __init__(self):
        """Initialize the enhanced logger."""
        self._config = DEFAULT_LOG_CONFIG.copy()
        self._logger = logging.getLogger("invesalius")
        self._in_memory_handler = InMemoryHandler()
        self._logger.addHandler(self._in_memory_handler)
        self._log_viewer_frame = None
        
        # Create the log directory if it doesn't exist
        os.makedirs(inv_paths.USER_LOG_DIR, exist_ok=True)
        
        # Read the configuration file if it exists
        self._read_config()
        
        # Configure logging
        self._configure_logging()
    
    def _read_config(self) -> None:
        """Read the logging configuration from the config file."""
        try:
            if os.path.exists(LOG_CONFIG_PATH):
                with open(LOG_CONFIG_PATH, 'r') as f:
                    config = json.load(f)
                    self._config = deep_merge_dict(self._config.copy(), config)
        except Exception as e:
            print(f"Error reading log config: {e}")
    
    def _write_config(self) -> None:
        """Write the logging configuration to the config file."""
        try:
            with open(LOG_CONFIG_PATH, 'w') as f:
                json.dump(self._config, f, indent=4)
        except Exception as e:
            print(f"Error writing log config: {e}")
    
    def _configure_logging(self) -> None:
        """Configure logging based on the configuration."""
        try:
            # Configure logging
            logging.config.dictConfig(self._config)
            
            # Get the logger
            self._logger = logging.getLogger("invesalius")
            
            # Add the in-memory handler if it's not already added
            if not any(isinstance(h, InMemoryHandler) for h in self._logger.handlers):
                self._logger.addHandler(self._in_memory_handler)
            
            # Log the configuration
            self._logger.info("Logging configured")
        except Exception as e:
            print(f"Error configuring logging: {e}")
    
    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """Get a logger."""
        if name is None:
            return self._logger
        
        return logging.getLogger(f"invesalius.{name}")
    
    def show_log_viewer(self, parent: Optional[wx.Window] = None) -> None:
        """Show the log viewer."""
        if self._log_viewer_frame is None:
            self._log_viewer_frame = LogViewerFrame(parent, self._in_memory_handler)
        
        self._log_viewer_frame.Show()
        self._log_viewer_frame.Raise()
    
    def set_level(self, level: Union[str, int]) -> None:
        """Set the logging level."""
        self._logger.setLevel(level)
        
        # Update the configuration
        self._config["loggers"]["invesalius"]["level"] = level if isinstance(level, str) else logging.getLevelName(level)
        
        # Write the configuration
        self._write_config()
    
    def get_level(self) -> int:
        """Get the logging level."""
        return self._logger.level
    
    def set_file_logging(self, enabled: bool) -> None:
        """Enable or disable file logging."""
        # Update the configuration
        if enabled:
            if "file" not in self._config["handlers"]:
                self._config["handlers"]["file"] = {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "DEBUG",
                    "formatter": "detailed",
                    "filename": DEFAULT_LOGFILE,
                    "maxBytes": 10485760,  # 10MB
                    "backupCount": 5,
                    "encoding": "utf8"
                }
            
            if "file" not in self._config["loggers"]["invesalius"]["handlers"]:
                self._config["loggers"]["invesalius"]["handlers"].append("file")
        else:
            if "file" in self._config["loggers"]["invesalius"]["handlers"]:
                self._config["loggers"]["invesalius"]["handlers"].remove("file")
        
        # Reconfigure logging
        self._configure_logging()
        
        # Write the configuration
        self._write_config()
    
    def set_console_logging(self, enabled: bool) -> None:
        """Enable or disable console logging."""
        # Update the configuration
        if enabled:
            if "console" not in self._config["handlers"]:
                self._config["handlers"]["console"] = {
                    "class": "logging.StreamHandler",
                    "level": "INFO",
                    "formatter": "simple",
                    "stream": "ext://sys.stdout"
                }
            
            if "console" not in self._config["loggers"]["invesalius"]["handlers"]:
                self._config["loggers"]["invesalius"]["handlers"].append("console")
        else:
            if "console" in self._config["loggers"]["invesalius"]["handlers"]:
                self._config["loggers"]["invesalius"]["handlers"].remove("console")
        
        # Reconfigure logging
        self._configure_logging()
        
        # Write the configuration
        self._write_config()
    
    def set_log_file(self, path: str) -> None:
        """Set the log file path."""
        # Update the configuration
        if "file" in self._config["handlers"]:
            self._config["handlers"]["file"]["filename"] = path
        
        # Reconfigure logging
        self._configure_logging()
        
        # Write the configuration
        self._write_config()
    
    def get_log_file(self) -> str:
        """Get the log file path."""
        if "file" in self._config["handlers"]:
            return self._config["handlers"]["file"]["filename"]
        
        return DEFAULT_LOGFILE

# Create the enhanced logger instance
enhanced_logger = EnhancedLogger()

# Function to get the enhanced logger
def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger."""
    return enhanced_logger.get_logger(name)

# Function to show the log viewer
def show_log_viewer(parent: Optional[wx.Window] = None) -> None:
    """Show the log viewer."""
    enhanced_logger.show_log_viewer(parent)

# Function to set the logging level
def set_level(level: Union[str, int]) -> None:
    """Set the logging level."""
    enhanced_logger.set_level(level)

# Function to get the logging level
def get_level() -> int:
    """Get the logging level."""
    return enhanced_logger.get_level()

# Function to enable or disable file logging
def set_file_logging(enabled: bool) -> None:
    """Enable or disable file logging."""
    enhanced_logger.set_file_logging(enabled)

# Function to enable or disable console logging
def set_console_logging(enabled: bool) -> None:
    """Enable or disable console logging."""
    enhanced_logger.set_console_logging(enabled)

# Function to set the log file path
def set_log_file(path: str) -> None:
    """Set the log file path."""
    enhanced_logger.set_log_file(path)

# Function to get the log file path
def get_log_file() -> str:
    """Get the log file path."""
    return enhanced_logger.get_log_file()

# Register a menu handler for the log viewer
def register_menu_handler() -> None:
    """Register a menu handler for the log viewer."""
    Publisher.subscribe(show_log_viewer, "Show log viewer") 