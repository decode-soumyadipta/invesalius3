# ---------------------------------------------------------------------
# Software: InVesalius Software de Reconstrucao 3D de Imagens Medicas

# Copyright: (c) 2001  Centro de Pesquisas Renato Archer
# Homepage: http://www.softwarepublico.gov.br
# Contact:  invesalius@cenpra.gov.br
# License:  GNU - General Public License version 2 (LICENSE.txt/
#                                                         LICENCA.txt)
#
#    Este programa eh software livre; voce pode redistribui-lo e/ou
#    modifica-lo sob os termos da Licenca Publica Geral GNU, conforme
#    publicada pela Free Software Foundation; de acordo com a versao 2
#    da Licenca.
#
#    Este programa eh distribuido na expectativa de ser util, mas SEM
#    QUALQUER GARANTIA; sem mesmo a garantia implicita de
#    COMERCIALIZACAO ou de ADEQUACAO A QUALQUER PROPOSITO EM
#    PARTICULAR. Consulte a Licenca Publica Geral GNU para obter mais
#    detalhes.
# ---------------------------------------------------------------------


# ---------------------------------------------------------
# PROBLEM 1
# There are times when there are lots of groups on dict, but
# each group contains only one slice (DICOM file).
#
# Equipments / manufacturer:
# TODO
#
# Cases:
# TODO 0031, 0056, 1093
#
# What occurs in these cases:
# <dicom.image.number> and <dicom.acquisition.series_number>
# were swapped


# -----------------------------------------------------------
# PROBLEM 2
# Two slices (DICOM file) inside a group have the same
# position.
#
# Equipments / manufacturer:
# TODO
#
# Cases:
# TODO 0031, 0056, 1093
#
# What occurs in these cases:
# <dicom.image.number> and <dicom.acquisition.series_number>
# were swapped

import logging
import sys

import gdcm

from invesalius.enhanced_logging import get_logger
from invesalius.error_handling import (
    DicomError,
    ErrorCategory,
    ErrorSeverity,
    handle_errors,
)

# Initialize logger
logger = get_logger("reader.dicom_grouper")

if sys.platform == "win32":
    try:
        import win32api

        _has_win32api = True
    except ImportError:
        _has_win32api = False
else:
    _has_win32api = False

import invesalius.constants as const
import invesalius.utils as utils

ORIENT_MAP = {"SAGITTAL": 0, "CORONAL": 1, "AXIAL": 2, "OBLIQUE": 2}


