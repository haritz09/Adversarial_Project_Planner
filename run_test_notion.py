import asyncio
import os
from pathlib import Path

# dotenv support
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

# Load .env if present
dot_env = Path('.') / '.env'
if load_dotenv:
    load_dotenv(dotenv_path=dot_env)
else:
    if dot_env.exists():
        for line in dot_env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"\''))

# Prefer NOTION_CONNECTION_TOKEN but fall back to NOTION_TOKEN
NOTION_TOKEN = os.getenv('NOTION_CONNECTION_TOKEN')
if not NOTION_TOKEN:
    raise RuntimeError('NOTION token not found in environment (.env must define NOTION_CONNECTION_TOKEN or NOTION_TOKEN)')

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command='npx',
    args=['-y', '@notionhq/notion-mcp-server'],
    env={'NOTION_TOKEN': NOTION_TOKEN},
)

# Parent page id provided by the user (from the Notion link)
PARENT_PAGE_ID = os.gentenv('NOTION_PARENT_PAGE_ID')

async def test_notion():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Tools disponibles:")
            for tool in tools.tools:
                print(f"  - {tool.name}")

async def create_test_page():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # Crear una página como hija de la página existente
            payload = {
                "parent": {"type": "page_id", "page_id": PARENT_PAGE_ID},
                "properties": {
                    "title": [{"text": {"content": "🧪 Test page - Adversarial Planner (child)"}}]
                },
                "children": [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"type": "text", "text": {"content": "Creada por MCP desde run_notion.py"}}]}
                    }
                ]
            }

            result = await session.call_tool("API-post-page", payload)
            print("API-post-page result:", result)

            # Intentar extraer el id de la página creada y recuperarla
            new_page_id = None
            try:
                import json
                # El resultado del MCP suele venir en result.content[0].text como JSON string
                if hasattr(result, 'content') and len(result.content) > 0:
                    data = json.loads(result.content[0].text)
                    new_page_id = data.get('id')
            except Exception as e:
                print(f"Error parseando respuesta: {e}")
                new_page_id = None

            if new_page_id:
                retrieved = await session.call_tool("API-retrieve-a-page", {"page_id": new_page_id})
                print("Página recuperada:", retrieved)
            else:
                print("No se pudo determinar el id de la página creada desde la respuesta:", result)

async def main():
    await test_notion()
    await create_test_page()

if __name__ == '__main__':
    asyncio.run(main())
