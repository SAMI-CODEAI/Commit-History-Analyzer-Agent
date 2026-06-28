import unittest
import os
from unittest.mock import patch, MagicMock
from config import Config
from mcp_client import GitHubMCPClient
from agent import HistoryAnalyzerAgent

class TestAgentConfig(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_config_validation_fails_when_empty(self):
        # Temporarily clear Config properties
        orig_openai = Config.OPENAI_API_KEY
        orig_github = Config.GITHUB_TOKEN
        
        Config.OPENAI_API_KEY = None
        Config.GITHUB_TOKEN = None
        try:
            with self.assertRaises(ValueError):
                Config.validate()
        finally:
            Config.OPENAI_API_KEY = orig_openai
            Config.GITHUB_TOKEN = orig_github
            
    def test_config_validation_passes_when_present(self):
        orig_openai = Config.OPENAI_API_KEY
        orig_github = Config.GITHUB_TOKEN
        
        Config.OPENAI_API_KEY = "test_openai_key"
        Config.GITHUB_TOKEN = "test_github_token"
        try:
            Config.validate()
        except ValueError:
            self.fail("Config.validate() raised ValueError unexpectedly!")
        finally:
            Config.OPENAI_API_KEY = orig_openai
            Config.GITHUB_TOKEN = orig_github

class TestGitHubMCPClientMapping(unittest.TestCase):
    def test_mcp_client_init(self):
        client = GitHubMCPClient(github_token="dummy_token")
        self.assertEqual(client.github_token, "dummy_token")
        self.assertIn("GITHUB_PERSONAL_ACCESS_TOKEN", client.server_params.env)

class TestHistoryAnalyzerAgent(unittest.TestCase):
    def test_agent_init(self):
        agent = HistoryAnalyzerAgent(repo="octocat/Hello-World")
        self.assertEqual(agent.owner, "octocat")
        self.assertEqual(agent.repo_name, "Hello-World")

if __name__ == "__main__":
    unittest.main()