class DicomGroup:
    general_index = -1

    def __init__(self):
        self.slices_dict = {}
        self.nslices = 0
        self.dicom = None
        self.zspacing = 0
        self.title = ""
        self.index = DicomGroup.general_index = DicomGroup.general_index + 1

    def AddSlice(self, dicom):
        """Add a DICOM slice to the group."""
        try:
            self.slices_dict[dicom.image.number] = dicom
            self.nslices += 1
            self.dicom = dicom
            logger.debug(f"Added slice {dicom.image.number} to group {self.index}")
        except Exception as e:
            logger.error(f"Error adding slice to group {self.index}: {str(e)}", exc_info=True)
            raise DicomError(
                "Failed to add DICOM slice to group",
                details={"group_index": self.index, "slice_number": dicom.image.number},
                original_exception=e,
            )

    def GetList(self):
        """Get list of DICOM slices for creating vtkImageData."""
        try:
            slices = list(self.slices_dict.values())
            logger.debug(f"Retrieved {len(slices)} slices from group {self.index}")
            return slices
        except Exception as e:
            logger.error(f"Error getting slice list from group {self.index}: {str(e)}", exc_info=True)
            return []

    def GetFilenameList(self):
        """Get list of DICOM filenames for creating vtkImageData."""
        try:
            if not self.slices_dict:
                logger.error(f"No DICOM files found in group {self.index}")
                return []

            if _has_win32api:
                try:
                    filelist = [
                        win32api.GetShortPathName(dicom.image.file)
                        for dicom in self.slices_dict.values()
                    ]
                    logger.debug(f"Using win32api GetShortPathName for {len(filelist)} files")
                except Exception as e:
                    logger.warning(f"Error using win32api: {str(e)}")
                    filelist = [dicom.image.file for dicom in self.slices_dict.values()]
            else:
                filelist = [dicom.image.file for dicom in self.slices_dict.values()]
                logger.debug(f"Using standard filenames for {len(filelist)} files")

            # Sort slices using GDCM
            sorter = gdcm.IPPSorter()
            sorter.SetComputeZSpacing(True)
            sorter.SetZSpacingTolerance(1e-10)
            try:
                sorter.Sort([utils.encode(i, const.FS_ENCODE) for i in filelist])
                logger.debug("Successfully sorted files using GDCM IPPSorter")
            except TypeError:
                logger.debug("Using unencoded filenames for sorting")
                sorter.Sort(filelist)
            except Exception as e:
                logger.warning(f"Error during IPPSorter.Sort: {str(e)}")

            filelist = sorter.GetFilenames()
            logger.debug(f"Final sorted file list contains {len(filelist)} files")

            # Check if z-spacing was computed by GDCM
            spacing_computed = False
            try:
                computed_spacing = sorter.GetZSpacing()
                if computed_spacing > 0:
                    logger.debug(f"GDCM computed Z spacing: {computed_spacing}")
                    self.zspacing = computed_spacing
                    spacing_computed = True
                else:
                    logger.warning("GDCM could not compute Z spacing, will calculate manually")
            except Exception as e:
                logger.warning(f"Error retrieving computed Z spacing from GDCM: {str(e)}")

            # If GDCM failed to compute spacing, calculate it manually
            if not spacing_computed:
                logger.info("Calculating Z spacing manually from slice positions")
                self.UpdateZSpacing()
                logger.info(f"Manually calculated Z spacing: {self.zspacing}")

            # Special handling for breast-CT of koning manufacturing (KBCT)
            try:
                if list(self.slices_dict.values())[0].parser.GetManufacturerName() == "Koning":
                    logger.debug("Detected Koning manufacturer, using simple filename sort")
                    filelist.sort()
            except Exception as e:
                logger.warning(f"Error checking manufacturer name: {str(e)}")

            return filelist
        except Exception as e:
            logger.error(f"Error getting filename list from group {self.index}: {str(e)}", exc_info=True)
            return []

    def GetHandSortedList(self):
        """Get manually sorted list of DICOM slices."""
        try:
            list_ = list(self.slices_dict.values())
            list_ = sorted(list_, key=lambda dicom: dicom.image.number)
            logger.debug(f"Hand-sorted {len(list_)} slices by image number")
            return list_
        except Exception as e:
            logger.error(f"Error hand-sorting slices in group {self.index}: {str(e)}", exc_info=True)
            return []

    def UpdateZSpacing(self):
        """Update Z spacing based on slice positions."""
        try:
            list_ = self.GetHandSortedList()

            if len(list_) > 1:
                dicom = list_[0]
                axis = ORIENT_MAP.get(dicom.image.orientation_label, 2)  # Default to AXIAL if unknown
                p1 = dicom.image.position[axis]

                dicom = list_[1]
                p2 = dicom.image.position[axis]

                self.zspacing = abs(p1 - p2)
                logger.debug(f"Updated Z spacing to {self.zspacing} for group {self.index}")
            else:
                self.zspacing = 1
                logger.debug(f"Set default Z spacing of 1 for group {self.index} (single slice)")
        except Exception as e:
            logger.error(f"Error updating Z spacing for group {self.index}: {str(e)}", exc_info=True)
            self.zspacing = 1

    def GetDicomSample(self):
        """Get a representative DICOM slice from the middle of the group."""
        try:
            size = len(self.slices_dict)
            dicom = self.GetHandSortedList()[size // 2]
            logger.debug(f"Retrieved DICOM sample from middle of group {self.index} (slice {size//2})")
            return dicom
        except Exception as e:
            logger.error(f"Error getting DICOM sample from group {self.index}: {str(e)}", exc_info=True)
            return None


class PatientGroup:
    def __init__(self):
        self.groups_dict = {}
        self.ngroups = 0
        self.nslices = 0
        self.dicom = None

    def AddFile(self, dicom):
        """Add a DICOM file to the appropriate group."""
        try:
            # Get DICOM group key
            # Use equipment name if available, otherwise use "Unknown"
            try:
                equipment = dicom.acquisition.equipment_model
            except AttributeError:
                try:
                    equipment = dicom.acquisition.equipment_name
                except AttributeError:
                    equipment = "Unknown"

            # Convert series number to int if possible, otherwise use as string
            try:
                serie_number = int(dicom.acquisition.serie_number)
            except (ValueError, TypeError):
                serie_number = dicom.acquisition.serie_number

            key = (
                serie_number,
                equipment,
                dicom.image.orientation_label,
            )
            logger.debug(f"Processing DICOM file with key: {key}")

            # Create new group if it doesn't exist
            if key not in self.groups_dict:
                group = DicomGroup()
                self.groups_dict[key] = group
                self.ngroups += 1
                logger.debug(f"Created new group {group.index} for key {key}")

            # Add slice to group
            self.groups_dict[key].AddSlice(dicom)
            self.nslices += 1
            self.dicom = dicom

            # Update group title
            group = self.groups_dict[key]
            try:
                protocol_name = dicom.acquisition.protocol_name
            except AttributeError:
                protocol_name = "Unknown Protocol"

            group.title = "{} {} {}".format(
                serie_number,
                protocol_name,
                dicom.image.orientation_label,
            )
            logger.debug(f"Updated group {group.index} title to: {group.title}")

        except Exception as e:
            logger.error("Error adding DICOM file to patient group", exc_info=True)
            raise DicomError(
                "Failed to add DICOM file to patient group",
                details={"serie_number": getattr(dicom.acquisition, "serie_number", "Unknown")},
                original_exception=e,
            )

    def Update(self):
        """Update groups to handle special cases."""
        try:
            # Check if Problem 1 occurs (n groups with 1 slice each)
            is_there_problem_1 = False
            logger.debug(f"Checking for Problem 1: nslices={self.nslices}, ngroups={len(self.groups_dict)}")
            
            if (self.nslices == len(self.groups_dict)) and (self.nslices > 1):
                is_there_problem_1 = True
                logger.warning("Detected Problem 1: Each group contains only one slice")

            # Fix Problem 1
            if is_there_problem_1:
                logger.info("Attempting to fix Problem 1")
                self.groups_dict = self.FixProblem1(self.groups_dict)
                logger.info(f"After fixing Problem 1: {len(self.groups_dict)} groups remain")

        except Exception as e:
            logger.error("Error updating patient groups", exc_info=True)
            raise DicomError(
                "Failed to update patient groups",
                details={"ngroups": len(self.groups_dict), "nslices": self.nslices},
                original_exception=e,
            )

    def GetGroups(self):
        """Get sorted list of DICOM groups."""
        try:
            glist = self.groups_dict.values()
            glist = sorted(glist, key=lambda group: group.title, reverse=True)
            logger.debug(f"Retrieved {len(glist)} sorted groups")
            return glist
        except Exception as e:
            logger.error("Error getting sorted groups", exc_info=True)
            return []

    def GetDicomSample(self):
        """Get a representative DICOM file."""
        try:
            logger.debug("Retrieved DICOM sample from patient group")
            return self.dicom
        except Exception as e:
            logger.error("Error getting DICOM sample from patient group", exc_info=True)
            return None

    def FixProblem1(self, dict):
        """
        Merge multiple DICOM groups in case Problem 1 (description
        above) occurs.

        WARN: We've implemented an heuristic to try to solve
        the problem. There is no scientific background and this aims
        to be a workaround to exams which are not in conformance with
        the DICOM protocol.
        """
        # Divide existing groups into 2 groups:
        dict_final = {}  # 1
        # those containing "3D photos" and undefined
        # orientation - these won't be changed (groups_lost).

        dict_to_change = {}  # 2
        # which can be re-grouped according to our heuristic

        # split existing groups in these two types of group, based on
        # orientation label

        # 1st STEP: RE-GROUP
        for group_key in dict:
            # values used as key of the new dictionary
            dicom = dict[group_key].GetList()[0]
            orientation = dicom.image.orientation_label
            study_id = dicom.acquisition.id_study
            # if axial, coronal or sagittal
            if orientation in ORIENT_MAP:
                group_key_s = (orientation, study_id)
                # If this method was called, there is only one slice
                # in this group (dicom)
                dicom = dict[group_key].GetList()[0]
                if group_key_s not in dict_to_change.keys():
                    group = DicomGroup()
                    group.AddSlice(dicom)
                    dict_to_change[group_key_s] = group
                else:
                    group = dict_to_change[group_key_s]
                    group.AddSlice(dicom)
            else:
                dict_final[group_key] = dict[group_key]

        # group_counter will be used as key to DicomGroups created
        # while checking differences
        group_counter = 0
        for group_key in dict_to_change:
            # 2nd STEP: SORT
            sorted_list = dict_to_change[group_key].GetHandSortedList()

            # 3rd STEP: CHECK DIFFERENCES
            axis = ORIENT_MAP[group_key[0]]  # based on orientation
            for index in range(len(sorted_list) - 1):
                current = sorted_list[index]
                # next = sorted_list[index + 1]

                pos_current = current.image.position[axis]
                pos_next = current.image.position[axis]
                spacing = current.image.spacing

                if (pos_next - pos_current) <= (spacing[2] * 2):
                    if group_counter in dict_final:
                        dict_final[group_counter].AddSlice(current)
                    else:
                        group = DicomGroup()
                        group.AddSlice(current)
                        dict_final[group_counter] = group
                        # Getting the spacing in the Z axis
                        group.UpdateZSpacing()
                else:
                    group_counter += 1
                    group = DicomGroup()
                    group.AddSlice(current)
                    dict_final[group_counter] = group
                    # Getting the spacing in the Z axis
                    group.UpdateZSpacing()

        return dict_final


class DicomPatientGrouper:
    # read file, check if it is dicom...
    # dicom = dicom.Dicom
    # grouper = DicomPatientGrouper()
    # grouper.AddFile(dicom)
    # ... (repeat to all files on folder)
    # grouper.Update()
    # groups = GetPatientGroups()

    def __init__(self):
        self.patients_dict = {}

    def AddFile(self, dicom):
        patient_key = (dicom.patient.name, dicom.patient.id)

        # Does this patient exist?
        if patient_key not in self.patients_dict.keys():
            patient = PatientGroup()
            patient.key = patient_key
            patient.AddFile(dicom)
            self.patients_dict[patient_key] = patient
        # Patient exists... Lets add group to it
        else:
            patient = self.patients_dict[patient_key]
            patient.AddFile(dicom)

    def Update(self):
        for patient in self.patients_dict.values():
            patient.Update()

    def GetPatientsGroups(self):
        """
        How to use:
        patient_list = grouper.GetPatientsGroups()
        for patient in patient_list:
            group_list = patient.GetGroups()
            for group in group_list:
                group.GetList()
                # :) you've got a list of dicom.Dicom
                # of the same series
        """
        plist = self.patients_dict.values()
        plist = sorted(plist, key=lambda patient: patient.key[0])
        return plist
