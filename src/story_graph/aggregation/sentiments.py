from story_graph.aggregation.normalization import normalize_name


def aggregate_sentiments(results):

    edges = {}

    for result in results:

        for s in result.sentiments:

            source = normalize_name(s.source)
            target = normalize_name(s.target)

            key = (source, target, s.sentiment)

            if key not in edges:
                edges[key] = {
                    "source": source,
                    "target": target,
                    "sentiment": s.sentiment,
                    "evidence": set()
                }
            edges[key]["evidence"].add(s.evidence)

    return list(edges.values())