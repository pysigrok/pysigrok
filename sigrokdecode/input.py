"""Super class for output formats that make them look like decoders."""
from sigrokdecode import OutputType, DataType, OUTPUT_ANN, OUTPUT_BINARY


class Input:
    def __init__(self):
        self.callbacks = {}

    def add_callback(self, output_type, output_filter, fun):
        if output_type not in self.callbacks:
            self.callbacks[output_type] = set()

        self.callbacks[output_type].add((output_filter, fun))

    def put(
        self, startsample: int, endsample: int, output_id: OutputType, data: DataType
    ) -> None:
        """
        This is used to provide the decoded data back into the backend

        :param startsample: absolute sample number of where this item (e.g. an
            annotation) starts
        :param endsample: absolute sample number of where this item (e.g. an annotation)
            ends
        :param output_id:
        :param data: contents depend on the output type
        :return: None
        """
        # print(startsample, endsample, output_id, data)
        if output_id not in self.callbacks:
            return
        for output_filter, cb in self.callbacks[output_id]:
            if output_filter is not None:
                if output_id == OUTPUT_ANN:
                    annotation = self.annotations[data[0]]
                    if annotation[0] != output_filter:
                        continue
                elif output_id == OUTPUT_BINARY:
                    track = self.binary[data[0]]
                    if track[0] != output_filter:
                        continue
            cb(startsample, endsample, data)
