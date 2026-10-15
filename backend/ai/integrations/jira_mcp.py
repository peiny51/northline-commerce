"""Optional Jira escalation through Atlassian's MCP endpoint after agent approval.

Credentials and OAuth setup are intentionally external to the customer web app.
A missing MCP connection is reported as a failure, not a fake ticket.
"""
import asyncio
import json
import os


def configured():
    return all(os.getenv(x) for x in ('ATLASSIAN_MCP_URL', 'ATLASSIAN_CLOUD_ID', 'JIRA_PROJECT_KEY'))


async def _create_issue(summary, description):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    # An MCP service reachable via a trusted, pre-authenticated endpoint.
    # For OAuth-enabled Atlassian MCP, deploy a token-handling gateway here.
    async with streamablehttp_client(os.environ['ATLASSIAN_MCP_URL']) as (reader, writer, _):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            result = await session.call_tool('createJiraIssue', {
                'cloudId': os.environ['ATLASSIAN_CLOUD_ID'],
                'projectKey': os.environ['JIRA_PROJECT_KEY'],
                'issueType': 'Task', 'summary': summary[:255], 'description': description,
                'labels': ['customer-escalation', 'human-approved']})
            if result.isError:
                raise RuntimeError('Jira MCP tool reported an error')
            for item in result.content:
                if getattr(item, 'type', '') == 'text':
                    payload = json.loads(item.text)
                    data = payload.get('data', payload)
                    if data.get('key'):
                        return data['key']
    raise RuntimeError('No issue key was returned from Jira MCP')


def create_jira_escalation(summary, description):
    if not configured():
        raise RuntimeError('Jira MCP credentials not configured')
    return asyncio.run(_create_issue(summary, description))
