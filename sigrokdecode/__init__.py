"""Python implementation of sigrok tools"""
from enum import Enum
import sys
if sys.version_info < (3, 10):
    from importlib_metadata import entry_points
else:
    from importlib.metadata import entry_points

__version__ = "0.0.2"

class OutputType(Enum):
    SRD_OUTPUT_ANN = 0
    SRD_OUTPUT_PYTHON = 1
    SRD_OUTPUT_BINARY = 2
    SRD_OUTPUT_LOGIC = 3
    SRD_OUTPUT_META = 4

OUTPUT_ANN = OutputType.SRD_OUTPUT_ANN
OUTPUT_PYTHON = OutputType.SRD_OUTPUT_PYTHON
OUTPUT_BINARY = OutputType.SRD_OUTPUT_BINARY
OUTPUT_LOGIC = OutputType.SRD_OUTPUT_LOGIC
OUTPUT_META = OutputType.SRD_OUTPUT_META

class Decoder:
    # __init__() won't get called by subclasses

    def register(self, output_type, meta=None):
        # print("register", output_type, meta)
        return output_type

    def add_callback(self, output_type, fun):
        if not hasattr(self, "callbacks"):
            self.callbacks = {}

        if output_type not in self.callbacks:
            self.callbacks[output_type] = set()

        self.callbacks[output_type].add(fun)

    def wait(self, conds=None):
        assert(hasattr(self, "input"))
        if isinstance(conds, dict):
            conds = [conds]
        if self.one_to_one:
            data_conds = conds
        else:
            data_conds = []
            for cond in conds:
                data_cond = {}
                for k in cond:
                    data_cond[self.decoder_channel_to_data_channel[k]] = cond[k]
                data_conds.append(data_cond)
        raw_data = self.input.wait(data_conds)
        data = [None] * (len(self.channels) + len(getattr(self, "optional_channels", [])))
        for decoder_channel in self.decoder_channel_to_data_channel:
            data_channel = self.decoder_channel_to_data_channel[decoder_channel]
            data[decoder_channel] = raw_data[data_channel]
        return tuple(data)

    def put(self, startsample, endsample, output_id, data):
        # print(startsample, endsample, output_id, data)
        if not output_id in self.callbacks:
            return
        for cb in self.callbacks[output_id]:
            cb(startsample, endsample, data)

    def set_channelnum(self, channelname, channelnum):
        if not hasattr(self, "decoder_channel_to_data_channel"):
            self.decoder_channel_to_data_channel = {}
            self.one_to_one = True
        optional = []
        if hasattr(self, "optional_channels"):
            optional = self.optional_channels
        for i, c in enumerate(self.channels + optional):
            if c["id"] == channelname:
                self.decoder_channel_to_data_channel[i] = channelnum
                self.one_to_one = self.one_to_one and i == channelnum
                break

    def has_channel(self, decoder_channel):
        return decoder_channel in self.decoder_channel_to_data_channel

    @property
    def samplenum(self):
        return self.input.samplenum

    @property
    def matched(self):
        return self.input.matched

def get_decoder(decoder_id):
    discovered_plugins = entry_points(name=decoder_id, group='pysigrok.decoders')
    if len(discovered_plugins) == 1:
        return discovered_plugins[0].load()
    raise RuntimeError("Decoder id ambiguous:" + ",".join([p.name for p in discovered_plugins]))
