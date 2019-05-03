# -*- coding: utf-8 -*-
"""Code to read in data files from Bio-Logic instruments"""

__all__ = ['MPTfileCSV', 'MPTfile']

import sys
import re
import csv
from os import SEEK_SET
import time
from datetime import date, datetime, timedelta
from collections import OrderedDict

import numpy as np


if sys.version_info.major <= 2:
    str3 = str
    from string import maketrans
else:
    str3 = lambda b: str(b, encoding='ascii')
    maketrans = bytes.maketrans


def fieldname_to_dtype(fieldname):
    """Converts a column header from the MPT file into a tuple of
    canonical name and appropriate numpy dtype"""

    if fieldname == 'mode':
        return ('mode', np.uint8)
    elif fieldname in ("ox/red", "error", "control changes", "Ns changes",
                       "counter inc."):
        return (fieldname, np.bool_)
    elif fieldname in ("time/s", "P/W", "(Q-Qo)/mA.h", "x", "control/V",
                       "control/V/mA", "(Q-Qo)/C", "dQ/C", "freq/Hz",
                       "|Ewe|/V", "|I|/A", "Phase(Z)/deg", "|Z|/Ohm",
                       "Re(Z)/Ohm", "-Im(Z)/Ohm"):
        return (fieldname, np.float_)
    elif fieldname in ("cycle number", "I Range", "Ns", "half cycle"):
        return (fieldname, np.int_)
    elif fieldname in ("dq/mA.h", "dQ/mA.h"):
        return ("dQ/mA.h", np.float_)
    elif fieldname in ("I/mA", "<I>/mA"):
        return ("I/mA", np.float_)
    elif fieldname in ("Ewe/V", "<Ewe>/V"):
        return ("Ewe/V", np.float_)
    else:
        raise ValueError("Invalid column header: %s" % fieldname)


def comma_converter(float_string):
    """Convert numbers to floats whether the decimal point is '.' or ','"""
    trans_table = maketrans(b',', b'.')
    return float(float_string.translate(trans_table))


def MPTfile(file_or_path):
    """Opens .mpt files as numpy record arrays

    Checks for the correct headings, skips any comments and returns a
    numpy record array object and a list of comments
    """

    if isinstance(file_or_path, str):
        mpt_file = open(file_or_path, 'rb')
    else:
        mpt_file = file_or_path

    magic = next(mpt_file)
    if magic != b'EC-Lab ASCII FILE\r\n':
        raise ValueError("Bad first line for EC-Lab file: '%s'" % magic)

    # TODO use rb'string' here once Python 2 is no longer supported
    nb_headers_match = re.match(b'Nb header lines : (\\d+)\\s*$', next(mpt_file))
    nb_headers = int(nb_headers_match.group(1))
    if nb_headers < 3:
        raise ValueError("Too few header lines: %d" % nb_headers)

    ## The 'magic number' line, the 'Nb headers' line and the column headers
    ## make three lines. Every additional line is a comment line.
    comments = [next(mpt_file) for i in range(nb_headers - 3)]

    fieldnames = str3(next(mpt_file)).strip().split('\t')
    record_type = np.dtype(list(map(fieldname_to_dtype, fieldnames)))

    ## Must be able to parse files where commas are used for decimal points
    converter_dict = dict(((i, comma_converter)
                           for i in range(len(fieldnames))))
    mpt_array = np.loadtxt(mpt_file, dtype=record_type,
                           converters=converter_dict)

    return mpt_array, comments


