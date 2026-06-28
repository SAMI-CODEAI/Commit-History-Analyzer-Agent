import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class GitHubMCPClient:
    def __init__(self, github_token):
        self.github_token = github_token
        # Use npx.cmd on Windows to avoid FileNotFoundError
        command = "npx.cmd" if sys.platform == "win32" else "npx"
        
        env = {**os.environ}
        if github_token:
            env["GITHUB_PERSONAL_ACCESS_TOKEN"] = github_token
            env["GITHUB_TOKEN"] = github_token

        self.server_params = StdioServerParameters(
            command=command,
            args=["-y", "@modelcontextprotocol/server-github"],
            env=env
        )
        self.session = None
        self._client_context = None

    async def connect(self):
        """Connect to the GitHub MCP server."""
        self._client_context = stdio_client(self.server_params)
        read_stream, write_stream = await self._client_context.__aenter__()
        self.session = ClientSession(read_stream, write_stream)
        await self.session.__aenter__()
        await self.session.initialize()

    async def list_tools(self):
        """Retrieve tools from GitHub MCP server and map to OpenAI format."""
        if not self.session:
            raise RuntimeError("Client not connected. Call connect() first.")
        
        tools_result = await self.session.list_tools()
        
        openai_tools = []
        for tool in tools_result.tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            })
        return openai_tools, tools_result.tools

    async def call_tool(self, tool_name, arguments):
        """Execute a tool on the GitHub MCP server and return output as a string."""
        if not self.session:
            raise RuntimeError("Client not connected.")
        
        try:
            result = await self.session.call_tool(tool_name, arguments)
            
            # Extract content from result
            texts = []
            for item in result.content:
                if hasattr(item, "text"):
                    texts.append(item.text)
                elif isinstance(item, dict) and "text" in item:
                    texts.append(item["text"])
                else:
                    texts.append(str(item))
            return "\n".join(texts)
        except Exception as e:
            return f"Error executing tool {tool_name}: {str(e)}"

    async def disconnect(self):
        """Clean up streams and exit subprocess."""
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except Exception:
                pass
            self.session = None
        if self._client_context:
            try:
                await self._client_context.__aexit__(None, None, None)
            except Exception:
                pass
            self._client_context = None
