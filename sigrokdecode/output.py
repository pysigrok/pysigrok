"""Super class for output formats that make them look like decoders."""

class Output:
    def reset(self):
        pass

    def start(self):
        pass

    def run(self, input_):
        channelnum = len(input_.logic_channels)
        any_edge = [{i: "e"} for i in range(channelnum)]
        done = False
        # Store the last value. By searching for the next edge, we're measuring
        # how long the starting value is.
        last_values = None
        while not done:
            startsample = input_.samplenum
            try:
                values = input_.wait(any_edge)
            except EOFError:
                done = True
            endsample = input_.samplenum
            bits = 0
            if last_values:
                for i, v in enumerate(last_values):
                    if v:
                        bits |= 1 << i
                self.decode(startsample, endsample, ["logic", bits])
            last_values = values

    def stop(self):
        pass