def MPTfileCSV(file_or_path):
    """Simple function to open MPT files as csv.DictReader objects

    Checks for the correct headings, skips any comments and returns a
    csv.DictReader object and a list of comments
    """

    if isinstance(file_or_path, str):
        mpt_file = open(file_or_path, 'r')
    else:
        mpt_file = file_or_path

    magic = next(mpt_file)
    if magic.rstrip() != 'EC-Lab ASCII FILE':
        raise ValueError("Bad first line for EC-Lab file: '%s'" % magic)

    nb_headers_match = re.match(r'Nb header lines : (\d+)\s*$', next(mpt_file))
    nb_headers = int(nb_headers_match.group(1))
    if nb_headers < 3:
        raise ValueError("Too few header lines: %d" % nb_headers)

    ## The 'magic number' line, the 'Nb headers' line and the column headers
    ## make three lines. Every additional line is a comment line.
    comments = [next(mpt_file) for i in range(nb_headers - 3)]

    mpt_csv = csv.DictReader(mpt_file, dialect='excel-tab')

    expected_fieldnames = (
        ["mode", "ox/red", "error", "control changes", "Ns changes",
         "counter inc.", "time/s", "control/V/mA", "Ewe/V", "dq/mA.h",
         "P/W", "<I>/mA", "(Q-Qo)/mA.h", "x"],
        ['mode', 'ox/red', 'error', 'control changes', 'Ns changes',
         'counter inc.', 'time/s', 'control/V', 'Ewe/V', 'dq/mA.h',
         '<I>/mA', '(Q-Qo)/mA.h', 'x'],
        ["mode", "ox/red", "error", "control changes", "Ns changes",
         "counter inc.", "time/s", "control/V", "Ewe/V", "I/mA",
         "dQ/mA.h", "P/W"],
        ["mode", "ox/red", "error", "control changes", "Ns changes",
         "counter inc.", "time/s", "control/V", "Ewe/V", "<I>/mA",
         "dQ/mA.h", "P/W"])
    if mpt_csv.fieldnames not in expected_fieldnames:
        raise ValueError("Unrecognised headers for MPT file format")

    return mpt_csv, comments


VMPmodule_hdr = np.dtype([('shortname', 'S10'),
                          ('longname', 'S25'),
                          ('length', '<u4'),
                          ('version', '<u4'),
                          ('date', 'S8')])

# Maps from colID to a tuple defining a numpy dtype
VMPdata_colID_dtype_map = {
    4: ('time/s', '<f8'),
    5: ('control/V/mA', '<f4'),
    6: ('Ewe/V', '<f4'),
    7: ('dQ/mA.h', '<f8'),
    8: ('I/mA', '<f4'),  # 8 is either I or <I> ??
    9: ('Ece/V', '<f4'),
    11: ('I/mA', '<f8'),
    13: ('(Q-Qo)/mA.h', '<f8'),
    19: ('control/V', '<f4'),
    20: ('control/mA', '<f4'),
    23: ('dQ/mA.h', '<f8'),  # Same as 7?
    24: ('cycle number', '<f8'),
    32: ('freq/Hz', '<f4'),
    33: ('|Ewe|/V', '<f4'),
    34: ('|I|/A', '<f4'),
    35: ('Phase(Z)/deg', '<f4'),
    36: ('|Z|/Ohm', '<f4'),
    37: ('Re(Z)/Ohm', '<f4'),
    38: ('-Im(Z)/Ohm', '<f4'),
    39: ('I Range', '<u2'),
    70: ('P/W', '<f4'),
    76: ('<I>/mA', '<f4'),
    77: ('<Ewe>/V', '<f4'),
    123: ('Energy charge/W.h', '<f8'),
    124: ('Energy discharge/W.h', '<f8'),
    125: ('Capacitance charge/µF', '<f8'),
    126: ('Capacitance discharge/µF', '<f8'),
    131: ('Ns', '<u2'),
    169: ('Cs/µF', '<f4'),
    172: ('Cp/µF', '<f4'),
    434: ('(Q-Qo)/C', '<f4'),
    435: ('dQ/C', '<f4'),
    467: ('Q charge/discharge/mA.h', '<f8'),
    468: ('half cycle', '<u4'),
    473: ('THD Ewe/%', '<f4'),
    474: ('THD I/%', '<f4'),
    476: ('NSD Ewe/%', '<f4'),
    477: ('NSD I/%', '<f4'),
    479: ('NSR Ewe/%', '<f4'),
    480: ('NSR I/%', '<f4'),
}


