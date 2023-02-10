import click

import functools
import sys

from . import srzip
from . import *
from .output import Output

class TestOutput(Output):
    def __init__(self, outfile, output_type, decoder_class):
        super().__init__()
        self.outfile = outfile
        self.output_type = output_type
        self.decoder_class = decoder_class

    def output(self, source, startsample, endsample, data):
        if type(source) != self.decoder_class:
            return
        if self.output_type == OUTPUT_PYTHON:
            self.outfile.write(f"{startsample}-{endsample} {self.decoder_class.id}: {data}\n")

        elif self.output_type == OUTPUT_ANN:
            annotation = self.decoder_class.annotations[data[0]]
            data = " ".join(["\"" + str(x) + "\"" for x in data[1]])
            self.outfile.write(f"{startsample}-{endsample} {self.decoder_class.id}: {annotation[0]}: {data}\n")

        elif self.output_type == OUTPUT_BINARY:
            data = " ".join([f"{x:02x}" for x in data[1]])
            self.outfile.write(f"{startsample}-{endsample} {self.decoder_class.id}: {data}\n")

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
            for default_option in getattr(current_decoder["cls"], "options", tuple()):
                current_decoder["options"][default_option["id"]] = default_option["default"]
            decoders.append(current_decoder)
        elif param.name == "pin_mapping":
            decoder_id, channelnum = value.split("=")
            channelnum = int(channelnum)
            current_decoder["pin_mapping"][decoder_id] = channelnum
        elif param.name == "channel_option":
            k, v = value.split("=")
            if isinstance(current_decoder["options"][k], int):
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
    output = TestOutput(f, output_type, decoders[-1]["cls"])

    data = srzip.SrZipInput(input_file, initial_values)
    run_decoders(data, output, decoders, output_type, output_filter)

    f.close()
