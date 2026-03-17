from story_graph.aggregation.character_registry import CharacterRegistry


def aggregate_relationships(results, registry: CharacterRegistry):

    edges = {}

    for result in results:

        for r in result.relationships:

            source = registry.resolve(r.source)
            target = registry.resolve(r.target)

            key = (source, target, r.relation)

            if key not in edges:
                edges[key] = {
                    "source": source,
                    "target": target,
                    "relation": r.relation,
                    "evidence": [],
                    "positions": [],
                    "end_positions": []
                }
            edges[key]["evidence"].append((r.evidence, r.position))
            if r.position is not None:
                edges[key]["positions"].append(r.position)
            if r.end_position is not None:
                edges[key]["end_positions"].append(r.end_position)

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