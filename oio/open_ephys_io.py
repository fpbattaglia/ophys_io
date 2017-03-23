import re
import sys
import os.path as op
import numpy as np
import neuroseries as nts

SIZE_HEADER = 1024  # size of header in B
NUM_SAMPLES = 1024  # number of samples per record
SIZE_RECORD = 2070  # total size of record (2x1024 B samples + record header)
REC_MARKER = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 255], dtype=np.uint8)
NAME_TEMPLATE = '{proc_node:d}_CH{channel:d}.continuous'

# HEADER_REGEX = re.compile("header\.([\d\w.\s]+).=.'*([^;']+)'*")
HEADER_REGEX = re.compile("header\.([\d\w.\s]+).=.\'*([^;\']+)\'*")


def gather_files(input_directory, channels, proc_node, template=NAME_TEMPLATE):
    """Return list of paths to valid input files for the input directory."""
    file_names = [op.join(input_directory, template.format(proc_node=proc_node, channel=chan))
                  for chan in channels]
    is_file = {f: op.isfile(f) for f in file_names}
    try:
        assert all(is_file.values())
    except AssertionError:
        print(IOError("Input files not found: {}".format([f for f, exists in is_file.items() if not exists])))
        sys.exit(1)
    return file_names


# data type of .continuous open ephys 0.2x file format header
def header_dt(size_header=SIZE_HEADER):
    return np.dtype([('Header', 'S%d' % size_header)])


# data type of individual records, n Bytes
# (2048 + 22) Byte = 2070 Byte total typically if full 1024 samples
def data_dt(num_samples=NUM_SAMPLES):
    return np.dtype([('timestamp', np.int64),  # 8 Byte
                     ('n_samples', np.uint16),  # 2 Byte
                     ('rec_num', np.uint16),  # 2 Byte
                     ('samples', ('>i2', num_samples)),  # 2 Byte each x 1024 typ.
                     ('rec_mark', (np.uint8, len(REC_MARKER)))])  # 10 Byte


def check_headers(oe_file):
    """Check that length, sampling rate, buffer and block sizes of a list of open-ephys ContinuousFiles are
    identical and return them in that order."""
    # Check oe_file make sense (same size, same sampling rate, etc.
    num_records = [f.num_records for f in oe_file]
    sampling_rates = [f.header['sampleRate'] for f in oe_file]
    buffer_sizes = [f.header['bufferSize'] for f in oe_file]
    block_sizes = [f.header['blockLength'] for f in oe_file]

    assert len(set(num_records)) == 1
    assert len(set(sampling_rates)) == 1
    assert len(set(buffer_sizes)) == 1
    assert len(set(block_sizes)) == 1

    return num_records[0], sampling_rates[0], buffer_sizes[0], block_sizes[0]


def fmt_header(header_str):
    # Stand back! I know regex!
    # Annoyingly, there is a newline character missing in the header_str (version/header_bytes)
    header_str = str(header_str[0][0]).rstrip(' ')
    header_dict = {group[0]: group[1] for group in HEADER_REGEX.findall(header_str)}
    for key in ['bitVolts', 'sampleRate']:
        header_dict[key] = float(header_dict[key])
    for key in ['blockLength', 'bufferSize', 'header_bytes', 'channel']:
        header_dict[key] = int(header_dict[key] if not key == 'channel' else header_dict[key][2:])
    return header_dict


