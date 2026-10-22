import json
from pathlib import Path

from mcp.shared.auth import (
    OAuthClientInformationFull,
    OAuthToken
)


class FileTokenStorage:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)

    async def get_tokens(self) -> OAuthToken | None:
        data = self._load_data()

        token_data = data.get("tokens")

        if token_data is None:
            return None

        return OAuthToken.model_validate(token_data)

    async def set_tokens(self, tokens: OAuthToken) -> None:
        data = self._load_data()

        data["tokens"] = tokens.model_dump(
            mode="json",
            exclude_none=True
        )

        self._save_data(data)

    async def get_client_info(
        self
    ) -> OAuthClientInformationFull | None:
        data = self._load_data()

        client_info_data = data.get("client_info")

        if client_info_data is None:
            return None

        return OAuthClientInformationFull.model_validate(
            client_info_data
        )

    async def set_client_info(
        self,
        client_info: OAuthClientInformationFull
    ) -> None:
        data = self._load_data()

        data["client_info"] = client_info.model_dump(
            mode="json",
            exclude_none=True
        )

        self._save_data(data)

    def _load_data(self) -> dict:
        if not self.file_path.exists():
            return {}

        with self.file_path.open(
            "r",
            encoding="utf-8"
        ) as file:
            return json.load(file)

    def _save_data(self, data: dict) -> None:
        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with self.file_path.open(
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                data,
                file,
                indent=2
            )