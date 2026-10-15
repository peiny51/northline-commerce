import os


class Config:
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")
    QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "northline_policies")
