import click
from serial.tools import list_ports
import sys
if sys.version_info < (3, 10):
    from importlib_metadata import entry_points
else:
    from importlib.metadata import entry_points

drivers = entry_points(group='pysigrok.hardware')
driver_classes = {}
for hw in drivers:
    loaded = hw.load()
    driver_classes[loaded.name] = loaded

decoders = entry_points(group='pysigrok.decoders')
decoder_classes = {}
for decoder in decoders:
    loaded = decoder.load()
    decoder_classes[loaded.id] = loaded

@click.command()
@click.option("--list-supported", "-L", is_flag=True, default=False)
@click.option("--list-serial", is_flag=True, default=False)
@click.option("-d", "--driver")
@click.option("-i", "--input-file")
@click.option("-I", "--input-format")
@click.option("-o", "--output-file")
@click.option("-O", "--output-format")
@click.option("-C", "--channels")
@click.option("--time", "sample_time")
@click.option("--samples", type=int)
@click.option("--frames")
@click.option("--continuous", is_flag=True)
def main(list_supported, list_serial, driver, input_file, input_format, output_file, output_format, channels, sample_time, samples, frames, continuous):

    if list_supported:
        print("Supported hardware drivers:")
        for driver_id in driver_classes:
            driver_class = driver_classes[driver_id]
            print(f"  {driver_id}\t{driver_class.longname}")
        print()
        print("Supported input formats:")
        print()
        print("Supported output formats:")
        print()
        print("Supported transform modules:")
        print()
        print("Supported protocol decoders:")
        for pd in decoder_classes:
            decoder_class = decoder_classes[pd]
            print(f"  {pd}\t{decoder_class.longname}")
    elif list_serial:
        print("Available serial ports:")
        for port in list_ports.comports():
            print(" ", port)

    if driver:
        if ":" in driver:
            driver, options = driver.split(":", maxsplit=1)
            driver_options = {}
            for option in options.split(":"):
                k, v = option.split("=", maxsplit=1)
                driver_options[k] = v
        driver_class = None
        for hw in drivers:
            loaded = hw.load()
            if loaded.name == driver:
                driver_class = loaded

        driver = driver_class(**driver_options)

        if samples:
            # acquire data
            driver.acquire(samples)
