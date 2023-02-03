import click

import functools
import sys

from . import srzip
from . import *

class Output:
    def __init__(self, outfile, output_type, decoder):
        self.outfile = outfile
        self.output_type = output_type
        self.decoder = decoder

    def decode(self, startsample, endsample, data):
        if self.output_type == OUTPUT_PYTHON:
            self.outfile.write(f"{startsample}-{endsample} {self.decoder.id}: {data}\n")

        elif self.output_type == OUTPUT_ANN:
            annotation = self.decoder.annotations[data[0]]
            data = " ".join(["\"" + str(x) + "\"" for x in data[1]])
            self.outfile.write(f"{startsample}-{endsample} {self.decoder.id}: {annotation[0]}: {data}\n")

        elif self.output_type == OUTPUT_BINARY:
            data = " ".join([f"{x:02x}" for x in data[1]])
            self.outfile.write(f"{startsample}-{endsample} {self.decoder.id}: {data}\n")

OUTPUT_TYPES = {
    "python": OUTPUT_PYTHON,
    "exception": OUTPUT_PYTHON,
    "annotation": OUTPUT_ANN,
    "binary": OUTPUT_BINARY,
}

class OrderedParamsCommand(click.Command):
    _options = []

    def parse_args(self, ctx, args):
        parser = self.make_parser(ctx)
        opts, _, param_order = parser.parse_args(args=list(args))
        for param in param_order:
            v = opts[param.name]
            if isinstance(v, list):
                v = v.pop(0)
            type(self)._options.append((param, v))

        return super().parse_args(ctx, args)

@click.command(cls=OrderedParamsCommand)
@click.option('-P', "--protocol-decoder", multiple=True)
@click.option("-p", "--pin-mapping", multiple=True, help="channelname=channelnum")
@click.option("-o", "--channel-option", multiple=True, help="channeloption=value")
@click.option("-N", "--channel-initial-value", multiple=True, help="channelname=initial-pin-value")
@click.option("-i", "--input-file")
@click.option("-O", "--output-format")
@click.option("-f", "--output-file")
def main(protocol_decoder, pin_mapping, channel_option, channel_initial_value, input_file, output_format, output_file):
    decoders = []
    current_decoder = None
    for param, value in OrderedParamsCommand._options:
        if param.name == "protocol_decoder":
            current_decoder = {"id": value, "cls": get_decoder(value), "options": {}, "pin_mapping": {}}
            decoders.append(current_decoder)
        elif param.name == "pin_mapping":
            decoder_id, channelnum = value.split("=")
            channelnum = int(channelnum)
            current_decoder["pin_mapping"][decoder_id] = channelnum
        elif param.name == "channel_option":
            k, v = value.split("=")
            for default_option in current_decoder["cls"].options:
                if default_option["id"] != k:
                    continue
                if isinstance(default_option["default"], int):
                    v = int(v)
            current_decoder["options"][k] = v

    initial_values = {}
    for v in channel_initial_value:
        decoder_id, value = v.split("=")
        value = int(value)
        initial_values[decoders[0]["pin_mapping"][decoder_id]] = value

    if output_file:
        f = open(output_file, "w")
    else:
        f = sys.stdout
    if output_format.count(":") == 1:
        decoder_id, output_name = output_format.split(":")
        output_filter = None
    else:
        decoder_id, output_name, output_filter = output_format.split(":", maxsplit=2)
    output_type = OUTPUT_TYPES[output_name]
    next_decoder = Output(f, output_type, decoders[-1]["cls"])

    data = srzip.SrZipInput(input_file, initial_values)
    all_decoders = []
    for decoder_info in reversed(decoders):
        decoder_class = decoder_info["cls"]
        decoder = decoder_class()
        all_decoders.insert(0, decoder)
        decoder.options = decoder_info["options"]

        # Set any default options that weren't on the command line.
        if hasattr(decoder_class, "options"):
            for option in decoder_class.options:
                if option["id"] not in decoder.options:
                    decoder.options[option["id"]] = option["default"]

        for decoder_id in decoder_info["pin_mapping"]:
            channelnum = decoder_info["pin_mapping"][decoder_id]
            decoder.set_channelnum(decoder_id, channelnum)        

        decoder.add_callback(output_type, output_filter, next_decoder.decode)
        next_decoder = decoder
        output_type = OUTPUT_PYTHON
        output_filter = None

    first_decoder = all_decoders[0]
    first_decoder.input = data
    for d in all_decoders:
        d.reset()
        d.start()
    if data.samplerate > 0:
        first_decoder.metadata(SRD_CONF_SAMPLERATE, data.samplerate)
    
    first_decoder.run(data)

    for d in all_decoders:
        d.stop()

    f.close()
