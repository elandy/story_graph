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
    text = load_book("data/books/hp.txt")

    paragraphs = split_paragraphs(text)

    chunks = chunk_paragraphs(paragraphs)
    filtered_chunks = [c for c in chunks if has_character_interaction(c['text'])]

    print("Paragraphs:", len(paragraphs))
    print("Chunks:", len(chunks))
    print("Filtered chunks:", len(filtered_chunks))

    results = await process_chunks(filtered_chunks[0:5])
    total_characters = sum(len(r.characters) for r in results)
    total_relationships = sum(len(r.relationships) for r in results)
    total_sentiments = sum(len(r.sentiments) for r in results)

    print("\nExtraction stats")
    print("Characters:", total_characters)
    print("Relationships:", total_relationships)
    print("Sentiments:", total_sentiments)

    for i, result in enumerate(results):
        print(f"\nChunk {i} relationships:")
        for r in result.relationships:
            print(f"  {r}")

    registry, relationships, sentiments = aggregate(results)

    # Write aggregate output to disk for inspection (avoids relying on stdout)
    import json
    with open('debug_relationships.json', 'w', encoding='utf-8') as f:
        json.dump(relationships, f, ensure_ascii=False, indent=2)

    G = build_graph(registry, relationships, sentiments)
    visualize_graph(G, total_chunks=len(filtered_chunks))
    print_graph(G)
    # print("\n--- Aggregated ---")
    #
    # print("Unique characters:", len(registry.characters))
    # print("Characters:", registry.characters)
    # print("Relationships:", len(relationships))
    # for r in relationships:
    #     print(f"{r['source']} -> {r['target']} : {r['relation']}")
    #
    #     for ev in r["evidence"]:
    #         print("  -", ev)
    #
    # print("Sentiments:", len(sentiments))
    # for s in sentiments:
    #     print(f"{s['source']} -> {s['target']} : {s['sentiment']}")
    #
    #     for ev in s["evidence"]:
    #         print("  -", ev)

if __name__ == "__main__":
    asyncio.run(main())
