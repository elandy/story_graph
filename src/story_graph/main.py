from dotenv import load_dotenv
load_dotenv()

from story_graph.chunking.splitter import split_paragraphs, chunk_paragraphs
from story_graph.extraction.checkpoint import default_checkpoint_path
from story_graph.extraction.pipeline import process_chunks
from story_graph.filtering.character_filter import has_character_interaction
from story_graph.ingest.loader import load_book
from story_graph.aggregation.pipeline import aggregate
from story_graph.graph.builder import build_graph
from story_graph.graph.debug import print_graph
from story_graph.graph.visualize import visualize_graph

import asyncio
import argparse
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Story graph pipeline")

    parser.add_argument("book", type=str, help="Path to the book file")

    parser.add_argument("--apply-nlp-filter", action="store_true",
                        help="Filter chunks using NLP character interaction")
    parser.add_argument("--max-chunks", type=int, default=0,
                        help="Maximum number of chunks to process")
    parser.add_argument("--debug-prints", action="store_true",
                        help="Enable verbose debug prints")
    parser.add_argument("--debug-json", action="store_true",
                        help="Dump relationships JSON to disk")
    parser.add_argument("--checkpoint-file", type=str, default="",
                        help="Path to the extraction checkpoint JSON file")
    parser.add_argument("--reset-checkpoint", action="store_true",
                        help="Delete any saved extraction checkpoint before running")

    return parser.parse_args()


async def main():
    args = parse_args()

    text = load_book(args.book)

    APPLY_NLP_FILTER = args.apply_nlp_filter
    MAX_CHUNKS = args.max_chunks
    DEBUG_PRINTS = args.debug_prints
    DEBUG_JSON = args.debug_json

    paragraphs = split_paragraphs(text)
    print("Paragraphs:", len(paragraphs))

    # --- Chunking ---
    chunks = chunk_paragraphs(paragraphs)
    total_chunks_raw = len(chunks)

    # --- Optional filtering ---
    if APPLY_NLP_FILTER:
        filtered_chunks = [c for c in chunks if has_character_interaction(c['text'])]
        print("Filtered chunks without interaction:", total_chunks_raw - len(filtered_chunks))
        chunks = filtered_chunks

    total_chunks_available = len(chunks)
    effective_chunks = min(MAX_CHUNKS, total_chunks_available) if MAX_CHUNKS else total_chunks_available

    print(f"Total chunks available: {total_chunks_available}")
    print(f"Chunks to process: {effective_chunks}")

    # --- ETA based on actual processed chunks ---
    sleeps = (effective_chunks - 1) // 5 if effective_chunks > 0 else 0
    estimated_time_seconds = sleeps * 60 + effective_chunks * 10
    estimated_time_minutes = estimated_time_seconds / 60
    print(f"E.T.A.: {estimated_time_minutes:.1f} minutes.")

    # --- Processing ---
    checkpoint_path = (
        Path(args.checkpoint_file)
        if args.checkpoint_file
        else default_checkpoint_path(args.book, APPLY_NLP_FILTER)
    )
    print(f"Extraction checkpoint: {checkpoint_path}")

    results = await process_chunks(
        chunks[:effective_chunks],
        checkpoint_path=checkpoint_path,
        reset_checkpoint=args.reset_checkpoint,
    )

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
        import json
        with open('debug_relationships.json', 'w', encoding='utf-8') as f:
            json.dump(relationships, f, ensure_ascii=False, indent=2)

    G = build_graph(registry, relationships, sentiments)
    visualize_graph(G, total_chunks=effective_chunks)

    if DEBUG_PRINTS:
        print_graph(G)


if __name__ == "__main__":
    asyncio.run(main())
