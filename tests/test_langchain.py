import asyncio
import os

from src.story_graph.extraction.extractor import extract_relationships
from dotenv import load_dotenv

load_dotenv()

text = "Alice greeted Bob at the market. Bob, who was her neighbor, waved back. 'I will always look after you,' said Alice."

async def run():
    res = await extract_relationships(text, api_key=os.getenv("GOOGLE_API_KEY"))
    print(res.model_dump_json(indent=2, ensure_ascii=False))

asyncio.run(run())
