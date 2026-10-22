import asyncio
import threading
import webbrowser
import os
from pathlib import Path
from dotenv import load_dotenv

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
from backend.ai.integrations.oauth_storage import FileTokenStorage
import httpx2

from pydantic import AnyUrl

from mcp import Client
from mcp.client.auth import (
    AuthorizationCodeResult,
    OAuthClientProvider
)
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import (
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthToken
)

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")
TOKEN_FILE = os.environ["ATLASSIAN_TOKEN_FILE"]
ATLASSIAN_MCP_URL = os.environ["ATLASSIAN_MCP_URL"]

CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 3000
CALLBACK_URL = f"http://{CALLBACK_HOST}:{CALLBACK_PORT}/callback"


class InMemoryTokenStorage:
    def __init__(self):
        self.tokens = None
        self.client_info = None

    async def get_tokens(self):
        return self.tokens

    async def set_tokens(self, tokens: OAuthToken):
        print("OAuth tokens received.")
        self.tokens = tokens

    async def get_client_info(self):
        return self.client_info

    async def set_client_info(
        self,
        client_info: OAuthClientInformationFull
    ):
        print("OAuth client information received.")
        self.client_info = client_info


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    callback_result = None
    callback_event = threading.Event()

    def do_GET(self):
        parsed_url = urlparse(self.path)

        if parsed_url.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        params = parse_qs(parsed_url.query)

        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]
        iss = params.get("iss", [None])[0]

        if code is None:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing authorization code.")
            return

        OAuthCallbackHandler.callback_result = AuthorizationCodeResult(
            code=code,
            state=state,
            iss=iss
        )

        OAuthCallbackHandler.callback_event.set()

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        self.wfile.write(
            b"""
            <html>
                <body>
                    <h2>Authorization successful.</h2>
                    <p>You can close this browser tab and return to the terminal.</p>
                </body>
            </html>
            """
        )

    def log_message(self, format, *args):
        return


def start_callback_server():
    server = HTTPServer(
        (CALLBACK_HOST, CALLBACK_PORT),
        OAuthCallbackHandler
    )

    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True
    )

    thread.start()

    print(f"Callback server listening at {CALLBACK_URL}")

    return server


async def open_browser(authorization_url: str):
    print("\nOpening Atlassian authorization page...")

    webbrowser.open(authorization_url)


async def wait_for_callback():
    print("Waiting for Atlassian OAuth callback...")

    await asyncio.to_thread(
        OAuthCallbackHandler.callback_event.wait
    )

    print("OAuth callback received.")

    return OAuthCallbackHandler.callback_result


async def main():
    callback_server = start_callback_server()

    try:
        print("Creating OAuth provider...")

        oauth = OAuthClientProvider(
            server_url=ATLASSIAN_MCP_URL,
            client_metadata=OAuthClientMetadata(
                client_name="Northline Commerce Customer Support",
                redirect_uris=[
                    AnyUrl(CALLBACK_URL)
                ],
                grant_types=[
                    "authorization_code",
                    "refresh_token"
                ],
                response_types=[
                    "code"
                ]
            ),
            storage=FileTokenStorage(TOKEN_FILE),
            # storage=InMemoryTokenStorage(),
            redirect_handler=open_browser,
            callback_handler=wait_for_callback
        )

        print("Creating HTTP client...")

        async with httpx2.AsyncClient(
            auth=oauth,
            timeout=30.0
        ) as http_client:
            print("Creating MCP transport...")

            transport = streamable_http_client(
                ATLASSIAN_MCP_URL,
                http_client=http_client
            )

            print("Connecting to Atlassian MCP...")

            async with Client(transport) as client:
                print("MCP connected.")
                print("Requesting tools...")

                tools = await client.list_tools()

                print("\nConnected successfully.")
                print("\nAvailable tools:")

                for tool in tools.tools:
                    print(f"- {tool.name}")

    finally:
        callback_server.shutdown()
        callback_server.server_close()

        print("\nCallback server stopped.")


if __name__ == "__main__":
    asyncio.run(main())