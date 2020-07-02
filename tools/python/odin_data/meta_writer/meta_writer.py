"""Implementation of odin_data Meta Writer

This module is passed meta data messages for a single acquisition which it writes to disk.
Will need to be subclassed by detector specific implementation.

Matt Taylor, Diamond Light Source
"""
import os
from time import time
import re
import logging

import numpy as np
import h5py

from .. import _version as versioneer
from .hdf5dataset import HDF5Dataset, Int64HDF5Dataset, StringHDF5Dataset

MAJOR_VER_REGEX = r"^([0-9]+)[\\.-].*|$"
MINOR_VER_REGEX = r"^[0-9]+[\\.-]([0-9]+).*|$"
PATCH_VER_REGEX = r"^[0-9]+[\\.-][0-9]+[\\.-]([0-9]+).|$"

# Data message parameters
FRAME = "frame"
OFFSET = "offset"
CREATE_DURATION = "create_duration"
WRITE_DURATION = "write_duration"
FLUSH_DURATION = "flush_duration"
CLOSE_DURATION = "close_duration"
MESSAGE_TYPE_ID = "parameter"

# Configuration items
DIRECTORY = "directory"
FILE_PREFIX = "file_prefix"
FLUSH_FRAME_FREQUENCY = "flush_frame_frequency"
FLUSH_TIMEOUT = "flush_timeout"


