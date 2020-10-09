import logging

import numpy as np


class HDF5Dataset(object):
    """A wrapper of h5py.Dataset with a cache to reduce I/O"""

    def __init__(self, name, dtype, fillvalue, shape=None, cache=True):
        """
        Args:
            name(str): Name to pass to h5py.Dataset (and for log messages)
            dtype(str) Datatype to pass to h5py.Dataset
            fillvalue(value matching dtype): Fill value for h5py.Dataset
            shape(tuple(int)): Shape to pass to h5py.Dataset
            cache(bool): Whether to store a local cache of values
                         or write directly to file

        """
        self.name = name
        self.dtype = dtype
        self.fillvalue = fillvalue
        self.shape = shape if shape is not None else (0,)
        self.maxshape = shape if shape is not None else (None,)

        if cache:
            self._cache = np.full(shape, self.fillvalue, dtype=self.dtype)
        else:
            self._cache = None

        self._h5py_dataset = None  # h5py.Dataset

        self._logger = logging.getLogger("HDF5Dataset")

    def initialise(self, dataset_handle, dataset_size=None):
        """Initialise _h5py_dataset handle and cache

        Args:
            dataset_handle(h5py.Dataset): Actual h5py Dataset object
            dataset_size(int): Length of datasets

        """
        self._h5py_dataset = dataset_handle

        # Turn off the cache if the dataset_size is set to 0 (unlimited)
        if dataset_size == 0:
            self._cache = None

        if self._cache is not None and dataset_size is not None:
            self._cache = np.full(dataset_size, self.fillvalue, dtype=self.dtype)
            self._h5py_dataset.resize(dataset_size, axis=0)

    def add_value(self, value, offset=None):
        """Add a value at the given offset

        If we are caching parameters, add the value to the cache, otherwise
        extend the dataset and write it directly.

        Args:
            value(object matching dtype): Value to add to dataset
            offset(int): Offset to insert value at in dataset

        """
        if self._cache is None:
            self._h5py_dataset.resize(self._h5py_dataset.shape[0] + 1, axis=0)
            self._h5py_dataset[-1] = value
            return

        if offset is not None and offset >= self._cache.size:
            self._logger.error(
                "%s | Cannot add value at offset %d, cache length = %d",
                self.name,
                offset,
                len(self._cache),
            )
        else:
            self._cache[offset] = value

    def flush(self):
        """Write cached values to file (if cache enabled) and call flush"""
        if self._cache is not None:
            self._logger.debug(
                "%s | Writing cache to dataset: %s",
                self.name,
                np.array2string(self._cache, threshold=10),
            )
            self._h5py_dataset[...] = self._cache

        self._h5py_dataset.flush()


class Int32HDF5Dataset(HDF5Dataset):
    """Int32 HDF5Dataset"""

    def __init__(self, name, shape=None, cache=True):
        super(Int32HDF5Dataset, self).__init__(
            name, dtype="int32", fillvalue=-1, shape=shape, cache=cache
        )


class Int64HDF5Dataset(HDF5Dataset):
    """Int64 HDF5Dataset"""

    def __init__(self, name, shape=None, cache=True):
        super(Int64HDF5Dataset, self).__init__(
            name, dtype="int64", fillvalue=-1, shape=shape, cache=cache
        )


class StringHDF5Dataset(HDF5Dataset):
    """String HDF5Dataset"""

    def __init__(self, name, shape=None, length=None, cache=True):
        """
        Args:
            length(int): Maximum length of the string elements

        """
        # If a specific string length is given, specify it, else use str
        dtype = "str" if length is None else "S{}".format(length)

        super(StringHDF5Dataset, self).__init__(
            name, dtype=dtype, fillvalue="", shape=shape, cache=cache
        )
