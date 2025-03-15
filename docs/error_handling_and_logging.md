# Enhanced Error Handling and Logging System for InVesalius

This document describes the enhanced error handling and logging system implemented for InVesalius.

## Overview

The enhanced error handling and logging system provides a comprehensive solution for handling errors and logging in InVesalius. It includes:

- Custom exception classes for different types of errors
- Error handling decorators for functions and methods
- User-friendly error messages
- Integration with the logging system
- Crash reporting functionality
- Log viewing GUI

## Error Handling

### Custom Exception Classes

The system defines a hierarchy of custom exception classes for different types of errors:

- `InVesaliusException`: Base exception class for all InVesalius exceptions
- `IOError`: Exception raised for I/O errors
- `DicomError`: Exception raised for DICOM-related errors
- `SegmentationError`: Exception raised for segmentation-related errors
- `SurfaceError`: Exception raised for surface-related errors
- `RenderingError`: Exception raised for rendering-related errors
- `NavigationError`: Exception raised for navigation-related errors
- `PluginError`: Exception raised for plugin-related errors
- `MemoryError`: Exception raised for memory-related errors

Each exception class includes:

- A message describing the error
- A category indicating the type of error
- A severity level indicating the severity of the error
- Details about the error, such as the file, line number, and traceback
- The original exception that caused the error, if applicable

### Error Categories

Errors are categorized into the following categories:

- `GENERAL`: General errors
- `IO`: I/O errors
- `DICOM`: DICOM-related errors
- `SEGMENTATION`: Segmentation-related errors
- `SURFACE`: Surface-related errors
- `RENDERING`: Rendering-related errors
- `NAVIGATION`: Navigation-related errors
- `PLUGIN`: Plugin-related errors
- `NETWORK`: Network-related errors
- `CONFIGURATION`: Configuration-related errors
- `USER_INTERFACE`: User interface-related errors
- `MEMORY`: Memory-related errors
- `PERFORMANCE`: Performance-related errors
- `HARDWARE`: Hardware-related errors
- `EXTERNAL_LIBRARY`: External library-related errors

### Error Severity Levels

Errors are assigned a severity level:

- `DEBUG`: Debug-level errors
- `INFO`: Informational errors
- `WARNING`: Warning-level errors
- `ERROR`: Error-level errors
- `CRITICAL`: Critical errors

### Error Handling Decorator

The system provides a decorator for handling errors in functions and methods:

```python
@handle_errors(
    error_message="Error message",
    show_dialog=True,
    log_error=True,
    reraise=False,
    expected_exceptions=(Exception,),
    category=ErrorCategory.GENERAL,
    severity=ErrorSeverity.ERROR
)
def my_function():
    # Function code
```

The decorator:

- Catches exceptions raised by the function
- Creates a detailed error message
- Logs the error
- Shows an error dialog to the user
- Publishes an error event
- Optionally reraises the exception

### Error Dialog

When an error occurs, an error dialog is shown to the user. The dialog includes:

- The error message
- Details about the error, such as the file, line number, and traceback
- System information
- A button to create a crash report

### Crash Reporting

The system can create crash reports for errors. Crash reports include:

- The error message
- The error category and severity
- System information
- Details about the error
- The traceback

Crash reports are saved in the user's log directory.

### Global Exception Handler

The system includes a global exception handler for unhandled exceptions. The handler:

- Logs the exception
- Creates a crash report
- Shows an error dialog to the user

## Logging

### Enhanced Logging

The enhanced logging system provides:

- Structured logging with different levels
- Log rotation
- Log filtering
- Log viewing GUI
- Integration with the error handling system

### Logging Levels

The system supports the standard Python logging levels:

- `DEBUG`: Detailed information, typically of interest only when diagnosing problems
- `INFO`: Confirmation that things are working as expected
- `WARNING`: An indication that something unexpected happened, or indicative of some problem in the near future
- `ERROR`: Due to a more serious problem, the software has not been able to perform some function
- `CRITICAL`: A serious error, indicating that the program itself may be unable to continue running

