import pytest

from app.services.context.stages.base_stage import PipelineStage


def test_pipeline_stage_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        PipelineStage()


def test_concrete_subclass_implementing_process_can_be_instantiated():
    class _Passthrough(PipelineStage):
        def process(self, data):
            return data

    stage = _Passthrough()
    assert isinstance(stage, PipelineStage)
    assert stage.process("anything") == "anything"