def VMPdata_dtype_from_colIDs(colIDs):
    type_list = []
    field_list = []
    flags_dict = OrderedDict()
    flags2_dict = OrderedDict()
    for colID in colIDs:
        if colID in (1, 2, 3, 21, 31, 65):
            if 'flags' not in field_list:
                type_list.append('u1')
                field_list.append('flags')
            if colID == 1:
                flags_dict['mode'] = (np.uint8(0x03), np.uint8)
            elif colID == 2:
                flags_dict['ox/red'] = (np.uint8(0x04), np.bool_)
            elif colID == 3:
                flags_dict['error'] = (np.uint8(0x08), np.bool_)
            elif colID == 21:
                flags_dict['control changes'] = (np.uint8(0x10), np.bool_)
            elif colID == 31:
                flags_dict['Ns changes'] = (np.uint8(0x20), np.bool_)
            elif colID == 65:
                flags_dict['counter inc.'] = (np.uint8(0x80), np.bool_)
            else:
                raise NotImplementedError("flag %d not implemented" % colID)
        else:
            try:
                field = VMPdata_colID_dtype_map[colID][0]
                if field in field_list:
                    field += str(len(field_list))
                field_list.append(field)
                type_list.append(VMPdata_colID_dtype_map[colID][1])
            except KeyError:
                print(list(zip(field_list, type_list)))
                raise NotImplementedError("column type %d not implemented"
                                          % colID)
    return np.dtype(list(zip(field_list, type_list))), flags_dict, flags2_dict


def read_VMP_modules(fileobj, read_module_data=True):
    """Reads in module headers in the VMPmodule_hdr format. Yields a dict with
    the headers and offset for each module.

    N.B. the offset yielded is the offset to the start of the data i.e. after
    the end of the header. The data runs from (offset) to (offset+length)"""
    while True:
        module_magic = fileobj.read(len(b'MODULE'))
        if len(module_magic) == 0:  # end of file
            break
        elif module_magic != b'MODULE':
            raise ValueError("Found %r, expecting start of new VMP MODULE" % module_magic)

        hdr_bytes = fileobj.read(VMPmodule_hdr.itemsize)
        if len(hdr_bytes) < VMPmodule_hdr.itemsize:
            raise IOError("Unexpected end of file while reading module header")

        hdr = np.frombuffer(hdr_bytes, dtype=VMPmodule_hdr, count=1)
        hdr_dict = dict(((n, hdr[n][0]) for n in VMPmodule_hdr.names))
        hdr_dict['offset'] = fileobj.tell()
        if read_module_data:
            hdr_dict['data'] = fileobj.read(hdr_dict['length'])
            if len(hdr_dict['data']) != hdr_dict['length']:
                raise IOError("""Unexpected end of file while reading data
                    current module: %s
                    length read: %d
                    length expected: %d""" % (hdr_dict['longname'],
                                              len(hdr_dict['data']),
                                              hdr_dict['length']))
            yield hdr_dict
        else:
            yield hdr_dict
            fileobj.seek(hdr_dict['offset'] + hdr_dict['length'], SEEK_SET)


