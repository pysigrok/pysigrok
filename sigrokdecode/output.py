"""Super class for output formats that make them look like decoders."""

class Output:
    def reset(self):
        pass

    def start(self):
        pass

    def metadata(self, key, value):
        pass

    def run(self, input_):
        done = False
        while not done:
            try:
                input_.wait([{"skip": 1000}])
            except EOFError:
                done = True


    def stop(self):
        pass
