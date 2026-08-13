from app.services.context.pipeline import ContextPipeline
from app.services.context.stages.base_stage import PipelineStage


class _RecordingStage(PipelineStage):
    def __init__(self, name, transform=None):
        self.name = name
        self.transform = transform or (lambda data: data)
        self.received = None

    def process(self, data):
        self.received = data
        return self.transform(data)


def test_runs_stages_in_the_order_given():
    call_order = []

    class _Tracking(PipelineStage):
        def __init__(self, name):
            self.name = name

        def process(self, data):
            call_order.append(self.name)
            return data

    pipeline = ContextPipeline([_Tracking("first"), _Tracking("second"), _Tracking("third")])

    pipeline.run("input")

    assert call_order == ["first", "second", "third"]


def test_passes_each_stages_output_as_the_next_stages_input():
    stage_a = _RecordingStage("a", transform=lambda data: data + 1)
    stage_b = _RecordingStage("b", transform=lambda data: data * 2)

    result = ContextPipeline([stage_a, stage_b]).run(1)

    assert stage_a.received == 1
    assert stage_b.received == 2  # stage_a's output
    assert result == 4  # stage_b's output


def test_empty_stage_list_returns_input_unchanged():
    pipeline = ContextPipeline([])

    assert pipeline.run("unchanged") == "unchanged"


def test_single_stage_pipeline():
    stage = _RecordingStage("only", transform=lambda data: data.upper())

    result = ContextPipeline([stage]).run("hello")

    assert result == "HELLO"


def test_stages_are_injected_through_the_constructor():
    stage = _RecordingStage("injected")
    pipeline = ContextPipeline([stage])

    assert pipeline.stages == [stage]
