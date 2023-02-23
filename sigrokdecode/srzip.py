import array
import zipfile
import configparser
import struct
import pathlib
import io

from .output import Output
from .input import Input

from . import cond_matches, __version__, OUTPUT_PYTHON

TYPECODE = {
    1: "B",
    2: "H",
    4: "L",
    5: "Q"
}

UNITS = {
    "Hz":  1,
    "kHz": 1000,
    "KHz": 1000,
    "MHz": 1000000,
    "mHz": 1000000,
    "GHz": 1000000000,
    "gHz": 1000000000,
}

class SrZipInput(Input):
    name = "srzip"
    desc = "srzip session file format data"
    def __init__(self, filename, initial_state=None):
        super().__init__()
        self.zip = zipfile.ZipFile(filename)
        # self.zip.printdir()
        metadata = configparser.ConfigParser()
        self.version = int(self.zip.read("version").decode("ascii"))
        metadata.read_string(self.zip.read("metadata").decode("ascii"))
        self.start_samplenum = None
        self.samplenum = -1
        self.matched = None
        self.single_file = "logic-1" in self.zip.namelist()
        # for s in metadata.sections():
        #     print(s)
        #     for o in metadata.options(s):
        #         print(" ", o, metadata.get(s, o))

        samplerate = metadata.get("device 1", "samplerate", fallback="0")
        self.samplerate = None
        if " " in samplerate:
            num, units = samplerate.split(" ")
            self.samplerate = float(num) * UNITS[units]
        else:
            # check for a suffix with Hz last
            for suffix in reversed(UNITS):
                if suffix in samplerate:
                    self.samplerate = int(samplerate[:-len(suffix)]) * UNITS[suffix]
                    break
            if self.samplerate is None:
                self.samplerate = int(samplerate)

        if initial_state:
            self.last_sample = 0
            for channel in initial_state:
                self.last_sample |= initial_state[channel] << channel
        else:
            self.last_sample = None
        self.unitsize = int(metadata.get("device 1", "unitsize"))
        self.typecode = TYPECODE[self.unitsize]

        self.bit_mapping = []
        self.one_to_one = True


        total_logic = int(metadata.get("device 1", "total probes", fallback="0"))
        total_analog = int(metadata.get("device 1", "total analog", fallback="0"))
        self.logic_channels = []
        self.analog_channels = []
        for in_bit in range(total_logic):
            probe_name = f"probe{in_bit + 1}"
            if not metadata.has_option("device 1", probe_name):
                continue
            name = metadata.get("device 1", probe_name)
            out_bit = len(self.logic_channels)
            self.bit_mapping.append((in_bit, out_bit))
            self.one_to_one = self.one_to_one and in_bit == out_bit
            self.logic_channels.append(name)
        for i in range(total_analog):
            name = metadata.get("device 1", f"analog{total_logic + i + 1}")
            self.analog_channels.append(name)

        if self.single_file:
            self.data = self.zip.read("logic-1")
            if self.unitsize > 1:
                self.data = array.array(self.typecode, self.data)
        else:
            self.data = None
            self._file_start = -1
            self._file_index = 1

        if self.analog_channels:
            self._analog_file_index = 1
            self._analog_data = []
            for c in range(total_logic + 1, total_logic + 1 + total_analog):
                self._analog_data.append(self.zip.read(f"analog-1-{c}-{self._analog_file_index}"))
            self._analog_offset = 0
            self._analog_chunk_len = len(self._analog_data[0]) // 4

    def wait(self, conds=[]):
        if conds is None:
            conds = []
        self.matched = [False]
        while not any(self.matched):
            self.matched = [True] * (len(conds) if conds else 1)
            self.samplenum += 1
            if self.single_file:
                if self.samplenum >= len(self.data):
                    self.put(self.start_samplenum, self.samplenum, OUTPUT_PYTHON, ["logic", self.last_sample])
                    raise EOFError()
                sample = self.data[self.samplenum]
            else:
                file_samplenum = self.samplenum - self._file_start
                if self.data is None or file_samplenum >= len(self.data):
                    self._file_start = self.samplenum
                    try:
                        self.data = self.zip.read(f"logic-1-{self._file_index:d}")
                    except KeyError:
                        self.put(self.start_samplenum, self.samplenum, OUTPUT_PYTHON, ["logic", self.last_sample])
                        raise EOFError()

                    if self.unitsize > 1:
                        self.data = array.array(self.typecode, self.data)

                    file_samplenum = 0
                    self._file_index += 1
                sample = self.data[file_samplenum]

            if not self.one_to_one:
                mapped_sample = 0
                for in_bit, out_bit in self.bit_mapping:
                    if sample & (1 << in_bit) != 0:
                        mapped_sample |= (1 << out_bit)
                sample = mapped_sample

            if self.last_sample is None:
                self.last_sample = sample
                self.start_samplenum = self.samplenum

            if self.last_sample != sample:
                self.put(self.start_samplenum, self.samplenum, OUTPUT_PYTHON, ["logic", self.last_sample])
                self.start_samplenum = self.samplenum

            if self.analog_channels:
                self.put(self.samplenum, self.samplenum + 1, OUTPUT_PYTHON, ["analog"] + self.get_analog_values(self.samplenum))

            for i, cond in enumerate(conds):
                if "skip" in cond:
                    cond["skip"] -= 1
                    self.matched[i] = cond["skip"] == 0
                    continue
                self.matched[i] = cond_matches(cond, self.last_sample, sample)
            self.last_sample = sample

        bits = []
        for b in range(self.unitsize * 8):
            bits.append((sample >> b) & 0x1)

        return tuple(bits)

    def get_analog_values(self, samplenum):
        if samplenum >= (self._analog_offset + self._analog_chunk_len):
            self._analog_offset += self._analog_chunk_len
            self._analog_file_index += 1
            self._analog_data = []
            total_logic = len(self.logic_channels)
            total_analog = len(self.analog_channels)
            for c in range(total_logic + 1, total_logic + 1 + total_analog):
                self._analog_data.append(self.zip.read(f"analog-1-{c}-{self._analog_file_index}"))
            self._analog_chunk_len = len(self._analog_data[0]) // 4

        values = []
        for data in self._analog_data:
            values.append(struct.unpack_from("f", data, (samplenum - self._analog_offset) * 4)[0])

        return values

