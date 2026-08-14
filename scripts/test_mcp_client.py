import asyncio
from src.mcp_client import get_mcp_client

async def test_mcp():
    print("Testing connection to mcp-brasil...")
    async with get_mcp_client() as session:
        tools = await session.list_tools()
        print(f"Server is up! Available tools: {len(tools.tools)}")
        print("First 5 tools:")
        for tool in tools.tools[:5]:
            print(f" - {tool.name}")
            
if __name__ == "__main__":
    asyncio.run(test_mcp())
