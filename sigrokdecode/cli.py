import click
import pathlib
from serial.tools import list_ports
import sys

if sys.version_info < (3, 10):
    from importlib_metadata import entry_points
else:
    from importlib.metadata import entry_points

drivers = entry_points(group="pysigrok.hardware")
driver_classes = {}
for hw in drivers:
    loaded = hw.load()
    driver_classes[loaded.name] = loaded

input_formats = entry_points(group="pysigrok.input_format")
input_classes = {}
for f in input_formats:
    loaded = f.load()
    input_classes[loaded.name] = loaded

output_formats = entry_points(group="pysigrok.output_format")
output_classes = {}
for f in output_formats:
    loaded = f.load()
    output_classes[loaded.name] = loaded

decoders = entry_points(group="pysigrok.decoders")
decoder_classes = {}
for decoder in decoders:
    loaded = decoder.load()
    decoder_classes[loaded.id] = loaded


@click.command()
@click.option("--list-supported", "-L", is_flag=True, default=False)
@click.option("--list-serial", is_flag=True, default=False)
@click.option("-d", "--driver")
@click.option("-c", "--config", "configs")
@click.option("-i", "--input-file")
@click.option("-I", "--input-format", default="srzip")
@click.option("-o", "--output-file")
@click.option("-O", "--output-format")
@click.option("-C", "--channels", help="comma separated list of channels to capture")
@click.option("-t", "--triggers", help="comma separated list of triggers")
@click.option("-w", "--wait-trigger", is_flag=True, default=False)
@click.option("--time", "sample_time")
@click.option("--samples", type=int)
@click.option("--frames")
@click.option("--continuous", is_flag=True)
def main(
    list_supported,
    list_serial,
    driver,
    configs,
    input_file,
    input_format,
    output_file,
    output_format,
    channels,
    triggers,
    wait_trigger,
    sample_time,
    samples,
    frames,
    continuous,
):
    if list_supported:
        print("Supported hardware drivers:")
        for driver_id in driver_classes:
            driver_class = driver_classes[driver_id]
            print(f"  {driver_id}\t{driver_class.longname}")
        print()
        print("Supported input formats:")
        for input_format_id in input_classes:
            input_class = input_classes[input_format_id]
            print(f"  {input_format_id}\t{input_class.desc}")
        print()
        print("Supported output formats:")
        for output_format_id in output_classes:
            output_class = output_classes[output_format_id]
            print(f"  {output_format_id}\t{output_class.desc}")
        print()
        print("Supported transform modules:")
        print()
        print("Supported protocol decoders:")
        for pd in decoder_classes:
            decoder_class = decoder_classes[pd]
            print(f"  {pd}\t{decoder_class.longname}")
        return
    elif list_serial:
        print("Available serial ports:")
        for port in list_ports.comports():
            print(" ", port)
        return

    if driver:
        driver_options = {}
        if ":" in driver:
            driver, options = driver.split(":", maxsplit=1)
            for option in options.split(":"):
                k, v = option.split("=", maxsplit=1)
                driver_options[k] = v
        driver_configs = {}
        if configs:
            for config in configs.split(":"):
                k, v = config.split("=", maxsplit=1)
                driver_configs[k] = v

        driver_class = None
        for hw in drivers:
            loaded = hw.load()
            if loaded.name == driver:
                driver_class = loaded

        driver = driver_class(channels, **driver_options, **driver_configs)

        if samples:
            triggers = triggers.split(",")
            trigger_dict = {}
            for t in triggers:
                pin, condition = t.split("=")
                if len(condition) > 1 or condition not in "01rfe":
                    raise ValueError("Only single 0, 1, r, f or e triggers supported.")
                if condition == "0":
                    condition = "l"
                elif condition == "1":
                    condition = "h"
                trigger_dict[pin] = condition
            # acquire data
            driver.acquire(samples, trigger_dict, not wait_trigger)

    elif input_file:
        input_class = input_classes[input_format]
        driver = input_class(input_file)

    if output_file:
        # Delete the file if it exists
        p = pathlib.Path(output_file)
        p.unlink(missing_ok=True)
        f = open(output_file, "wb")
        if not output_format:
            output_format = "srzip"
    else:
        f = sys.stdout
        if not output_format:
            output_format = "bits:width=64"
    output_options = {}
    if ":" in output_format:
        output_split = output_format.split(":")
        output_format_id = output_split[0]
        for option in output_split[1:]:
            if "=" in option:
                k, v = option.split("=")
                output_options[k] = v
            else:
                output_options[option] = "true"
    else:
        output_format_id = output_format

    output_class = output_classes[output_format_id]

    next_decoder = output_class(
        f,
        driver,
        logic_channels=driver.logic_channels,
        analog_channels=driver.analog_channels,
        **output_options,
    )
    next_decoder.reset()
    next_decoder.start()
    next_decoder.run(driver)

    next_decoder.stop()
