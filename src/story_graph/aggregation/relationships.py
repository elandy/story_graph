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
                    "evidence": []
                }
            edges[key]["evidence"].append((r.evidence, r.position))

    return list(edges.values())