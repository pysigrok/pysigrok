"""Super class for output formats that make them look like decoders."""
import abc
from typing import Dict, List, Optional, Literal, Sequence, Tuple

from sigrokdecode import OutputType, DataType, OUTPUT_ANN, OUTPUT_BINARY

TriggerOptions = Dict[int, Literal["r", "f", "l", "h", "e", "s"]]


class Input(abc.ABC):
    name: str
    longname: str
    desc: str = ""
    annotations: Optional[Sequence[Tuple[str, str]]] = None
    binary: Optional[Sequence[Tuple[str, str]]] = None

    # updated before wait() returns, and contains the sample number that is currently
    # being triggered on
    samplenum: Optional[int] = None
    # updated before wait() returns, and contains a list of bools indicating which of
    # conditions in `cond` matched
    matched: Optional[List[bool]] = None

    def __init__(self, channellist, **kwargs):
        self.matched = None
        self.samplenum = None
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
                    assert self.annotations is not None
                    annotation = self.annotations[data[0]]
                    if annotation[0] != output_filter:
                        continue
                elif output_id == OUTPUT_BINARY:
                    assert self.binary is not None
                    track = self.binary[data[0]]
                    if track[0] != output_filter:
                        continue
            cb(startsample, endsample, data)

    @abc.abstractmethod
    def acquire(
        self, sample_count: int, triggers: TriggerOptions, pretrigger_data=None
    ):
        ...

    @abc.abstractmethod
    def wait(self, conds: Optional[List[TriggerOptions]] = None):
        ...
