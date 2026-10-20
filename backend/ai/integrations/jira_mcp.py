"""Create a staff-follow-up Jira ticket through a trusted Atlassian MCP endpoint.

Creating a ticket requires no manager approval; any refund or cancellation is left to staff.
Credentials and OAuth are managed outside the customer-facing Django app.
"""
import asyncio
import json
import os


def configured():
    return all(os.getenv(x) for x in ("ATLASSIAN_MCP_URL", "ATLASSIAN_CLOUD_ID", "JIRA_PROJECT_KEY"))


async def _create_issue(summary, description):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    # Requires an authenticated MCP endpoint or a separately deployed OAuth gateway.
    async with streamablehttp_client(os.environ["ATLASSIAN_MCP_URL"]) as (reader, writer, _):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            result = await session.call_tool("createJiraIssue", {
                "cloudId": os.environ["ATLASSIAN_CLOUD_ID"],
                "projectKey": os.environ["JIRA_PROJECT_KEY"],
                "issueType": "Task",
                "summary": summary[:255],
                "description": description,
                "labels": ["customer-escalation", "ai-triaged"],
            })
            if result.isError:
                raise RuntimeError("Jira MCP tool reported an error")
            for item in result.content:
                if getattr(item, "type", "") == "text":
                    payload = json.loads(item.text)
                    data = payload.get("data", payload)
                    if data.get("key"):
                        return data["key"]
    raise RuntimeError("No issue key was returned from Jira MCP")


def create_jira_escalation(summary, description):
    if not configured():
        raise RuntimeError("Jira MCP credentials not configured")
    return asyncio.run(_create_issue(summary, description))