class ContinuousFile:
    """Single .continuous file. Generates chunks of data."""

    def __init__(self, path, t_min=None, t_max=None, records_per_iter=1):
        self.path = op.abspath(op.expanduser(path))
        self.file_size = op.getsize(self.path)
        # Make sure we have full records all the way through
        assert (self.file_size - SIZE_HEADER) % SIZE_RECORD == 0
        self.num_records = (self.file_size - SIZE_HEADER) // SIZE_RECORD
        self.duration = self.num_records
        self._block_timestamps = None
        self.__fid = open(self.path, 'rb')
        self.header = self._read_header()
        self.record_dtype = data_dt(self.header['blockLength'])
        self.t_min = t_min
        self.t_max = t_max
        self.cur_block, n_blocks = self._records_for_interval(self.t_min, self.t_max)
        self.last_block = self.cur_block + n_blocks
        self.records_per_iter = records_per_iter
        self.convert_to_volts = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.cur_block > self.last_block:
            raise StopIteration
        else:
            return self.read_record(count=self.records_per_iter, convert_to_volts=self.convert_to_volts)

    def __enter__(self):
        self.__fid.seek(SIZE_HEADER)
        return self

    def _read_header(self):
        return fmt_header(np.fromfile(self.path, dtype=header_dt(), count=1))

    def read_record(self, count=1, convert_to_volts=False):
        buf = np.fromfile(self.__fid, dtype=self.record_dtype, count=count)

        # make sure offsets are likely correct
        assert np.array_equal(buf[0]['rec_mark'], REC_MARKER)
        if convert_to_volts:
            data = buf['samples'].reshape(-1) * self.header['bitVolts']
        else:
            data = buf['samples'].reshape(-1)
        return data

    @property
    def n_records(self):
        return int((op.getsize(self.path) - SIZE_HEADER) / SIZE_RECORD)

    def next(self):
        return self.read_record() if self.__fid.tell() < self.file_size else None

    def __exit__(self, *args):
        self.__fid.close()

    @property
    def block_timestamps(self):
        if self._block_timestamps is None:
            conv_usec = 1.e6 / self.header['sampleRate']
            timestamps = np.array([])
            blocks_per_iter = 1000
            with open(self.path) as f:
                f.seek(SIZE_HEADER)
                for b in range(0, self.n_records, blocks_per_iter):
                    buf = np.fromfile(f, dtype=self.record_dtype, count=blocks_per_iter)
                    timestamps = np.hstack([timestamps, (buf['timestamp'] * conv_usec)])
            self._block_timestamps = timestamps

        return self._block_timestamps

    def _records_for_interval(self, t_min, t_max):
        """
        get the blocks that cover the interval asked
        Args:
            t_min: minimum (if None, it will be 0) and
            t_max: maximum time (if None, it will be the last record) in the requested interval

        Returns:
            first_block
            n_blocks
        """
        if t_min is None or t_min <= self.block_timestamps[0]:
            first_block = 0
        else:
            first_block = np.where(self.block_timestamps < t_min)[0][-1]

        if t_max is None or t_max >= self.block_timestamps[-1]:
            n_blocks = self.n_records - first_block
        else:
            last_block = np.where(self.block_timestamps > t_max)[0][0]
            n_blocks = last_block - first_block

        return first_block, n_blocks

    def _skip_to_block(self, block):
        if self.__fid is None:
            self.__fid = open(self.path, 'rb')
        self.__fid.seek(SIZE_HEADER + block * SIZE_RECORD)

    def read_interval(self, t_min=None, t_max=None):
        """
        returns data and timestamps. Records will be selected based on
        Args:
            t_min: the minimum time (if None it will be the first time in file)
            t_max: the maximum time (if None it will be the last time in file)

        Returns:
            data in a numpy array (in mV)
            timestamps: timestamps for each time point in microseconds
        """
        first_block, n_blocks = self._records_for_interval(t_min, t_max)

        self._skip_to_block(first_block)
        data = self.read_record(count=n_blocks, convert_to_volts=True)
        conv_usec = 1.e6 / self.header['sampleRate']
        tstamps = np.array([])
        for r in range(first_block, first_block+n_blocks):
            t = self.block_timestamps[r] + conv_usec * np.arange(NUM_SAMPLES)
            tstamps = np.hstack((tstamps, t))
        assert len(data) == len(tstamps)
        return data, tstamps


def is_sequence(obj):
    import collections
    if isinstance(obj, str):
        return False
    return isinstance(obj, collections.Sequence)


def load_continuous_tsd(paths, t_min=None, t_max=None, col_template=r'.*_(\w+\d+)\..*'):
    if isinstance(paths, str):
        paths = (paths,)
    elif not is_sequence(paths):
        raise TypeError("paths must be a string or list of strings.")

    f = ContinuousFile(paths[0])
    data, tstamps = f.read_interval(t_min, t_max)
    data = data.reshape((-1, 1))
    columns = [re.match(col_template, paths[0])]
    for fn in paths[1:]:
        f = ContinuousFile(fn)
        d, ts1 = f.read_interval(t_min, t_max)
        assert len(ts1) == len(tstamps)
        data = np.hstack((data, d.reshape((-1, 1))))
        columns.append(re.match(col_template, fn))
    cont_tsd = nts.TsdFrame(tstamps, data, columns=columns)
    print(data[0:10])

    return cont_tsd
