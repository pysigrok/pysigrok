import zipfile
import configparser

class SrZip:
    def __init__(self, filename, initial_state=None):
        self.zip = zipfile.ZipFile(filename)
        # self.zip.printdir()
        self.metadata = configparser.ConfigParser()
        self.version = int(self.zip.read("version").decode("ascii"))
        self.metadata.read_string(self.zip.read("metadata").decode("ascii"))
        self.samplenum = -1
        self.matched = None
        # print(self.version)
        # for s in self.metadata.sections():
        #     print(s)
        #     for o in self.metadata.options(s):
        #         print(" ", o, self.metadata.get(s, o))

        self.last_sample = 0
        for channel in initial_state:
            self.last_sample |= initial_state[channel] << channel
        self.unitsize = int(self.metadata.get("device 1", "unitsize"))
        assert(self.unitsize == 1)

        if self.version == 1:
            self.data = self.zip.read("logic-1")
        else:
            self.data = None
            self._file_start = -1
            self._file_index = 1

    def wait(self, conds=None):
        self.matched = [False]
        while not any(self.matched):
            self.matched = [True] * len(conds)
            self.samplenum += 1
            if self.version == 1:
                if self.samplenum * self.unitsize >= len(self.data):
                    raise EOFError()
                sample = self.data[self.samplenum]
            elif self.version == 2:
                file_samplenum = self.samplenum - self._file_start
                if self.data is None or file_samplenum * self.unitsize >= len(self.data):
                    self._file_start = self.samplenum
                    try:
                        self.data = self.data = self.zip.read(f"logic-1-{self._file_index:d}")
                    except KeyError:
                        raise EOFError()
                    file_samplenum = 0
                    self._file_index += 1
                sample = self.data[file_samplenum]

            for i, cond in enumerate(conds):
                for channel in cond:
                    state = cond[channel]
                    mask = 1 << channel
                    last_value = self.last_sample & mask
                    value = sample & mask
                    if ((state == "l" and value != 0) or
                        (state == "h" and value == 0) or
                        (state == "r" and not (last_value == 0 and value != 0)) or
                        (state == "f" and not (last_value != 0 and value == 0)) or
                        (state == "e" and last_value == value) or
                        (state == "s" and last_value != value)):
                            self.matched[i] = False
                            break
            self.last_sample = sample

        bits = []
        for b in range(self.unitsize * 8):
            bits.append((sample >> b) & 0x1)

        return tuple(bits)

