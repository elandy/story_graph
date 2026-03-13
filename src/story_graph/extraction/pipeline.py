from story_graph.extraction.extractor import extract_relationships


async def process_chunks(chunks: list[str]):
    results = []

    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{len(chunks)}")

        result = await extract_relationships(chunk)

        results.append(result)

    return results