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
import os
import sys

import gdcm

# Not showing GDCM warning and debug messages
try:
    gdcm.Trace_DebugOff()
    gdcm.Trace_WarningOff()
except AttributeError:
    pass


from vtkmodules.vtkCommonCore import vtkFileOutputWindow, vtkOutputWindow

import invesalius.constants as const
import invesalius.reader.dicom as dicom
import invesalius.reader.dicom_grouper as dicom_grouper
import invesalius.utils as utils
from invesalius import inv_paths
from invesalius.data import imagedata_utils
from invesalius.pubsub import pub as Publisher
from invesalius.enhanced_logging import get_logger
from invesalius.error_handling import DicomError, handle_errors, ErrorCategory

# Initialize logger for this module
logger = get_logger("invesalius.reader.dicom_reader")

if sys.platform == "win32":
    try:
        import win32api

        _has_win32api = True
    except ImportError:
        _has_win32api = False
        logger.warning("win32api module not available, using fallback path handling")
else:
    _has_win32api = False


def SelectLargerDicomGroup(patient_group):
    maxslices = 0
    for patient in patient_group:
        group_list = patient.GetGroups()
        for group in group_list:
            if group.nslices > maxslices:
                maxslices = group.nslices
                larger_group = group

    return larger_group


@handle_errors(error_message="Error sorting DICOM files", category=ErrorCategory.DICOM)
def SortFiles(filelist, dicom):
    # Sort slices
    # FIXME: Coronal Crash. necessary verify
    # if (dicom.image.orientation_label != "CORONAL"):
    ##Organize reversed image
    logger.debug(f"Sorting {len(filelist)} DICOM files")
    sorter = gdcm.IPPSorter()
    sorter.SetComputeZSpacing(True)
    sorter.SetZSpacingTolerance(1e-10)
    
    try:
        sorter.Sort(filelist)
        # Getting organized image
        filelist = sorter.GetFilenames()
        logger.info(f"Successfully sorted {len(filelist)} DICOM files")
        return filelist
    except Exception as e:
        logger.error(f"Failed to sort DICOM files: {str(e)}")
        raise DicomError(f"Failed to sort DICOM files: {str(e)}",
                       details={"file_count": len(filelist)},
                       original_exception=e)


tag_labels = {}
main_dict = {}
dict_file = {}


