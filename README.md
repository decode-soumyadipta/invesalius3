[![PythonVersion](https://img.shields.io/badge/python-3.8-blue)](https://www.python.org/downloads/release/python-380/)
# InVesalius

InVesalius generates 3D medical imaging reconstructions based on a sequence of 2D DICOM files acquired with CT or MRI equipments.  InVesalius is internationalized (currently available in English, Portuguese, French, German, Spanish, Catalan, Romanian, Korean, Italian and Czech), multi-platform (GNU Linux, Windows and MacOS) and provides several tools:
  * DICOM-support including: (a) ACR-NEMA version 1 and 2; (b) DICOM version 3.0 (including various encodings of JPEG -lossless and lossy-, RLE)
  * Support to Analyze files
  * Support to BMP, PNG, JPEG and TIF files
  * Image manipulation facilities (zoom, pan, rotation, brightness/contrast, etc)
  * Segmentation based on 2D slices
  * Pre-defined threshold ranges according to tissue of interest
  * Segmentation based on watershed
  * Edition tools (similar to Paint Brush) based on 2D slices
  * Linear and angular measurement tool
  * Volume reorientation tool
  * 3D surface creation
  * 3D surface volume measurement
  * 3D surface connectivity tools
  * 3D surface exportation (including: binary and ASCII STL, PLY, OBJ, VRML, Inventor)
  * High-quality volume rendering projection
  * Pre-defined volume rendering presets
  * Volume rendering crop plane
  * Picture exportation (including: BMP, TIFF, JPG, PostScript, POV-Ray)

### Development

* [Running InVesalius 3 in Linux](https://github.com/invesalius/invesalius3/wiki/Running-InVesalius-3-in-Linux)
* [Running InVesalius 3 in Mac](https://github.com/invesalius/invesalius3/wiki/Running-InVesalius-3-in-Mac)
* [Running InVesalius 3 in Windows](https://github.com/invesalius/invesalius3/wiki/Running-InVesalius-3-in-Windows)

The source code is available in this repository. Please read the
[contribute](CONTRIBUTE.md) file for more information.

## New Features
### Error Handling and Logging System
InVesalius 3 now includes a centralized error handling and logging system that improves the reliability and user experience of the application. This feature provides:
- Structured error reporting with detailed context
- Consistent error handling across the application
- Enhanced logging with configurable levels
- User-friendly error messages and recovery options

### Connection Status Dashboard
The Connection Status Dashboard is a diagnostic tool that provides real-time monitoring and troubleshooting capabilities for hardware devices connected to the system. This feature helps users identify and resolve connection issues with:
- Navigation trackers
- Cameras and other peripheral devices
- Serial ports
- Network connections

Key capabilities include:
- Real-time status monitoring of all connected devices
- Connection event history tracking
- Diagnostic tests for verifying proper device functioning
- Detailed error information and troubleshooting guidance

To access the Dashboard, select `Tools > Connection Status Dashboard` from the main menu.

## License

Copyright (c) 2007-2023 Renato Archer Information Technology Center

This software is FREE FOR NON-COMMERCIAL USE, please contact us for
commercial use.
