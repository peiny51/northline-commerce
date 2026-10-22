"""Create Jira support tickets through Atlassian MCP with OAuth."""

import asyncio
import json
import os

import httpx2
from dotenv import load_dotenv
from mcp import Client
from mcp.client.auth import OAuthClientProvider
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientMetadata
from pydantic import AnyUrl

from backend.ai.integrations.oauth_storage import FileTokenStorage


load_dotenv()

CALLBACK_URL = "http://127.0.0.1:3000/callback"


def configured():
    return all(os.getenv(key) for key in (
        "ATLASSIAN_MCP_URL",
        "ATLASSIAN_CLOUD_ID",
        "JIRA_PROJECT_KEY",
        "ATLASSIAN_TOKEN_FILE",
    ))


async def _reauthorization_required(authorization_url: str):
    raise RuntimeError(
        "Atlassian OAuth authorization is required. "
        "Run the Jira OAuth setup script as an administrator."
    )


async def _callback_not_available():
    raise RuntimeError(
        "Interactive Atlassian OAuth callback is disabled "
        "during normal application requests."
    )


def _build_oauth_provider():
    return OAuthClientProvider(
        server_url=os.environ["ATLASSIAN_MCP_URL"],
        client_metadata=OAuthClientMetadata(
            client_name="Northline Commerce Customer Support",
            redirect_uris=[AnyUrl(CALLBACK_URL)],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
        ),
        storage=FileTokenStorage(os.environ["ATLASSIAN_TOKEN_FILE"]),
        redirect_handler=_reauthorization_required,
        callback_handler=_callback_not_available,
    )


async def _create_issue(summary, description):
    oauth = _build_oauth_provider()

    # Reuse saved OAuth credentials without interactive customer authorization.
    async with httpx2.AsyncClient(
        auth=oauth,
        timeout=30.0,
    ) as http_client:
        transport = streamable_http_client(
            os.environ["ATLASSIAN_MCP_URL"],
            http_client=http_client,
        )

        async with Client(transport) as client:
            result = await client.call_tool(
                "createJiraIssue",
                {
                    "cloudId": os.environ["ATLASSIAN_CLOUD_ID"],
                    "projectKey": os.environ["JIRA_PROJECT_KEY"],
                    "issueType": "Task",
                    "summary": summary[:255],
                    "description": description,
                    "labels": ["customer-escalation", "ai-triaged"],
                },
            )

            if result.is_error:
                raise RuntimeError("Jira MCP tool reported an error")

            for item in result.content:
                if item.type != "text":
                    continue

                try:
                    payload = json.loads(item.text)
                except json.JSONDecodeError:
                    continue

                data = payload.get("data", payload)

                if data.get("key"):
                    return data["key"]

    raise RuntimeError("No Jira issue key returned from MCP")


def create_jira_escalation(summary, description):
    if not configured():
        raise RuntimeError("Jira MCP credentials not configured")

    return asyncio.run(_create_issue(summary, description))