class LoadDicom:
    def __init__(self, grouper, filepath):
        self.grouper = grouper
        self.filepath = utils.decode(filepath, const.FS_ENCODE)
        logger.debug(f"Initializing LoadDicom for file: {self.filepath}")
        self.run()

    @handle_errors(error_message="Error loading DICOM file", category=ErrorCategory.DICOM)
    def run(self):
        grouper = self.grouper
        reader = gdcm.ImageReader()
        
        logger.debug(f"Loading DICOM file: {self.filepath}")
        
        try:
            if _has_win32api:
                try:
                    reader.SetFileName(
                        utils.encode(win32api.GetShortPathName(self.filepath), const.FS_ENCODE)
                    )
                except TypeError:
                    reader.SetFileName(win32api.GetShortPathName(self.filepath))
            else:
                try:
                    reader.SetFileName(utils.encode(self.filepath, const.FS_ENCODE))
                except TypeError:
                    reader.SetFileName(self.filepath)
                    
            read_success = reader.Read()
            if not read_success:
                error_msg = f"Failed to read DICOM file: {self.filepath}"
                logger.error(error_msg)
                raise DicomError(error_msg, details={"filepath": self.filepath})
                
            file = reader.GetFile()
            # Retrieve data set
            dataSet = file.GetDataSet()
            # Retrieve header
            header = file.GetHeader()
            stf = gdcm.StringFilter()
            stf.SetFile(file)

            data_dict = {}

            tag = gdcm.Tag(0x0008, 0x0005)
            ds = reader.GetFile().GetDataSet()
            image_helper = gdcm.ImageHelper()
            data_dict["spacing"] = image_helper.GetSpacingValue(reader.GetFile())
            if ds.FindDataElement(tag):
                data_element = ds.GetDataElement(tag)
                if data_element.IsEmpty():
                    encoding_value = "ISO_IR 100"
                else:
                    encoding_value = str(ds.GetDataElement(tag).GetValue()).split("\\")[0]

                if encoding_value.startswith("Loaded"):
                    encoding = "ISO_IR 100"
                else:
                    try:
                        encoding = const.DICOM_ENCODING_TO_PYTHON[encoding_value]
                    except KeyError:
                        logger.warning(f"Unknown DICOM encoding: {encoding_value}, using default")
                        encoding = "ISO_IR 100"
            else:
                encoding = "ISO_IR 100"

            # Iterate through the Header
            iterator = header.GetDES().begin()
            while not iterator.equal(header.GetDES().end()):
                dataElement = iterator.next()
                if not dataElement.IsUndefinedLength():
                    tag = dataElement.GetTag()
                    data = stf.ToStringPair(tag)
                    stag = tag.PrintAsPipeSeparatedString()

                    group = str(tag.GetGroup())
                    field = str(tag.GetElement())

                    tag_labels[stag] = data[0]

                    if group not in data_dict.keys():
                        data_dict[group] = {}

                    if not (utils.VerifyInvalidPListCharacter(data[1])):
                        data_dict[group][field] = utils.decode(data[1], encoding)
                    else:
                        data_dict[group][field] = "Invalid Character"

            # Iterate through the Data set
            iterator = dataSet.GetDES().begin()
            while not iterator.equal(dataSet.GetDES().end()):
                dataElement = iterator.next()
                if not dataElement.IsUndefinedLength():
                    tag = dataElement.GetTag()
                    #  if (tag.GetGroup() == 0x0009 and tag.GetElement() == 0x10e3) \
                    #  or (tag.GetGroup() == 0x0043 and tag.GetElement() == 0x1027):
                    #  continue
                    data = stf.ToStringPair(tag)
                    stag = tag.PrintAsPipeSeparatedString()

                    group = str(tag.GetGroup())
                    field = str(tag.GetElement())

                    tag_labels[stag] = data[0]

                    if group not in data_dict.keys():
                        data_dict[group] = {}

                    if not (utils.VerifyInvalidPListCharacter(data[1])):
                        data_dict[group][field] = utils.decode(data[1], encoding, "replace")
                    else:
                        data_dict[group][field] = "Invalid Character"

            # -------------- To Create DICOM Thumbnail -----------

            try:
                data = data_dict[str(0x028)][str(0x1050)]
                level = [float(value) for value in data.split("\\")][0]
                data = data_dict[str(0x028)][str(0x1051)]
                window = [float(value) for value in data.split("\\")][0]
            except (KeyError, ValueError):
                logger.warning("Could not extract window/level values from DICOM file")
                level = None
                window = None

            img = reader.GetImage()
            try:
                thumbnail_path = imagedata_utils.create_dicom_thumbnails(img, window, level)
            except Exception as e:
                logger.warning(f"Failed to create DICOM thumbnail: {str(e)}")
                thumbnail_path = None

            # ------ Verify the orientation --------------------------------

            direc_cosines = img.GetDirectionCosines()
            orientation = gdcm.Orientation()
            try:
                _type = orientation.GetType(tuple(direc_cosines))
            except TypeError:
                _type = orientation.GetType(direc_cosines)
            label = orientation.GetLabel(_type)

            # ----------   Refactory --------------------------------------
            data_dict["invesalius"] = {"orientation_label": label}

            # -------------------------------------------------------------
            dict_file[self.filepath] = data_dict

            # ----------  Verify is DICOMDir -------------------------------
            is_dicom_dir = 1
            try:
                if data_dict[str(0x002)][str(0x002)] != "1.2.840.10008.1.3.10":  # DICOMDIR
                    is_dicom_dir = 0
            except KeyError:
                is_dicom_dir = 0

            if not (is_dicom_dir):
                parser = dicom.Parser()
                parser.SetDataImage(dict_file[self.filepath], self.filepath, thumbnail_path)

                dcm = dicom.Dicom()
                # self.l.acquire()
                dcm.SetParser(parser)
                grouper.AddFile(dcm)
                logger.debug(f"Successfully loaded DICOM file: {self.filepath}")
                # self.l.release()
        except Exception as e:
            logger.error(f"Error loading DICOM file {self.filepath}: {str(e)}")
            # Re-raise to be caught by the handle_errors decorator
            raise

        # ==========  used in test =======================================
        # print dict_file
        # main_dict = dict(
        #                data  = dict_file,
        #                labels  = tag_labels)
        # print main_dict
        # print "\n"
        # plistlib.writePlist(main_dict, ".//teste.plist")


