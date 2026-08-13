from abc import ABC, abstractmethod


class PipelineStage(ABC):
    """Common contract for every context-pipeline stage.

    Each stage performs exactly one transformation and knows nothing about
    any other stage's internals or position in the pipeline -
    ContextPipeline composes them purely by calling process() in sequence,
    passing one stage's output as the next stage's input.
    """

    @abstractmethod
    def process(self, data):
        """Transform data and return the result for the next stage."""
        raise NotImplementedError