class MetaWriter(object):
    """This class handles meta data messages and writes parameters to disk"""

    FILE_SUFFIX = "_meta.h5"
    CONFIGURE_PARAMETERS = [
        DIRECTORY,
        FILE_PREFIX,
        FLUSH_FRAME_FREQUENCY,
        FLUSH_TIMEOUT,
    ]
    DATASETS = [
        Int64HDF5Dataset(FRAME),
        Int64HDF5Dataset(OFFSET),
        Int64HDF5Dataset(CREATE_DURATION, cache=False),
        Int64HDF5Dataset(WRITE_DURATION),
        Int64HDF5Dataset(FLUSH_DURATION),
        Int64HDF5Dataset(CLOSE_DURATION, cache=False),
    ]
    # Detector-specific meta datasets
    DETECTOR_DATASETS = []
    # Detector-specific parameters received on per-frame meta message
    DETECTOR_WRITE_FRAME_PARAMETERS = []

    def __init__(self, name, directory):
        """
        Args:
            name(str): Unique name to construct file path and to include in
                       log messages
            directory(str): Directory to create the meta file in

        """
        self._logger = logging.getLogger(self.__class__.__name__)

        # Config
        self.directory = directory
        self.file_prefix = None
        self.flush_frame_frequency = 100
        self.flush_timeout = 1

        # Status
        self.full_file_path = None
        self.file_created = False
        self.number_processes_running = 0
        self.write_count = 0
        self.finished = False
        self.write_timeout_count = 0

        # Internal parameters
        self._name = name
        self._num_frames_to_write = -1
        self._last_flushed = time()  # Seconds since epoch
        self._hdf5_file = None
        self._datasets = dict(
            (dataset.name, dataset)
            for dataset in self.DATASETS + self.DETECTOR_DATASETS
        )
        # Child class parameters
        self._frame_data_map = dict()  # Map of frame number to detector data

    def _generate_full_file_path(self):
        prefix = self.file_prefix if self.file_prefix is not None else self._name
        self.full_file_path = os.path.join(
            self.directory, "{}{}".format(prefix, self.FILE_SUFFIX)
        )
        return self.full_file_path

    def _create_file(self, file_path, dataset_size):
        self._logger.debug(
            "%s | Opening file %s - Expecting %d frames",
            self._name,
            file_path,
            dataset_size,
        )
        self._hdf5_file = h5py.File(file_path, "w", libver="latest")
        self._create_datasets(dataset_size)
        self._hdf5_file.swmr_mode = True

    def hdf5_file_open(self):
        """Verify HDF5 file is open - Log the reason why if not"""
        if self._hdf5_file is None:
            if self.finished:
                reason = "Already finished writing"
            else:
                reason = "Have not received startacquisition yet"

            self._logger.info("%s | File not open - %s", self._name, reason)
            return False

        return True

    def _close_file(self):
        self._logger.info("%s | Closing file", self._name)
        if not self.hdf5_file_open():
            return

        self._write_datasets()
        self._hdf5_file.close()
        self._hdf5_file = None

    def _create_datasets(self, dataset_size):
        """Add predefined datasets to HDF5 file and store handles

        Args:
            datasets(list(HDF5Dataset)): The datasets to add to the file

        """
        self._logger.debug("%s | Creating datasets", self._name)
        if not self.hdf5_file_open():
            return

        for dataset in self._datasets.values():
            dataset_handle = self._hdf5_file.create_dataset(
                name=dataset.name,
                shape=dataset.shape,
                maxshape=dataset.maxshape,
                dtype=dataset.dtype,
                fillvalue=dataset.fillvalue,
            )
            dataset.initialise(dataset_handle, dataset_size)

    def _add_dataset(self, dataset_name, data, dataset_size=None):
        """Add a new dataset with the given data

        Args:
            dataset_name(str): Name of dataset
            data(np.ndarray): Data to initialise HDF5 dataset with
            dataset_size(int): Dataset size - required if more data will be added

        """
        self._logger.debug("%s | Adding dataset %s", self._name, dataset_name)
        if not self.hdf5_file_open():
            return

        if dataset_name in self._datasets:
            self._logger.debug(
                "%s | Dataset %s already created", self._name, dataset_name
            )
            return

        self._logger.debug(
            "%s | Creating dataset %s with data", self._name, dataset_name
        )
        self._logger.debug(data)
        dataset = HDF5Dataset(dataset_name, dtype=None, fillvalue=None, cache=False)
        dataset_handle = self._hdf5_file.create_dataset(name=dataset_name, data=data)
        dataset.initialise(dataset_handle, dataset_size)

        self._datasets[dataset_name] = dataset

    def _add_value(self, dataset_name, value, offset=0):
        """Append a value to the named dataset

        Args:
            dataset_name(str): Name of dataset
            value(): The value to append
            index(int): The offset to add the value to

        """
        self._logger.debug("%s | Adding value to %s", self._name, dataset_name)
        if not self.hdf5_file_open():
            return

        if dataset_name not in self._datasets:
            self._logger.error("%s | No such dataset %s")
            return

        self._datasets[dataset_name].add_value(value, offset)

    def _add_values(self, expected_parameters, data, offset):
        """Take values of parameters from data and write to datasets at offset

        Args:
            expected_parameters(list(str)): Parameters to write
            data(dict): Set of parameter values
            offset(int): Offset to write parameters to in datasets

        """
        self._logger.debug("%s | Adding values to datasets", self._name)
        if not self.hdf5_file_open():
            return

        for parameter in expected_parameters:
            if parameter not in data:
                self._logger.error(
                    "%s | Expected parameter %s not found in %s",
                    self._name,
                    parameter,
                    data,
                )
                continue

            self._add_value(parameter, data[parameter], offset)

    def _write_datasets(self):
        self._logger.debug("%s | Writing datasets", self._name)
        if not self.hdf5_file_open():
            return

        for dataset in self._datasets.values():
            dataset.flush()

    def stop(self):
        self._close_file()
        self.finished = True
        self._logger.info("%s | Finished", self._name)

    def configure(self, configuration):
        """Configure the writer with a set of one or more parameters

        Args:
            writer_name(str): Name of writer to configure
            configuration(dict): Paramters to configure with

        Returns:
            error(None/str): None if successful else an error message

        """
        error = None
        for parameter, value in configuration.items():
            if parameter in self.CONFIGURE_PARAMETERS:
                self._logger.debug(
                    "%s | Setting %s to %s", self._name, parameter, value
                )
                setattr(self, parameter, value)
            else:
                error = "Invalid parameter {}".format(parameter)
                self._logger.error("%s | %s", self._name, error)

        return error

    def request_configuration(self):
        """Return the current configuration

        Returns:
            configuration(dict): Dictionary of current configuration parameters

        """
        configuration = dict(
            (parameter, getattr(self, parameter))
            for parameter in self.CONFIGURE_PARAMETERS
        )

        return configuration

    # Methods for handling various message types

    def process_message(self, header, data):
        """Process a message from a data socket

        This is main entry point for handling any type of message and calling
        the appropriate method.

        Look up the appropriate message handler based on the message type and
        call it.

        Leading underscores on a handler function definition parameter mean it
        does not use the argument.

        This should be overridden by child classes to handle any additional messages.

        Args:
            header(str): The header message part
            data(str): The data message part (a json string or a data blob)

        """
        message_handlers = {
            "startacquisition": self.handle_start_acquisition,
            "createfile": self.handle_create_file,
            "writeframe": self.handle_write_frame,
            "closefile": self.handle_close_file,
            "stopacquisition": self.handle_stop_acquisition,
        }

        handler = message_handlers.get(header[MESSAGE_TYPE_ID], None)
        if handler is not None:
            handler(header["header"], data)
        else:
            self._logger.error(
                "%s | Unknown message type: %s", self._name, header[MESSAGE_TYPE_ID]
            )

    def handle_start_acquisition(self, header, _data):
        """Prepare the data file with the number of frames to write"""
        self._logger.debug("%s | Handling start acquisition message", self._name)

        self.number_processes_running = self.number_processes_running + 1

        if self._num_frames_to_write == -1:
            self._num_frames_to_write = header["totalFrames"]
            self._create_file(
                self._generate_full_file_path(), self._num_frames_to_write
            )
            self.file_created = True

    def handle_create_file(self, _header, data):
        self._logger.debug("%s | Handling create file message", self._name)

        self._add_value(CREATE_DURATION, data[CREATE_DURATION])

    def handle_write_frame(self, _header, data):
        self._logger.debug("%s | Handling write frame message", self._name)

        # TODO: Handle getting more frames than expected because of rewinding?
        write_frame_parameters = [FRAME, OFFSET, WRITE_DURATION, FLUSH_DURATION]
        self._add_values(write_frame_parameters, data, data[OFFSET])

        # Here we keep track of whether we need to write to disk based on:
        #   - Time since last write
        #   - Number of write frame messages since last write

        # Reset timeout count to 0
        self.write_timeout_count = 0

        self.write_count += 1

        # Write detector meta data for this frame, now that we know the offset
        self.write_detector_frame_data(data[FRAME], data[OFFSET])

        write_data = False
        if self.flush_timeout is not None:
            if (time() - self._last_flushed) >= self.flush_timeout:
                write_data = True
        # TODO: This isn't technically doing the right thing:
        if self.write_count % self.flush_frame_frequency == 0:
            write_data = True

        if write_data:
            self._write_datasets()
            self._last_flushed = time()

    def write_detector_frame_data(self, frame, offset):
        """Write the frame data to at the given offset

        Args:
            frame(int): Frame to write
            offset(int): Offset in datasets to write the frame data to

        """
        if not self.DETECTOR_WRITE_FRAME_PARAMETERS:
            # No detector specific data to write
            return

        self._logger.debug("%s | Writing detector data for frame %d", self._name, frame)

        if frame not in self._frame_data_map:
            self._logger.error(
                "%s | No detector meta data stored for frame %d", self._name, frame
            )
            return

        data = self._frame_data_map[frame]
        self._add_values(self.DETECTOR_WRITE_FRAME_PARAMETERS, data, offset)

    def handle_close_file(self, _header, data):
        self._logger.debug("%s | Handling close file message", self._name)

        self._add_value(CLOSE_DURATION, data[CLOSE_DURATION])

    def handle_stop_acquisition(self, header, _data):
        """Register that a process has finished and stop if it is the last one"""
        self._logger.debug("%s | Handling stop acquisition message", self._name)

        if self.number_processes_running > 0:
            self.number_processes_running = self.number_processes_running - 1

        self._logger.debug("%s | Process rank %d stopped", self._name, header["rank"])

        if self.number_processes_running == 0:
            self._logger.info("%s | Last processor stopped", self._name)
            self.stop()

    # TODO: Do this properly
    @staticmethod
    def get_version():
        full_version = versioneer.get_versions()["version"]
        major_version = re.findall(MAJOR_VER_REGEX, full_version)[0]
        minor_version = re.findall(MINOR_VER_REGEX, full_version)[0]
        patch_version = re.findall(PATCH_VER_REGEX, full_version)[0]
        short_version = major_version + "." + minor_version + "." + patch_version

        version_dict = {}
        version_dict["full"] = full_version
        version_dict["major"] = major_version
        version_dict["minor"] = minor_version
        version_dict["patch"] = patch_version
        version_dict["short"] = short_version

        return version_dict
