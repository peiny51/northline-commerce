"""Initialize LangGraph checkpoint tables in the existing PostgreSQL database."""

import os
from pathlib import Path

from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")


def main():
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://outdoor:outdoor@127.0.0.1:5434/northline_django",
    )
    # Run once after installing requirements; it does not touch Django tables.
    with PostgresSaver.from_conn_string(database_url) as checkpointer:
        checkpointer.setup()
    print("LangGraph PostgreSQL checkpoint tables are ready.")


if __name__ == "__main__":
    main()
