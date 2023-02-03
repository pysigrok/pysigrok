# pysigrok

This re-implements the sigrok core and utilizes Python's entry points for plugins. This alleviates the need for a central repo of decoders, hardware and file format implementations.

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



