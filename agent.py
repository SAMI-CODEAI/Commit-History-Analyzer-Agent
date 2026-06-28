import os
import json
import logging
from openai import AsyncOpenAI
from config import Config
from mcp_client import GitHubMCPClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI software engineer specializing in Git history investigation.
Your job is to determine why a behavior changed in a GitHub repository.
You have access to a GitHub MCP server that can search repositories, inspect commits, browse code, and retrieve GitHub metadata.

Never guess.
Always investigate using the available tools.
When evidence is insufficient, explicitly say so.
Never invent commit hashes.
Never fabricate commit messages.
Always cite evidence retrieved from the repository.

Objective:
Given a user query, identify:
1. The commit(s) responsible.
2. The files modified.
3. The reasoning behind the change.
4. Whether the change was intentional.
5. Whether another commit later fixed it.

Investigation Strategy:
You MUST investigate in this order:
Step 1: Extract technical keywords (e.g. Authentication, Login, JWT, OAuth, Token, Bearer, Cookie, Session, Middleware, local file names or concepts in user's query).
Step 2: Search repository history using GitHub MCP tools to search commit messages, PR titles, issue references, branches, and release notes for those keywords. Prioritize recent commits first.
Step 3: Inspect candidate commits. For every likely commit, retrieve: commit message, author, date, changed files, patch/diff, and associated pull request if available.
Step 4: Analyze the code diff. Determine: what changed, was code deleted, were env variables renamed, did API routes change, were middleware rules updated, did dependency versions change, did secrets or libraries change?
Step 5: Search nearby commits. Investigate commits immediately before and after. Many regressions are introduced in one commit and fixed two commits later.
Step 6: Look for related issues or PRs. If the commit references a commit, pull request, or issue (e.g., "Fixes #53", "Closes #19", "PR #82"), retrieve that information.
Step 7: Explain findings in a concise engineering report.

Additional Behaviors:
- If the user asks "Who introduced this bug?", identify the commit author without assigning blame. Phrase it neutrally, e.g., "The change was introduced in commit <hash> authored by <name>."
- If the user asks "When did this feature disappear?", search commit history first, then inspect diffs around the relevant period.
- If multiple commits are plausible, compare them and explain why one is more likely to be the root cause.
- If the evidence is inconclusive, present the competing hypotheses and explain what additional repository info would resolve it.

Output Format:
Your final response MUST be formatted EXACTLY like this:

Summary
<One paragraph explaining what happened.>

Root Cause
<Explain exactly why behavior changed.>

Evidence
Commit: <hash>
Author: <author name>
Date: <commit date>
Changed Files: <comma-separated list of affected files>
Commit Message: "<commit message>"
Related PR: <PR number/link if available, or 'None'>

Code Changes
<Summarize important modifications, including lines removed/added if critical.>

Confidence
<High / Medium / Low> - <Explain why.>

If No Root Cause Found:
If after running your search you cannot find the root cause, your final answer MUST be exactly:
"I searched commits and related history but did not find evidence connecting the reported issue to a specific commit."
Do not speculate.
"""

class HistoryAnalyzerAgent:
    def __init__(self, repo: str):
        self.repo = repo
        if "/" in repo:
            self.owner, self.repo_name = repo.split("/", 1)
        else:
            self.owner = ""
            self.repo_name = repo

        # Build the OpenAI-compatible client for either OpenAI or Ollama
        if Config.LLM_BACKEND == "ollama":
            self.openai_client = AsyncOpenAI(
                api_key="ollama",          # Ollama doesn't validate this; non-empty required
                base_url=Config.OLLAMA_BASE_URL
            )
            print(f"[*] LLM backend: Ollama ({Config.OLLAMA_BASE_URL}) | Model: {Config.DEFAULT_MODEL}")
        else:
            self.openai_client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
            print(f"[*] LLM backend: OpenAI | Model: {Config.DEFAULT_MODEL}")

        self.mcp_client = GitHubMCPClient(github_token=Config.GITHUB_TOKEN)
        
    async def run(self, query: str, model: str = None) -> str:
        if not model:
            model = Config.DEFAULT_MODEL
            
        print("[*] Connecting to GitHub MCP Server...")
        await self.mcp_client.connect()
        
        try:
            print("[*] Retrieving tools list...")
            openai_tools, raw_tools = await self.mcp_client.list_tools()
            
            # Map of tool names to their raw definitions to inspect parameter requirements
            tool_definitions = {t.name: t for t in raw_tools}
            
            # Formulate initial system and user messages
            # Instruct the agent about target repo and query
            print(f"[*] Starting history analysis for repo '{self.repo}'...")
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"We are investigating the repository: {self.repo}\n"
                        f"Target Owner: {self.owner}\n"
                        f"Target Repository Name: {self.repo_name}\n"
                        f"User Query: {query}\n\n"
                        f"Remember, when invoking GitHub tools, make sure to specify the 'owner' and 'repo' parameters. "
                        f"For this repository, the owner is '{self.owner}' and repo is '{self.repo_name}'.\n"
                        f"Start by extracting keywords and searching commits."
                    )
                }
            ]
            
            max_iterations = 30
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                
                # Fetch completion from OpenAI
                response = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=openai_tools if openai_tools else None,
                    tool_choice="auto" if openai_tools else None,
                    temperature=0.0
                )
                
                choice = response.choices[0]
                message = choice.message
                
                # Format assistant message for continuation
                msg_dict = {"role": "assistant", "content": message.content}
                if message.tool_calls:
                    msg_dict["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in message.tool_calls
                    ]
                messages.append(msg_dict)
                
                # Log any textual thoughts/status from assistant
                if message.content:
                    print(f"\n[Agent]: {message.content}\n")
                
                # If no tool calls, this is the final answer!
                if not message.tool_calls:
                    return message.content
                
                # Execute tool calls sequentially
                for tool_call in message.tool_calls:
                    name = tool_call.function.name
                    args_str = tool_call.function.arguments
                    try:
                        args = json.loads(args_str)
                    except Exception:
                        args = {}
                    
                    # Auto-inject owner and repo if missing but required by tool schema
                    if name in tool_definitions:
                        required_params = tool_definitions[name].inputSchema.get("required", [])
                        properties = tool_definitions[name].inputSchema.get("properties", {})
                        
                        if "owner" in properties and ("owner" not in args or not args["owner"]):
                            args["owner"] = self.owner
                        if "repo" in properties and ("repo" not in args or not args["repo"]):
                            args["repo"] = self.repo_name
                        if "repository" in properties and ("repository" not in args or not args["repository"]):
                            args["repository"] = self.repo
                    
                    print(f"[*] Calling GitHub tool: {name}({json.dumps(args)})")
                    tool_result = await self.mcp_client.call_tool(name, args)
                    
                    snippet = tool_result[:400].replace("\n", " ")
                    if len(tool_result) > 400:
                        snippet += "..."
                    print(f"[+] Result snippet: {snippet}")
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": tool_result
                    })
            
            return "Error: Maximum iteration limit reached without generating a final response."
            
        finally:
            print("[*] Disconnecting from GitHub MCP Server...")
            await self.mcp_client.disconnect()
