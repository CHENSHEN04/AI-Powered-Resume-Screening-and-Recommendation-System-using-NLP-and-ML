
"""
Stitch MCP Client
=================
Handles communication with the Stitch Model Context Protocol server.
This client enables the application to store and retrieve memory/context about candidates.
"""

import os
import httpx
import json
import logging
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StitchClient:
    """
    Client for interacting with a Stitch MCP Server (JSON-RPC over HTTP).
    """

    def __init__(self, server_url: Optional[str] = None):
        """
        Initialize the Stitch Client.
        
        Args:
            server_url: URL of the Stitch MCP server (e.g., "http://localhost:3000/mcp").
                        Defaults to STITCH_MCP_URL env var or localhost.
        """
        self.server_url = server_url or os.getenv("STITCH_MCP_URL", "http://localhost:3000/mcp")
        self.timeout = 10.0
        self.session_id = "default_session" # Can be updated per user

    def set_session(self, session_id: str):
        """Set the current session ID for context isolation."""
        self.session_id = session_id

    def check_connection(self) -> bool:
        """Ping the server to check connectivity."""
        try:
            # Assuming a health check or simple list_tools call
            response = httpx.post(
                self.server_url,
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
                timeout=2.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Stitch MCP connection failed: {e}")
            return False

    def store_memory(self, key: str, content: Any, metadata: Optional[Dict] = None) -> bool:
        """
        Store a piece of information in Stitch Memory.
        
        Args:
            key: Unique identifier or prompt for the memory.
            content: The data to store (text, JSON, etc.).
            metadata: Additional tags/info.
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "store_memory",
                "arguments": {
                    "key": key,
                    "content": content,
                    "metadata": metadata or {},
                    "session_id": self.session_id
                }
            },
            "id": 2
        }
        
        try:
            response = httpx.post(self.server_url, json=payload, timeout=self.timeout)
            if response.status_code == 200:
                result = response.json()
                if "error" in result:
                    logger.error(f"Stitch MCP Error: {result['error']}")
                    return False
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return False

    def retrieve_context(self, query: str) -> List[Dict]:
        """
        Retrieve relevant context based on a query.
        
        Args:
            query: The search query (e.g., "What is the candidate's experience?").
            
        Returns:
            List of relevant memory items.
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "search_memory",
                "arguments": {
                    "query": query,
                    "session_id": self.session_id
                }
            },
            "id": 3
        }
        
        try:
            response = httpx.post(self.server_url, json=payload, timeout=self.timeout)
            if response.status_code == 200:
                result = response.json()
                if "error" in result:
                    logger.error(f"Stitch MCP Error: {result['error']}")
                    return []
                
                # Adapt based on actual Stitch response structure
                # Assuming it returns a list of contents or objects
                return result.get("result", {}).get("content", []) 
            return []
        except Exception as e:
            logger.error(f"Failed to retrieve context: {e}")
            return []
            
    def list_memories(self) -> List[Dict]:
        """Debug method to list all memories for the session."""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "list_memories",
                "arguments": {
                    "session_id": self.session_id
                }
            },
            "id": 4
        }
        
        try:
            response = httpx.post(self.server_url, json=payload, timeout=self.timeout)
            if response.status_code == 200:
                return response.json().get("result", {}).get("content", [])
            return []
        except Exception as e:
            return []
