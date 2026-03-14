from story_graph.aggregation.character_registry import CharacterRegistry


def aggregate_sentiments(results, registry: CharacterRegistry):

    edges = {}

    for result in results:

        for s in result.sentiments:

            source = registry.resolve(s.source)
            target = registry.resolve(s.target)

            key = (source, target, s.sentiment)

            if key not in edges:
                edges[key] = {
                    "source": source,
                    "target": target,
                    "sentiment": s.sentiment,
                    "evidence": []
                }
            edges[key]["evidence"].append((s.evidence, s.position))

    return list(edges.values())