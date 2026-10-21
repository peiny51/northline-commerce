import os


class Config:
    # Maximum recent messages included in each model request (including latest user message).
    AI_HISTORY_MESSAGE_LIMIT = max(1, int(os.getenv("AI_HISTORY_MESSAGE_LIMIT", "10")))
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")
    QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "northline_policies")
