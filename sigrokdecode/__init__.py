"""Python implementation of sigrok tools"""
from enum import Enum
import sys
if sys.version_info < (3, 10):
    from importlib_metadata import entry_points
else:
    from importlib.metadata import entry_points
import functools

__version__ = "0.4.2"

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

SRD_CONF_SAMPLERATE = 1

def SR_KHZ(num):
    return num * 1000

def SR_MHZ(num):
    return SR_KHZ(num) * 1000

class Decoder:
    # __init__() won't get called by subclasses

    def register(self, output_type, proto_id=None, meta=None):
        # print("register", output_type, meta)
        return output_type

    def metadata(self, key, value):
        # Backup for decoders that don't care.
        pass

    def add_callback(self, output_type, output_filter, fun):
        # print(output_type, output_filter, fun)
        if not hasattr(self, "callbacks"):
            self.callbacks = {}

        if output_type not in self.callbacks:
            self.callbacks[output_type] = set()

        self.callbacks[output_type].add((output_filter, fun))

    def wait(self, conds=[]):
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
                    if k == "skip":
                        data_cond["skip"] = cond[k]
                    else:
                        data_cond[self.decoder_channel_to_data_channel[k]] = cond[k]
                data_conds.append(data_cond)

        raw_data = self.input.wait(data_conds)
        data = [None] * (len(type(self).channels) + len(getattr(type(self), "optional_channels", [])))
        for decoder_channel in self.decoder_channel_to_data_channel:
            data_channel = self.decoder_channel_to_data_channel[decoder_channel]
            data[decoder_channel] = raw_data[data_channel]

        return tuple(data)

    def put(self, startsample, endsample, output_id, data):
        # print(startsample, endsample, output_id, data)
        if not output_id in self.callbacks:
            return
        for output_filter, cb in self.callbacks[output_id]:
            if output_filter is not None:
                if output_id == OUTPUT_ANN:
                    annotation = self.annotations[data[0]]
                    if annotation[0] != output_filter:
                        continue
                elif output_id == OUTPUT_BINARY:
                    track = self.binary[data[0]]
                    if track[0] != output_filter:
                        continue
            cb(startsample, endsample, data)

    def set_channelnum(self, channelname, channelnum):
        if not hasattr(self, "decoder_channel_to_data_channel"):
            self.decoder_channel_to_data_channel = {}
            self.one_to_one = True

        if not hasattr(type(self), "optional_channels"):
            type(self).optional_channels = tuple()
        if not hasattr(type(self), "channels"):
            type(self).channels = tuple()
        for i, c in enumerate(type(self).channels + type(self).optional_channels):
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

    def run(self, input_):
        self.input = input_
        try:
            self.decode()
        except EOFError:
            pass

    def stop(self):
        pass

def get_decoder(decoder_id):
    discovered_plugins = entry_points(name=decoder_id, group='pysigrok.decoders')
    if len(discovered_plugins) == 1:
        return discovered_plugins[0].load()
    raise RuntimeError("Decoder id ambiguous:" + ",".join([p.name for p in discovered_plugins]))


def cond_matches(cond, last_sample, current_sample):
    matches = True
    for channel in cond:
        if channel == "skip":
            return cond["skip"] == 0
        state = cond[channel]
        mask = 1 << channel
        last_value = last_sample & mask
        value = current_sample & mask
        if ((state == "l" and value != 0) or
            (state == "h" and value == 0) or
            (state == "r" and not (last_value == 0 and value != 0)) or
            (state == "f" and not (last_value != 0 and value == 0)) or
            (state == "e" and last_value == value) or
            (state == "s" and last_value != value)):
                matches = False
                break
    return matches

def run_decoders(input_, output, decoders=[], output_type=OUTPUT_ANN, output_filter=None):
    input_.add_callback(OUTPUT_PYTHON, None, functools.partial(output.output, input_))

    all_decoders = []
    next_decoder = None
    for decoder_info in reversed(decoders):
        decoder_class = decoder_info["cls"]
        decoder = decoder_class()
        all_decoders.insert(0, decoder)
        decoder.options = decoder_info["options"]

        for decoder_id in decoder_info["pin_mapping"]:
            channelnum = decoder_info["pin_mapping"][decoder_id]
            decoder.set_channelnum(decoder_id, channelnum)

        decoder.add_callback(output_type, output_filter, functools.partial(output.output, decoder))
        if next_decoder:
            decoder.add_callback(output_type, output_filter, next_decoder.decode)
        next_decoder = decoder
        output_type = OUTPUT_PYTHON
        output_filter = None

    if all_decoders:
        first_decoder = all_decoders[0]
    else:
        first_decoder = output
    for d in all_decoders:
        d.reset()
    output.reset()

    if input_.samplerate > 0:
        first_decoder.metadata(SRD_CONF_SAMPLERATE, input_.samplerate)

    output.start()
    for d in all_decoders:
        d.start()

    first_decoder.run(input_)

    for d in all_decoders:
        d.stop()
    output.stop()