class MPRfile:
    """Bio-Logic .mpr file

    The file format is not specified anywhere and has therefore been reverse
    engineered. Not all the fields are known.

    Attributes
    ==========
    modules - A list of dicts containing basic information about the 'modules'
              of which the file is composed.
    data - numpy record array of type VMPdata_dtype containing the main data
           array of the file.
    startdate - The date when the experiment started
    enddate - The date when the experiment finished
    """

    def __init__(self, file_or_path):
        self.loop_index = None
        if isinstance(file_or_path, str):
            mpr_file = open(file_or_path, 'rb')
        else:
            mpr_file = file_or_path

        mpr_magic = b'BIO-LOGIC MODULAR FILE\x1a                         \x00\x00\x00\x00'
        magic = mpr_file.read(len(mpr_magic))
        if magic != mpr_magic:
            raise ValueError('Invalid magic for .mpr file: %s' % magic)

        modules = list(read_VMP_modules(mpr_file))
        self.modules = modules
        settings_mod, = (m for m in modules if m['shortname'] == b'VMP Set   ')
        data_module, = (m for m in modules if m['shortname'] == b'VMP data  ')
        maybe_loop_module = [m for m in modules if m['shortname'] == b'VMP loop  ']
        maybe_log_module = [m for m in modules if m['shortname'] == b'VMP LOG   ']

        n_data_points = np.frombuffer(data_module['data'][:4], dtype='<u4')
        n_columns = np.frombuffer(data_module['data'][4:5], dtype='u1').item()

        if data_module['version'] == 0:
            column_types = np.frombuffer(data_module['data'][5:], dtype='u1',
                                         count=n_columns)
            remaining_headers = data_module['data'][5 + n_columns:100]
            main_data = data_module['data'][100:]
        elif data_module['version'] == 2:
            column_types = np.frombuffer(data_module['data'][5:], dtype='<u2',
                                         count=n_columns)
            ## There is 405 bytes of data before the main array starts
            remaining_headers = data_module['data'][5 + 2 * n_columns:405]
            main_data = data_module['data'][405:]
        else:
            raise ValueError("Unrecognised version for data module: %d" %
                             data_module['version'])

        if sys.version_info.major <= 2:
            assert(all((b == '\x00' for b in remaining_headers)))
        else:
            assert(not any(remaining_headers))

        self.dtype, self.flags_dict, self.flags2_dict = VMPdata_dtype_from_colIDs(column_types)
        self.data = np.frombuffer(main_data, dtype=self.dtype)
        assert(self.data.shape[0] == n_data_points)

        ## No idea what these 'column types' mean or even if they are actually
        ## column types at all
        self.version = int(data_module['version'])
        self.cols = column_types
        self.npts = n_data_points

        try:
            tm = time.strptime(str3(settings_mod['date']), '%m/%d/%y')
        except ValueError:
            tm = time.strptime(str3(settings_mod['date']), '%m-%d-%y')
        self.startdate = date(tm.tm_year, tm.tm_mon, tm.tm_mday)

        if maybe_loop_module:
            loop_module, = maybe_loop_module
            if loop_module['version'] == 0:
                self.loop_index = np.fromstring(loop_module['data'][4:],
                                                dtype='<u4')
                self.loop_index = np.trim_zeros(self.loop_index, 'b')
            else:
                raise ValueError("Unrecognised version for data module: %d" %
                                 data_module['version'])

        if maybe_log_module:
            log_module, = maybe_log_module
            try:
                tm = time.strptime(str3(log_module['date']), '%m/%d/%y')
            except ValueError:
                tm = time.strptime(str3(log_module['date']), '%m-%d-%y')
            self.enddate = date(tm.tm_year, tm.tm_mon, tm.tm_mday)

            ## There is a timestamp at either 465 or 469 bytes
            ## I can't find any reason why it is one or the other in any
            ## given file
            ole_timestamp1 = np.frombuffer(log_module['data'][465:],
                                           dtype='<f8', count=1)
            ole_timestamp2 = np.frombuffer(log_module['data'][469:],
                                           dtype='<f8', count=1)
            ole_timestamp3 = np.frombuffer(log_module['data'][473:],
                                           dtype='<f8', count=1)
            ole_timestamp4 = np.frombuffer(log_module['data'][585:],
                                           dtype='<f8', count=1)

            if ole_timestamp1 > 40000 and ole_timestamp1 < 50000:
                ole_timestamp = ole_timestamp1
            elif ole_timestamp2 > 40000 and ole_timestamp2 < 50000:
                ole_timestamp = ole_timestamp2
            elif ole_timestamp3 > 40000 and ole_timestamp3 < 50000:
                ole_timestamp = ole_timestamp3
            elif ole_timestamp4 > 40000 and ole_timestamp4 < 50000:
                ole_timestamp = ole_timestamp4
    
            else:
                raise ValueError("Could not find timestamp in the LOG module")

            ole_base = datetime(1899, 12, 30, tzinfo=None)
            ole_timedelta = timedelta(days=ole_timestamp[0])
            self.timestamp = ole_base + ole_timedelta
            if self.startdate != self.timestamp.date():
                raise ValueError("""Date mismatch:
                Start date: %s
                End date: %s
                Timestamp: %s""" % (self.startdate, self.enddate, self.timestamp))

    def get_flag(self, flagname):
        if flagname in self.flags_dict:
            mask, dtype = self.flags_dict[flagname]
            return np.array(self.data['flags'] & mask, dtype=dtype)
        elif flagname in self.flags2_dict:
            mask, dtype = self.flags2_dict[flagname]
            return np.array(self.data['flags2'] & mask, dtype=dtype)
        else:
            raise AttributeError("Flag '%s' not present" % flagname)
