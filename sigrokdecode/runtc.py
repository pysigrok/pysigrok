import click

import functools

from . import srzip
from . import *

def output_python(decoder, outfilter, outfile, startsample, endsample, data):
    outfile.write(f"{startsample}-{endsample} {decoder.id}: {data}\n".encode("utf-8"))

def output_annotation(decoder, outfilter, outfile, startsample, endsample, data):
    annotation = decoder.annotations[data[0]]
    if outfilter is None or annotation[0] == outfilter:
        data = " ".join([repr(x) for x in data[1]]).replace("\'", "\"")
        outfile.write(f"{startsample}-{endsample} {decoder.id}: {annotation[0]}: {data}\n".encode("utf-8"))

def output_binary(decoder, outfilter, outfile, startsample, endsample, data):
    track = decoder.binary[data[0]]
    if track[0] == outfilter:
        data = " ".join([f"{x:02x}" for x in data[1]])
        outfile.write(f"{startsample}-{endsample} {decoder.id}: {data}\n".encode("utf-8"))

OUTPUT_TYPES = {
    "python": (OUTPUT_PYTHON, output_python),
    "annotation": (OUTPUT_ANN, output_annotation),
    "binary": (OUTPUT_BINARY, output_binary)
}

@click.command()
@click.option('-P', "--protocol-decoder")
@click.option("-p", "--pin-mapping", multiple=True, help="channelname=channelnum")
@click.option("-o", "--channel-option", multiple=True, help="channeloption=value")
@click.option("-N", "--channel-initial-value", multiple=True, help="channelname=initial-pin-value")
@click.option("-i", "--input-file")
@click.option("-O", "--output-format")
@click.option("-f", "--output-file")
def main(protocol_decoder, pin_mapping, channel_option, channel_initial_value, input_file, output_format, output_file):
    parsed_mapping = {}
    for mapping in pin_mapping:
        decoder_id, channelnum = mapping.split("=")
        channelnum = int(channelnum)
        parsed_mapping[decoder_id] = channelnum

    initial_values = {}
    for v in channel_initial_value:
        decoder_id, value = v.split("=")
        value = int(value)
        initial_values[parsed_mapping[decoder_id]] = value


    data = srzip.SrZip(input_file, initial_values)
    decoder_class = get_decoder(protocol_decoder)
    decoder = decoder_class()
    decoder.options = {}
    if hasattr(decoder_class, "options"):
        for o in decoder_class.options:
            decoder.options[o["id"]] = o["default"]
    decoder.input = data
    for decoder_id in parsed_mapping:
        channelnum = parsed_mapping[decoder_id]
        decoder.set_channelnum(decoder_id, channelnum)

    with open(output_file, "wb") as f:
        if output_format.count(":") == 1:
            decoder_id, output_name = output_format.split(":")
            output_filter = None
        else:
            decoder_id, output_name, output_filter = output_format.split(":", maxsplit=2)
        output_type, output_fun = OUTPUT_TYPES[output_name]
        decoder.add_callback(output_type, functools.partial(output_fun, decoder, output_filter, f))
        decoder.start()
        decoder.reset()
        try:
            decoder.decode()
        except EOFError:
            pass

