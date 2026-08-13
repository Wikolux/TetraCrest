from app.services.context.stages.base_stage import PipelineStage


class ContextPipeline:
    """Executes a sequence of PipelineStages, passing each stage's output
    as the next stage's input.

    Fully generic: has no knowledge of DuplicateStage/BudgetStage/
    GroupingStage/FormatterStage specifically, or of how many stages there
    are. ContextBuilder decides which concrete stages to run and in what
    order; this class only knows how to run whatever list it's given.
    """

    def __init__(self, stages: list[PipelineStage]):
        self.stages = stages

    def run(self, data):
        for stage in self.stages:
            data = stage.process(data)
        return data
