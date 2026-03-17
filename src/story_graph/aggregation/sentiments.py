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
                    "evidence": [],
                    "positions": [],
                    "end_positions": []
                }
            edges[key]["evidence"].append((s.evidence, s.position))
            if s.position is not None:
                edges[key]["positions"].append(s.position)
            if s.end_position is not None:
                edges[key]["end_positions"].append(s.end_position)

    # Finalize: set position to min start, end_position to min end if any
    for key, data in edges.items():
        if data["positions"]:
            data["position"] = min(data["positions"])
        else:
            data["position"] = None
        if data["end_positions"]:
            data["end_position"] = min(data["end_positions"])  # Earliest end
        else:
            data["end_position"] = None
        # Remove temp lists
        del data["positions"]
        del data["end_positions"]

    return list(edges.values())