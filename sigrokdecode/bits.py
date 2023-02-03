from .output import Output

class BitsOutput(Output):
    name = "bits"
    desc = "ASCII rendering with 0/1"
    def __init__(self, openfile, driver, logic_channels=[], *, width="64"):
        self.width = int(width)
        for i, channel in enumerate(logic_channels):
            print(i, channel)

    def decode(self, startsample, endsample, data):
        ptype = data[0]
        if ptype == "logic":
            print(startsample, endsample, data)
