import array
import zipfile
import configparser
import struct
import pathlib
import io

from .output import Output

from . import cond_matches, __version__

TYPECODE = {
    1: "B",
    2: "H",
    4: "L"
}

UNITS = {
    "Hz":  1,
    "kHz": 1000,
    "KHz": 1000,
    "MHz": 1000000,
    "mHz": 1000000,
}

class SrZipInput:
    name = "srzip"
    desc = "srzip session file format data"
    def __init__(self, filename, initial_state=None):
        self.zip = zipfile.ZipFile(filename)
        # self.zip.printdir()
        self.metadata = configparser.ConfigParser()
        self.version = int(self.zip.read("version").decode("ascii"))
        self.metadata.read_string(self.zip.read("metadata").decode("ascii"))
        self.samplenum = -1
        self.matched = None
        self.single_file = "logic-1" in self.zip.namelist()
        # for s in self.metadata.sections():
        #     print(s)
        #     for o in self.metadata.options(s):
        #         print(" ", o, self.metadata.get(s, o))

        samplerate = self.metadata.get("device 1", "samplerate", fallback="0")
        # print(samplerate)
        if " " in samplerate:
            num, units = samplerate.split(" ")
            self.samplerate = float(num) * UNITS[units]
        else:
            self.samplerate = int(samplerate)

        if initial_state:
            self.last_sample = 0
            for channel in initial_state:
                self.last_sample |= initial_state[channel] << channel
        else:
            self.last_sample = None
        self.unitsize = int(self.metadata.get("device 1", "unitsize"))
        self.typecode = TYPECODE[self.unitsize]

        if self.single_file:
            self.data = self.zip.read("logic-1")
            if self.unitsize > 1:
                self.data = array.array(self.typecode, self.data)
        else:
            self.data = None
            self._file_start = -1
            self._file_index = 1

    def wait(self, conds=None):
        self.matched = [False]
        while not any(self.matched):
            self.matched = [True] * len(conds)
            self.samplenum += 1
            if self.single_file:
                if self.samplenum >= len(self.data):
                    raise EOFError()
                sample = self.data[self.samplenum]
            else:
                file_samplenum = self.samplenum - self._file_start
                if self.data is None or file_samplenum >= len(self.data):
                    self._file_start = self.samplenum
                    try:
                        self.data = self.zip.read(f"logic-1-{self._file_index:d}")
                    except KeyError:
                        raise EOFError()

                    if self.unitsize > 1:
                        self.data = array.array(self.typecode, self.data)

                    file_samplenum = 0
                    self._file_index += 1
                sample = self.data[file_samplenum]

            if self.last_sample is None:
                self.last_sample = sample

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

CHUNK_SIZE = 4 * 1024 * 1024

class SrZipOutput(Output):
    name = "srzip"
    desc = "srzip session file format data"
    def __init__(self, filename, driver, logic_channels=[], analog_channels=[], annotations=[]):
        if annotations:
            raise NotImplementedError("Annotations can't be saved into .sr files.")

        self.zip = zipfile.ZipFile(filename, "w", compression=zipfile.ZIP_DEFLATED)

        self.zip.writestr("version", "2")
        self.metadata = configparser.ConfigParser()
        # libsigrok skips the global section.
        self.metadata.add_section("global")
        self.metadata.set("global", "pysigrok version", __version__)

        self.metadata.add_section("device 1")
        self.metadata.set("device 1", "driver", driver.name)
        self.metadata.set("device 1", "samplerate", str(driver.samplerate))
        self.logic_buffer = None
        if logic_channels:
            self.capturefile = "logic-1"
            self.count = 1
            self.metadata.set("device 1", "capturefile", self.capturefile)
            self.unitsize = len(logic_channels) // 8 + 1
            self.metadata.set("device 1", "unitsize", str(self.unitsize))
            self.metadata.set("device 1", "total probes", str(len(logic_channels)))
            for i, channelname in enumerate(logic_channels):
                self.metadata.set("device 1", f"probe{i+1:d}", channelname)
            self.logic_buffer = array.array(TYPECODE[self.unitsize])
        if analog_channels:
            self.metadata.set("device 1", "total analog", len(analog_channels))
            for i, channelname in enumerate(analog_channels):
                self.metadata.set("device 1", f"analog{i+1:d}", channelname)

        with self.zip.open("metadata", "w") as f:
            self.metadata.write(io.TextIOWrapper(f))


    def decode(self, startsample, endsample, data):
        ptype = data[0]
        if ptype == "logic":
            for _ in range(startsample, endsample):
                self.logic_buffer.append(data[1])
                if len(self.logic_buffer) >= CHUNK_SIZE:
                    fn = f"{self.capturefile}-{self.count:d}"
                    self.zip.writestr(f"{self.capturefile}-{self.count:d}", self.logic_buffer.tobytes())
                    self.count += 1
                    self.logic_buffer = array.array(TYPECODE[self.unitsize])

    def stop(self):
        if self.logic_buffer:
            fn = f"{self.capturefile}-{self.count:d}"
            self.zip.writestr(fn, self.logic_buffer.tobytes())
        self.zip.close()