CHUNK_SIZE = 4 * 1024 * 1024

class SrZipOutput(Output):
    name = "srzip"
    desc = "srzip session file format data"
    def __init__(self, filename, driver, logic_channels=[], analog_channels=[], decoders=[]):
        super().__init__()
        if decoders:
            raise NotImplementedError("Annotations can't be saved into .sr files.")

        self.zip = zipfile.ZipFile(filename, "w", compression=zipfile.ZIP_DEFLATED)

        self.zip.writestr("version", "2")
        metadata = configparser.ConfigParser()
        # libsigrok skips the global section.
        metadata.add_section("global")
        metadata.set("global", "pysigrok version", __version__)

        metadata.add_section("device 1")
        metadata.set("device 1", "driver", driver.name)
        metadata.set("device 1", "samplerate", str(driver.samplerate))
        self.driver = driver
        self.logic_buffer = None
        self._analog_buffers = []
        self._analog_indices = []
        self._analog_count = 1
        if logic_channels:
            self.capturefile = "logic-1"
            self.count = 1
            metadata.set("device 1", "capturefile", self.capturefile)
            self.unitsize = len(logic_channels) // 8 + 1
            metadata.set("device 1", "unitsize", str(self.unitsize))
            metadata.set("device 1", "total probes", str(len(logic_channels)))
            for i, channelname in enumerate(logic_channels):
                metadata.set("device 1", f"probe{i+1:d}", channelname)
            self.logic_buffer = array.array(TYPECODE[self.unitsize])
        if analog_channels:
            metadata.set("device 1", "total analog", str(len(analog_channels)))
            for i, channelname in enumerate(analog_channels):
                i += len(logic_channels)
                self._analog_indices.append(i + 1)
                self._analog_buffers.append(array.array("f"))
                metadata.set("device 1", f"analog{i+1:d}", channelname)

        with self.zip.open("metadata", "w") as f:
            metadata.write(io.TextIOWrapper(f))


    def output(self, source, startsample, endsample, data):
        # Only output data from the input driver.
        if source != self.driver:
            return
        ptype = data[0]
        if ptype == "logic":
            for _ in range(startsample, endsample):
                self.logic_buffer.append(data[1])
                if len(self.logic_buffer) * self.logic_buffer.itemsize >= CHUNK_SIZE:
                    fn = f"{self.capturefile}-{self.count:d}"
                    self.zip.writestr(fn, self.logic_buffer.tobytes())
                    self.count += 1
                    self.logic_buffer = array.array(TYPECODE[self.unitsize])
        elif ptype == "analog":
            for _ in range(startsample, endsample):
                if len(self._analog_buffers[0]) * 4 >= CHUNK_SIZE:
                    for i, file_index in enumerate(self._analog_indices):
                        fn = f"analog-1-{file_index:d}-{self._analog_count:d}"
                        self.zip.writestr(fn, self._analog_buffers[i].tobytes())
                        self._analog_buffers[i] = array.array("f")
                    self._analog_count += 1
                for i, file_index in enumerate(self._analog_indices):
                    self._analog_buffers[i].append(data[1 + i])

    def stop(self):
        if self.logic_buffer:
            fn = f"{self.capturefile}-{self.count:d}"
            self.zip.writestr(fn, self.logic_buffer.tobytes())
        if self._analog_buffers:
            for i, file_index in enumerate(self._analog_indices):
                fn = f"analog-1-{file_index:d}-{self._analog_count:d}"
                self.zip.writestr(fn, self._analog_buffers[i].tobytes())
        self.zip.close()
