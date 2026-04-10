from config import EMBEDDING_MODEL


class EmbeddingService:
    def __init__(self, model_name: str = EMBEDDING_MODEL):
        self._model = None
        self._model_name = model_name

    def _get_model(self):
        if self._model is None:
            from fastembed import TextEmbedding
            self._model = TextEmbedding(model_name=self._model_name)
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        embeddings = list(model.passage_embed(texts))
        return [emb.tolist() if hasattr(emb, "tolist") else list(emb) for emb in embeddings]

    def embed_query(self, text: str) -> list[float]:
        model = self._get_model()
        embeddings = list(model.query_embed(text))
        emb = embeddings[0]
        return emb.tolist() if hasattr(emb, "tolist") else list(emb)