@handle_errors(error_message="Error finding DICOM files", category=ErrorCategory.DICOM)
def yGetDicomGroups(directory, recursive=True, gui=True):
    """
    Return all full paths to DICOM files inside given directory.
    """
    nfiles = 0
    # Find total number of files
    if recursive:
        for dirpath, dirnames, filenames in os.walk(directory):
            nfiles += len(filenames)
    else:
        dirpath, dirnames, filenames = os.walk(directory)
        nfiles = len(filenames)

    counter = 0
    grouper = dicom_grouper.DicomPatientGrouper()
    # q = Queue.Queue()
    # l = threading.Lock()
    # threads = []
    # for i in xrange(cpu_count()):
    #    t = LoadDicom(grouper, q, l)
    #    t.start()
    #    threads.append(t)
    # Retrieve only DICOM files, splited into groups
    if recursive:
        for dirpath, dirnames, filenames in os.walk(directory):
            for name in filenames:
                filepath = os.path.join(dirpath, name)
                counter += 1
                if gui:
                    yield (counter, nfiles)
                LoadDicom(grouper, filepath)
    else:
        dirpath, dirnames, filenames = os.walk(directory)
        for name in filenames:
            filepath = str(os.path.join(dirpath, name))
            counter += 1
            if gui:
                yield (counter, nfiles)
            # q.put(filepath)

    # for t in threads:
    #    q.put(0)

    # for t in threads:
    #    t.join()

    # TODO: Is this commented update necessary?
    # grouper.Update()
    yield grouper.GetPatientsGroups()


@handle_errors(error_message="Error retrieving DICOM groups", category=ErrorCategory.DICOM)
def GetDicomGroups(directory, recursive=True):
    """
    Return all full paths to DICOM files inside given directory.
    """
    # Use iterator to avoid loading all files into memory
    logger.info(f"Getting DICOM groups from {directory}, recursive={recursive}")
    
    try:
        return IteratorDirectory(directory, recursive)
    except Exception as e:
        logger.error(f"Error getting DICOM groups: {str(e)}")
        raise

def IteratorDirectory(directory, recursive=True):
    """
    Return all files in directory.
    """
    logger.debug(f"Scanning directory for DICOM files: {directory}, recursive={recursive}")
    
    if recursive:
        for dirpath, dirnames, filenames in os.walk(directory):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                yield filepath
    else:
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                yield filepath


class ProgressDicomReader:
    def __init__(self):
        self.running = True
        logger.debug("Initializing ProgressDicomReader")

    def CancelLoad(self):
        self.running = False
        logger.info("DICOM load operation was canceled")

    def SetWindowEvent(self, frame):
        self.frame = frame

    def SetDirectoryPath(self, path, recursive=True):
        self.directory = path
        self.recursive = recursive
        logger.info(f"DICOM reader initialized with directory: {path}, recursive={recursive}")

    def UpdateLoadFileProgress(self, cont_progress):
        Publisher.sendMessage("Update dicom load", data=cont_progress)

    def EndLoadFile(self, patient_list):
        Publisher.sendMessage("End dicom load", patient_list=patient_list)

    @handle_errors(error_message="Error reading DICOM files", category=ErrorCategory.DICOM)
    def GetDicomGroups(self, path, recursive):
        patient_groups = []
        dicom_groups = GetDicomGroups(path, recursive)
        
        cont_total = len(dicom_groups)
        
        if not cont_total:
            error_msg = f"No DICOM files found in directory: {path}"
            logger.warning(error_msg)
            return
            
        grouper = dicom_grouper.DicomPatientGrouper()
        
        cont_progress = 0
        
        try:
            for file_path in dicom_groups:
                cont_progress += 1
                
                if not self.running:
                    return
                    
                self.UpdateLoadFileProgress(int(100 * cont_progress / cont_total))
                
                LoadDicom(grouper, file_path)
                
            grouper.Update()
            
            patient_groups = grouper.GetPatientsGroups()
            
            self.EndLoadFile(patient_groups)
            logger.info(f"Successfully processed {cont_total} DICOM files")
        except Exception as e:
            logger.error(f"Error in DICOM reader processing: {str(e)}")
            raise
