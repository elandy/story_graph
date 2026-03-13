from story_graph.aggregation.normalization import normalize_name


def aggregate_relationships(results):

    edges = {}

    for result in results:

        for r in result.relationships:

            source = normalize_name(r.source)
            target = normalize_name(r.target)

            key = (source, target, r.relation)

            if key not in edges:
                edges[key] = {
                    "source": source,
                    "target": target,
                    "relation": r.relation,
                    "evidence": set()
                }
            edges[key]["evidence"].add(r.evidence)

    return list(edges.values())