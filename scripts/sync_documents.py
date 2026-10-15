"""Run explicitly after policy changes; never during Django server startup."""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
from dotenv import load_dotenv

load_dotenv()
from backend.ai.rag.vector_store import sync_documents

if __name__ == "__main__":
    sync_documents()
