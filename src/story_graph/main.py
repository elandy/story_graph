from dotenv import load_dotenv
load_dotenv()

from story_graph.chunking.splitter import split_paragraphs, chunk_paragraphs
from story_graph.extraction.pipeline import process_chunks
from story_graph.filtering.character_filter import has_character_interaction
from story_graph.ingest.loader import load_book
from story_graph.aggregation.pipeline import aggregate
from story_graph.graph.builder import build_graph
from story_graph.graph.debug import print_graph
from story_graph.graph.visualize import visualize_graph


import asyncio

async def main():
    text = load_book("data/books/quantico.txt")
    APPLY_NLP_FILTER = False
    MAX_CHUNKS = 5
    DEBUG_PRINTS = False
    DEBUG_JSON = False

    paragraphs = split_paragraphs(text)
    print("Paragraphs:", len(paragraphs))
    chunks = chunk_paragraphs(paragraphs)
    total_chunks = len(chunks)
    print(f"Total chunks: {total_chunks}")
    if APPLY_NLP_FILTER:
        chunks = [c for c in chunks if has_character_interaction(c['text'])]
        print("Filtered chunks without interaction:", total_chunks - len(chunks))
    sleeps = (total_chunks - 1) // 5
    # Rough estimate: 60s per sleep + 10s per request
    estimated_time_seconds = sleeps * 60 + total_chunks * 10
    estimated_time_minutes = estimated_time_seconds / 60
    print(f"E.T.A.: {estimated_time_minutes:.1f} minutes.")

    results = await process_chunks(chunks[0:MAX_CHUNKS])
    total_characters = sum(len(r.characters) for r in results)
    total_relationships = sum(len(r.relationships) for r in results)
    total_sentiments = sum(len(r.sentiments) for r in results)

    print("\nExtraction stats")
    print("Characters:", total_characters)
    print("Relationships:", total_relationships)
    print("Sentiments:", total_sentiments)

    if DEBUG_PRINTS:
        for i, result in enumerate(results):
            print(f"\nChunk {i} relationships:")
            for r in result.relationships:
                print(f"  {r}")

    registry, relationships, sentiments = aggregate(results)

    if DEBUG_JSON:
        # Write aggregate output to disk for inspection (avoids relying on stdout)
        import json
        with open('debug_relationships.json', 'w', encoding='utf-8') as f:
            json.dump(relationships, f, ensure_ascii=False, indent=2)

    G = build_graph(registry, relationships, sentiments)
    visualize_graph(G, total_chunks=MAX_CHUNKS)
    if DEBUG_PRINTS:
        print_graph(G)


if __name__ == "__main__":
    asyncio.run(main())
