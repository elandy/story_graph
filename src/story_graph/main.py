from story_graph.graph.debug import print_graph
from story_graph.pipeline import StoryGraphRunConfig, run_story_graph_pipeline_from_file

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
    checkpoint_path = args.checkpoint_file or None
    result = await run_story_graph_pipeline_from_file(
        args.book,
        StoryGraphRunConfig(
            apply_nlp_filter=args.apply_nlp_filter,
            max_chunks=args.max_chunks,
            debug_json=args.debug_json,
            checkpoint_path=Path(checkpoint_path) if checkpoint_path else None,
            reset_checkpoint=args.reset_checkpoint,
            confirm_extraction=None,
            progress_callback=_print_progress,
        ),
    )

    print("\nExtraction stats")
    print("Characters:", result.total_characters)
    print("Relationships:", result.total_relationships)
    print("Sentiments:", result.total_sentiments)

    if args.debug_prints:
        for i, chunk_result in enumerate(result.extraction_results):
            print(f"\nChunk {i} relationships:")
            for relationship in chunk_result.relationships:
                print(f"  {relationship}")

        print_graph(result.graph)


def _print_progress(update):
    if update.message:
        print(update.message)


if __name__ == "__main__":
    asyncio.run(main())
