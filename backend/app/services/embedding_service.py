from app.services.embedding.base_provider import EmbeddingProvider
from app.services.embedding.provider_factory import EmbeddingProviderFactory


class EmbeddingService:
    """Turns text into embeddings. Nothing else.

    Delegates all provider-specific work to whichever EmbeddingProvider
    EmbeddingProviderFactory resolves - this service knows nothing about
    OpenAI, or any other backend, or how providers are selected.

    Its responsibility ends once it returns vectors: it has no knowledge
    of VectorStore, persistence, or any storage backend. Coordinating
    generation with storage is EmbeddingPersistenceService's job.
    """

    def __init__(self, provider: EmbeddingProvider | None = None):
        self.provider = provider or EmbeddingProviderFactory.create()

    def generate_embedding(self, text: str) -> list[float]:
        return self.generate_embeddings([text])[0]

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        return self.provider.embed(texts)
