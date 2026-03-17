import asyncio
from story_graph.extraction.extractor import extract_relationships


async def process_chunks(chunks: list[dict]):

    proceed = input("Proceed with extraction? (y/n): ")
    if proceed.lower() != 'y':
        print("Extraction cancelled.")
        return []

    results = []

    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{len(chunks)}")

        result = await extract_relationships(text=chunk['text'])
        
        # Rate limiting: sleep after every 5 requests
        if (i + 1) % 5 == 0 and i + 1 < len(chunks):
            print("Rate limit: sleeping 60 seconds after 5 requests")
            await asyncio.sleep(60)
        
        # Split chunk back into paragraphs to find positions
        paras_in_chunk = chunk['text'].split('\n\n')
        
        for r in result.relationships:
            for j, para in enumerate(paras_in_chunk):
                if r.evidence in para:
                    r.position = chunk['start_index'] + j
                    break
            else:
                # Fallback if evidence not found (shouldn't happen)
                r.position = chunk['start_index']

        for s in result.sentiments:
            for j, para in enumerate(paras_in_chunk):
                if s.evidence in para:
                    s.position = chunk['start_index'] + j
                    break
            else:
                s.position = chunk['start_index']

        results.append(result)

    return results