### Log Rotation

The system supports log rotation, which:

- Creates a new log file when the current log file reaches a certain size
- Keeps a specified number of backup log files
- Deletes the oldest log files when the number of backup log files exceeds the specified limit

### Log Filtering

The log viewer allows filtering logs by level.

### Log Viewing GUI

The system includes a GUI for viewing logs. The GUI:

- Displays logs in a grid
- Allows filtering logs by level
- Shows details about selected log entries
- Allows saving logs to a file
- Allows clearing the log

### Integration with Error Handling

The logging system is integrated with the error handling system. When an error occurs:

- The error is logged
- The error details are included in the log
- The error traceback is included in the log

## Usage

### Error Handling

To use the error handling system:

1. Import the necessary classes and functions:

```python
from invesalius.error_handling import (
    ErrorCategory,
    ErrorSeverity,
    InVesaliusException,
    handle_errors,
    show_error_dialog
)
```

2. Use the error handling decorator:

```python
@handle_errors(
    error_message="Error message",
    show_dialog=True,
    log_error=True,
    reraise=False,
    expected_exceptions=(Exception,),
    category=ErrorCategory.GENERAL,
    severity=ErrorSeverity.ERROR
)
def my_function():
    # Function code
```

3. Or handle errors manually:

```python
try:
    # Code that might raise an exception
except Exception as e:
    # Create an InVesalius exception
    inv_exception = InVesaliusException(
        "Error message",
        category=ErrorCategory.GENERAL,
        severity=ErrorSeverity.ERROR,
        details={
            "function": "my_function",
            "exception_type": type(e).__name__,
            "exception_message": str(e),
            "traceback": traceback.format_exc()
        },
        original_exception=e
    )
    
    # Show an error dialog
    show_error_dialog("Error message", inv_exception)
    
    # Log the error
    logger.error("Error message", exc_info=True)
```

### Logging

To use the enhanced logging system:

1. Import the necessary functions:

```python
from invesalius import enhanced_logging
```

2. Get a logger:

```python
logger = enhanced_logging.get_logger("my_module")
```

3. Log messages:

```python
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical message")
```

4. Show the log viewer:

```python
enhanced_logging.show_log_viewer(parent_window)
```

5. Configure logging:

```python
# Set the logging level
enhanced_logging.set_level(logging.DEBUG)

# Enable or disable file logging
enhanced_logging.set_file_logging(True)

# Enable or disable console logging
enhanced_logging.set_console_logging(True)

# Set the log file path
enhanced_logging.set_log_file("/path/to/log/file.log")
```

## Implementation Details

The enhanced error handling and logging system is implemented in the following files:

- `invesalius/error_handling.py`: Contains the error handling system
- `invesalius/enhanced_logging.py`: Contains the enhanced logging system
- `invesalius/test_error_handling.py`: Contains tests for the error handling and logging system

The system is initialized in `app.py` and integrated with the InVesalius GUI in `invesalius/gui/frame.py`.

## Benefits

The enhanced error handling and logging system provides several benefits:

- Improved error handling: Errors are handled consistently throughout the application
- Better error messages: Error messages are more informative and user-friendly
- Crash reporting: Crash reports help diagnose and fix errors
- Enhanced logging: Structured logging with different levels helps diagnose problems
- Log viewing: The log viewer makes it easy to view and filter logs
- Integration: The error handling and logging systems are integrated for a seamless experience

## Future Improvements

Potential future improvements to the system include:

- Remote crash reporting: Send crash reports to a server for analysis
- Error analytics: Analyze crash reports to identify common errors
- Log analysis: Analyze logs to identify performance issues
- Log search: Search logs for specific messages
- Log export: Export logs in different formats
- Log filtering by date: Filter logs by date range
- Log filtering by source: Filter logs by source module
- Log filtering by message: Filter logs by message content
- Log filtering by exception: Filter logs by exception type
- Log filtering by severity: Filter logs by severity level
- Log filtering by category: Filter logs by error category 