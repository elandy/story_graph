from story_graph.aggregation.character_registry import CharacterRegistry


def _select_end_position(start_position, end_positions):
    normalized_end_positions = []

    for end_position in end_positions:
        if start_position is None:
            normalized_end_positions.append(end_position)
            continue

        if end_position == start_position:
            normalized_end_positions.append(start_position + 1)
        elif end_position > start_position:
            normalized_end_positions.append(end_position)

    if normalized_end_positions:
        return min(normalized_end_positions)

    return None


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

    # Finalize the active window using the earliest known start and end.
    for key, data in edges.items():
        if data["positions"]:
            data["position"] = min(data["positions"])
        else:
            data["position"] = None
        data["end_position"] = _select_end_position(
            data["position"],
            data["end_positions"],
        )
        # Remove temp lists
        del data["positions"]
        del data["end_positions"]

    return list(edges.values())
