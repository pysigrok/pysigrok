# pysigrok

This re-implements the sigrok core and utilizes Python's entry points for plugins. This alleviates the need for a central repo of decoders, hardware and file format implementations.

> **Warning**
> `pysigrok` is very new and below is a brain dump of the process. Please ask questions and propose changes via PR. The [Adafruit Discord](https://adafru.it/discord) has a #pysigrok channel for discussion.

## Quick start

To install the raspberry pi pico support and sigrok decoders do:

```sh
pip install pysigrok-hardware-raspberrypi-pico pysigrok-libsigrokdecode
```

Once installed you can list supported hardware, formats and decoders with:

```sh
$ pysigrok-cli -L

Supported hardware drivers:
  raspberrypi-pico      RaspberryPI PICO

Supported input formats:
  srzip srzip session file format data

Supported output formats:
  bits  ASCII rendering with 0/1
  srzip srzip session file format data

Supported transform modules:

Supported protocol decoders:
  ac97  Audio Codec \'97
  ad5626        Analog Devices AD5626
  ad79x0        Analog Devices AD79x0
...
```

You'll need to install the sigrok-pico code onto your RP2040. The [source is on Github](https://github.com/tannewt/sigrok-pico) and the [uf2 to install is as well](https://github.com/tannewt/sigrok-pico/blob/main/pico_sdk_sigrok/build/pico_sdk_sigrok.uf2).

To find the CDC device for the RP2040:

```sh
$ pysigrok-cli --list-serial

Available serial ports:
  /dev/ttyUSB0 - CP2102N USB to UART Bridge Controller
  /dev/ttyACM2 - Pico - Board CDC
  /dev/ttyACM1 - nRF52 Connectivity
  /dev/ttyACM0 - Feather M0 Express - CircuitPython CDC control
```

To capture to a sigrok `.sr` file:

```sh
pysigrok-cli -d raspberrypi-pico:conn=/dev/ttyACM2 -C D16,D17,D18,D19 --samples 10 -c samplerate=10000000 -o test.sr
```

## Extending pysigrok
pysigrok's goal is to make it easier to extend than normal sigrok. It does this by utilizing [Python packaging's entry point mechanic for a plugin system](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/). You can have a separately developed and distributed python module used by `pysigrok-cli` without needing to modify the `pysigrok` repo. There are four ways to extend pysigrok: capture driver, file format input, file format output and protocol decoder.

### New repo
`pysigrok` repos use [`flit`]() with `pyproject.toml` for easy package creation and publication.

To start a new extension, create a repo, init flit and init git.

```sh
mkdir my-extension
cd my-extension
flit init
git init
```

`flit init` will ask for a package name. This is used when someone will `pip install` it. You should prefix it with `pysigrok` so it's [easily searchable on pypi](https://pypi.org/search/?q=pysigrok). You can also then do `format`, `hardware` or `decoder` to classify it. So something like `pysigrok-decoder-my-extension`.

Next, create a python file, `my_extension.py` to hold your extension.

```python
"""My extension does..."""

__version__ = "0.0.1"

class Foo:
    ...
```

Now edit the generated `pyproject.toml`. Under the `[project]` portion add:

```toml
dependencies = [
    "pysigrok >= 0.4.0"
]
```

If you don't want the Python filename to match the package name, you can add a section to tell flit what module name to use (replace `my_extension`):
```toml
[tool.flit.module]
name = "my_extension"
```

Add a new section for the entry point your extension provides. (You can add multiple.)
```toml
[project.entry-points."pysigrok.entry_group"]
id = "modulename:ClassName"
```

