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

import sys

import gdcm

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
from invesalius.enhanced_logging import get_logger
from invesalius.error_handling import DicomError, handle_errors, ErrorCategory

# Initialize logger for this module
logger = get_logger("invesalius.reader.dicom_grouper")

ORIENT_MAP = {"SAGITTAL": 0, "CORONAL": 1, "AXIAL": 2, "OBLIQUE": 2}


class DicomGroup:
    general_index = -1

    def __init__(self):
        DicomGroup.general_index += 1
        self.index = DicomGroup.general_index
        # key:
        # (dicom.patient.name, dicom.acquisition.id_study,
        #  dicom.acquisition.series_number,
        #  dicom.image.orientation_label, index)
        self.key = ()
        self.title = ""
        self.slices_dict = {}  # slice_position: Dicom.dicom
        # IDEA (13/10): Represent internally as dictionary,
        # externally as list
        self.nslices = 0
        self.zspacing = 1
        self.dicom = None
        
        logger.debug(f"Created DicomGroup with index {self.index}")

    @handle_errors(error_message="Error adding slice to DICOM group", category=ErrorCategory.DICOM)
    def AddSlice(self, dicom):
        if not self.dicom:
            self.dicom = dicom

        pos = tuple(dicom.image.position)
        
        logger.debug(f"Adding slice at position {pos} to group {self.index}")

        # Case to test: \other\higroma
        # condition created, if any dicom with the same
        # position, but 3D, leaving the same series.
        if "DERIVED" not in dicom.image.type:
            # if any dicom with the same position
            if pos not in self.slices_dict.keys():
                self.slices_dict[pos] = dicom
                self.nslices += dicom.image.number_of_frames
                logger.debug(f"Added slice to group {self.index}, total slices: {self.nslices}")
                return True
            else:
                logger.warning(f"Position {pos} already exists in group {self.index}, skipping slice")
                return False
        else:
            self.slices_dict[dicom.image.number] = dicom
            self.nslices += dicom.image.number_of_frames
            logger.debug(f"Added derived slice to group {self.index}, total slices: {self.nslices}")
            return True

    def GetList(self):
        # Should be called when user selects this group
        # This list will be used to create the vtkImageData
        # (interpolated)
        return self.slices_dict.values()

    @handle_errors(error_message="Error getting filenames from DICOM group", category=ErrorCategory.DICOM)
    def GetFilenameList(self):
        # Should be called when user selects this group
        # This list will be used to create the vtkImageData
        # (interpolated)
        
        logger.debug(f"Getting filename list for group {self.index} with {self.nslices} slices")
        
        try:
            if _has_win32api:
                filelist = [
                    win32api.GetShortPathName(dicom.image.file) for dicom in self.slices_dict.values()
                ]
            else:
                filelist = [dicom.image.file for dicom in self.slices_dict.values()]

            # Sort slices using GDCM
            # if (self.dicom.image.orientation_label != "CORONAL"):
            # Organize reversed image
            sorter = gdcm.IPPSorter()
            sorter.SetComputeZSpacing(True)
            sorter.SetZSpacingTolerance(1e-10)
            try:
                sorter.Sort([utils.encode(i, const.FS_ENCODE) for i in filelist])
            except TypeError:
                sorter.Sort(filelist)
            filelist = sorter.GetFilenames()

            # for breast-CT of koning manufacturing (KBCT)
            if list(self.slices_dict.values())[0].parser.GetManufacturerName() == "Koning":
                logger.info("Sorting Koning breast-CT files by filename")
                filelist.sort()
                
            logger.debug(f"Successfully obtained {len(filelist)} sorted filenames for group {self.index}")
            return filelist
        except Exception as e:
            logger.error(f"Failed to get filename list for group {self.index}: {str(e)}")
            raise DicomError(f"Failed to get filename list: {str(e)}",
                         details={"group_index": self.index, "slice_count": self.nslices},
                         original_exception=e)

    def GetHandSortedList(self):
        # This will be used to fix problem 1, after merging
        # single DicomGroups of same study_id and orientation
        list_ = list(self.slices_dict.values())
        # dicom = list_[0]
        # axis = ORIENT_MAP[dicom.image.orientation_label]
        # list_ = sorted(list_, key = lambda dicom:dicom.image.position[axis])
        list_ = sorted(list_, key=lambda dicom: dicom.image.number)
        return list_

    @handle_errors(error_message="Error updating Z spacing", category=ErrorCategory.DICOM)
    def UpdateZSpacing(self):
        list_ = self.GetHandSortedList()

        if len(list_) > 1:
            dicom = list_[0]
            axis = ORIENT_MAP[dicom.image.orientation_label]
            p1 = dicom.image.position[axis]

            dicom = list_[1]
            p2 = dicom.image.position[axis]

            self.zspacing = abs(p1 - p2)
            logger.debug(f"Updated Z spacing for group {self.index} to {self.zspacing}")
        else:
            self.zspacing = 1
            logger.debug(f"Not enough slices to calculate Z spacing in group {self.index}, using default value 1.0")

    def GetDicomSample(self):
        size = len(self.slices_dict)
        dicom = self.GetHandSortedList()[size // 2]
        return dicom


class PatientGroup:
    def __init__(self):
        # key:
        # (dicom.patient.name, dicom.patient.id)
        self.key = ()
        self.groups_dict = {}  # group_key: DicomGroup
        self.nslices = 0
        self.ngroups = 0
        self.dicom = None
        logger.debug("Created PatientGroup")

    @handle_errors(error_message="Error adding file to patient group", category=ErrorCategory.DICOM)
    def AddFile(self, dicom, index=0):
        # Given general DICOM information, we group slices according
        # to main series information (group_key)

        # WARN: This was defined after years of experience
        # (2003-2009), so THINK TWICE before changing group_key

        # Problem 2 is being fixed by the way this method is
        # implemented, dinamically during new dicom's addition
        group_key = (
            dicom.patient.name,
            dicom.acquisition.id_study,
            dicom.acquisition.serie_number,
            dicom.image.orientation_label,
            index,
        )  # This will be used to deal with Problem 2
        if not self.dicom:
            self.dicom = dicom

        self.nslices += 1
        logger.debug(f"Adding DICOM file to PatientGroup, group key: {group_key}, index: {index}")
        
        try:
            # Does this group exist? Best case ;)
            if group_key not in self.groups_dict.keys():
                group = DicomGroup()
                group.key = group_key
                group.title = dicom.acquisition.series_description
                group.AddSlice(dicom)
                self.ngroups += 1
                self.groups_dict[group_key] = group
                logger.debug(f"Created new group for key {group_key}, total groups: {self.ngroups}")
            # Group exists... Lets try to add slice
            else:
                group = self.groups_dict[group_key]
                slice_added = group.AddSlice(dicom)
                if not slice_added:
                    # If we're here, then Problem 2 occured
                    logger.info(f"Problem 2 detected: duplicate position in group. Trying with index+1 ({index+1})")
                    # TODO: Optimize recursion
                    self.AddFile(dicom, index + 1)
                else:
                    # Getting the spacing in the Z axis
                    group.UpdateZSpacing()
        except Exception as e:
            logger.error(f"Error adding file to patient group: {str(e)}")
            raise

    @handle_errors(error_message="Error updating patient group", category=ErrorCategory.DICOM)
    def Update(self):
        # Ideally, AddFile would be sufficient for splitting DICOM
        # files into groups (series). However, this does not work for
        # acquisitions / equipments and manufacturers.

        # Although DICOM is a protocol, each one uses its fields in a
        # different manner

        # Check if Problem 1 occurs (n groups with 1 slice each)
        is_there_problem_1 = False
        logger.debug(f"Updating PatientGroup: slices={self.nslices}, groups={len(self.groups_dict)}")
        
        if (self.nslices == len(self.groups_dict)) and (self.nslices > 1):
            is_there_problem_1 = True
            logger.info("Problem 1 detected: number of slices equals number of groups, need to fix")

        # Fix Problem 1
        if is_there_problem_1:
            logger.debug("Fixing Problem 1...")
            try:
                self.groups_dict = self.FixProblem1(self.groups_dict)
                logger.info(f"Problem 1 fixed. New group count: {len(self.groups_dict)}")
            except Exception as e:
                logger.error(f"Failed to fix Problem 1: {str(e)}")
                raise DicomError(f"Failed to fix DICOM groups with Problem 1: {str(e)}",
                             details={"slice_count": self.nslices, "original_group_count": len(self.groups_dict)},
                             original_exception=e)

    def GetGroups(self):
        logger.debug(f"Returning {len(self.groups_dict)} groups from PatientGroup")
        return self.groups_dict.values()

    def GetDicomSample(self):
        return self.dicom

    @handle_errors(error_message="Error fixing DICOM grouping (Problem 1)", category=ErrorCategory.DICOM)
    def FixProblem1(self, dict):
        """
        If we have n groups with 1 slice each, it's most likely
        that we have Problem 1, i.e., dicom.image.number and dicom.
        acquisition.serie_number were swapped
        """
        logger.debug("Attempting to fix Problem 1 (single slices in multiple groups)")
        
        first_group = next(iter(dict.values()))
        dicom_sample = first_group.dicom

        id_study = dicom_sample.acquisition.id_study

        orientation_labels = []
        # Getting distinct orientations
        for group in dict.values():
            if group.dicom.image.orientation_label not in orientation_labels:
                orientation_labels.append(group.dicom.image.orientation_label)

        study_grouped_dict = {}

        # New dict: orientations with dicom used as values
        for orientation in orientation_labels:
            study_oriented_dict = {}
            for key, group in dict.items():
                if group.dicom.image.orientation_label == orientation:
                    study_oriented_dict[key] = group
            study_grouped_dict[orientation] = study_oriented_dict

        ordered_dict = {}

        logger.debug(f"Found {len(orientation_labels)} distinct orientations to process")
        
        # Solving Problem 1 for each orientation
        for orientation, oriented_dict in study_grouped_dict.items():
            patients_dict = {}

            logger.debug(f"Processing orientation: {orientation}")

            # Dictionary containing patient's name and dicoms from an orientation
            for key, group in oriented_dict.items():
                dicom = group.dicom
                patient_key = (dicom.patient.name, dicom.patient.id)
                if not (patient_key in patients_dict.keys()):
                    patients_dict[patient_key] = [dicom]
                else:
                    patients_dict[patient_key].append(dicom)

            # Create dictionary for each patient
            for patient_key, dicoms in patients_dict.items():
                # Just one dicom for patient, add to ordered_dict
                if len(dicoms) == 1:
                    logger.debug(f"Single DICOM for patient {patient_key} in orientation {orientation}")
                    dicom = dicoms[0]
                    group_key = (
                        dicom.patient.name,
                        dicom.acquisition.id_study,
                        dicom.acquisition.serie_number,
                        dicom.image.orientation_label,
                        0,
                    )
                    # Add existing group to ordered_dict
                    for key, group in dict.items():
                        if key == group_key:
                            ordered_dict[key] = group
                            break
                # Problem 1 detected
                else:
                    logger.info(f"Problem 1 detected for patient {patient_key}, orientation {orientation}: merging {len(dicoms)} slices")
                    
                    # Use first dicom as sample, assuming they're all from the same study
                    dicom = dicoms[0]

                    # Create key for merged group
                    group_key = (
                        dicom.patient.name,
                        dicom.acquisition.id_study,
                        dicom.acquisition.serie_number,
                        dicom.image.orientation_label,
                        0,
                    )

                    # Sort list by instance_number (necessary for
                    # identifying position)
                    dicom_list = sorted(dicoms, key=lambda x: x.image.number)

                    # Create group for this study
                    group = DicomGroup()
                    group.key = group_key
                    group.title = dicom.acquisition.series_description
                    for i, dicom in enumerate(dicom_list):
                        # TODO: Check if could generate Problem 2
                        group.AddSlice(dicom)

                    # Add to dict
                    ordered_dict[group_key] = group

        logger.info(f"Problem 1 fixed. Reduced groups from {len(dict)} to {len(ordered_dict)}")
        return ordered_dict


class DicomPatientGrouper:
    """
    Helps to merge / sort DICOM slices given multiple files.
    Given many DICOM slices, it creates multiple structures:
    first splits into Patients > Patient Groups > Group (each group
    is a DicomGroup, containing several slices)
    """

    def __init__(self):
        self.patients_dict = {}  # key: (name, id)
        logger.debug("Initialized DicomPatientGrouper")

    @handle_errors(error_message="Error adding file to DICOM patient grouper", category=ErrorCategory.DICOM)
    def AddFile(self, dicom):
        """
        Given a DICOM file, organizes it in the directory structure:
        Patient > Patient Group > Group
        """
        patient_key = (dicom.patient.name, dicom.patient.id)
        
        logger.debug(f"Adding file to patient {patient_key}")
        
        try:
            # Does this patient exist?
            if patient_key not in self.patients_dict.keys():
                # Create new Patient
                patient = PatientGroup()
                patient.key = patient_key
                self.patients_dict[patient_key] = patient
                logger.debug(f"Created new patient group for {patient_key}")
            else:
                # Get existing Patient
                patient = self.patients_dict[patient_key]

            # Add dicom to Patient
            patient.AddFile(dicom)
        except Exception as e:
            logger.error(f"Error adding file to patient grouper: {str(e)}")
            raise

    def Update(self):
        logger.debug("Updating all patient groups")
        # Fix some problems
        for patient in self.patients_dict.values():
            patient.Update()

    @handle_errors(error_message="Error getting patient groups", category=ErrorCategory.DICOM)
    def GetPatientsGroups(self):
        """
        Get all patients groups given all DICOM files included so far.
        """
        logger.debug(f"Getting all patient groups from {len(self.patients_dict)} patients")
        patients_groups = []
        
        try:
            for patient in self.patients_dict.values():
                groups = patient.GetGroups()
                if groups:
                    patients_groups.append(patient)
                    
            logger.info(f"Successfully obtained {len(patients_groups)} patient groups")
            return patients_groups
        except Exception as e:
            logger.error(f"Error getting patient groups: {str(e)}")
            raise DicomError(f"Failed to get patient groups: {str(e)}",
                         details={"patient_count": len(self.patients_dict)},
                         original_exception=e)
