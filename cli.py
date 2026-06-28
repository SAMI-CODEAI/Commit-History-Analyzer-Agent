import argparse
import asyncio
import sys
from config import Config
from agent import HistoryAnalyzerAgent

async def async_main():
    parser = argparse.ArgumentParser(
        description="Commit History Analyzer Agent: Investigate changes in Git repositories using GitHub MCP and OpenAI."
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="GitHub repository path in 'owner/repo' format (e.g. octocat/Hello-World)"
    )
    parser.add_argument(
        "--query",
        required=True,
        help="The query or question to investigate (e.g. 'Why did token verification fail?')"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="OpenAI completion model to use (default: gpt-4o)"
    )
    
    args = parser.parse_args()
    
    # Validate environment variables before running
    try:
        Config.validate()
    except ValueError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)
        
    agent = HistoryAnalyzerAgent(repo=args.repo)
    
    try:
        report = await agent.run(query=args.query, model=args.model)
        print("\n" + "="*50)
        print("FINAL ANALYSIS REPORT")
        print("="*50)
        print(report)
        print("="*50 + "\n")
    except Exception as e:
        print(f"Error during agent run: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    # Set Windows Proactor Event Loop Policy to support subprocess communication
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nAgent analysis interrupted.")
        sys.exit(0)

if __name__ == "__main__":
    main()