Replace:
* `entry_group` with the corresponding name below.
* `id` with a unique to your package name. (pysigrok doesn't use this yet.)
* `modulename` is the same as the Python file you made without the `.py`.
* `ClassName` is the extension class within the file. (A file can have more than one. See [`srzip.py`](https://github.com/pysigrok/pysigrok/blob/main/sigrokdecode/srzip.py) for an example.)

Once you've setup the .py file and `pyproject.toml` you can install the extension in editable mode with:

```sh
pip install -e .
```

Now, your installed `pysigrok-cli` should be able to discover your extension and run it. It will use the .py file in the current directory each time so you don't need to reinstall every time you change the file. To verify do:

```sh
pysigrok-cli -L
```

This should list all drivers, formats and decoders that have been pip installed.

To publish your extension to pypi do:

```sh
flit publish
```

It's also a good idea to push to a public git repo to backup your code.

### Capture driver
A capture driver acquires data from a hardware device and then acts like an input to decoders and file output. It uses the entry point group `pysigrok.hardware`. The [raspberrypi-pico is the first example repo](https://github.com/pysigrok/hardware-raspberrypi-pico).

The capture driver must implement:

```python
class SkeletonDriver(Input):
    name = "short name used for id"
    longname = "Human readable name"
    
    def __init__(self, channellist):
        self.samplenum
        self.matched
        ...

    def acquire(self, sample_count, triggers, pretrigger_data):
        ...
        
    def wait(self, conds=None):
        ...
```

* `name` is the short id used in the cli
* `longname` is used as the human readable name when listing
* `__init__()` takes in channel list to capture and any config options as kwargs.
* `acquire()` takes in the sample count to capture and trigger settings. Triggers is a dictionary with pin as the key and a trigger value. The trigger values are strings: `r`ising edge, `f`alling edge, `l`ow value, `h`igh value, any `e`dge and `s`ame value. (In the CLI it is `0` and `1` for low and high but this API is normalized to match `wait()`.

### File input
File inputs are used to run existing data through protocol decoders and then output the result back to a file or to the CLI. [pysigrok has support for sigrok's srzip format](https://github.com/pysigrok/pysigrok/blob/main/sigrokdecode/srzip.py) for interoperability with sigrok and, therefore, PulseView. File inputs use the entry point group `pysigrok.input_format`.

```python
class SkeletonInput(Input):
    name = "short name used for id"
    desc = "Human readable description"
    
    def __init__(self, filename, initial_state=None):
        self.samplenum
        self.matched
        ...

    def wait(self, conds=None):
        ...
```

File inputs are similar to capture drivers because they both implement `wait()`. `wait()` is used by the first stage protocol decoder to skip to the next interesting sample based on conditions or triggers. `wait()`'s trigger conditions are a bit more complex than the `acquire()` trigger because it can be a list of trigger dictionaries. Wait proceeds through samples until one or more of the dictionaries matches. `self.matches` is a list of bools to indicate which of the previous provided conditions matched. `self.samplenum` should be updated as well.

`wait()` also has a `skip` condition that can be used to skip a set number of samples.

The implementation of wait must go through samples until one or more condition matches and then return the bit values as a list of bools. As it goes along, it should also call `self.put(start_samplenum, end_samplenum, OUTPUT_PYTHON, ["logic", sample])` for each range of sample values. This is used for outputs and is the same API used for decoders to output their decoded data. Analog values are `self.put(ss, es, OUTPUT_PYTHON, ["analog", <float values>]`

### Protocol decoders
`sigrok`'s [existing protocol decoders](https://github.com/pysigrok/libsigrokdecode) are written in Python already. There are really two types of decoders. First level decoders use the `wait()` API to seek through an input when their `decode()` method is called. Stacked decoders have a `decode(ss, es, output_type, data)` API where it is called for every emitted piece of data from the previous decoder. They then emit their own data by calling `put(ss, es, output_type, data)`. This data may go to another decoder or an output formatter.

`pysigrok` packages the existing decoders into the [`pysigrok-libsigrokdecode` Python package](https://github.com/pysigrok/libsigrokdecode) and [most](https://github.com/pysigrok/libsigrokdecode/actions) work with `pysigrok-cli`. Decoders use the `pysigrok.decoders` entry point group.

Decoders have `reset()`, `start()`, `decode()` and `stop()` functions to hook into the decoding lifecycle.

### File output
File outputs are used to write a particular format to a given file which may be stdout. They use the entry point group `pysigrok.output_format`.


```python
class SkeletonOutput(Input):
    name = "short name used for id"
    desc = "Human readable description"
    
    def __init__(self, openfile, driver, logic_channels=[], analog_channels=[]):
        ...

    def output(self, source, startsample, endsample, data):
        ...
        
    def stop(self):
        ...
```

Outputs receive all OUTPUT_PYTHON events from the driver/input and any OUTPUT_ANN events from the decoders. The source class is the first argument to `output()`. The remaining arguments match `put()`.


Outputs have `reset()`, `start()`, `output()` and `stop()` functions to hook into the decode lifecycle.
