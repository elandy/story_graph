import networkx as nx


def build_graph(registry, relationships, sentiments):

    G = nx.MultiDiGraph()

    # add character nodes
    for key, name in registry.characters.items():
        G.add_node(key, label=name, aliases=list(registry.aliases[key]))

    # add relationship edges (one edge per (source, target, relation); evidence: list of {text, position})
    for r in relationships:
        relation_evidence = [
            {"text": text, "position": pos}
            for text, pos in r["evidence"]
        ]
        relation_key = r["relation"].value
        G.add_edge(
            r["source"],
            r["target"],
            relation_key,
            relation=relation_key,
            relation_evidence=relation_evidence,
        )

    # attach sentiments to every edge between (source, target)
    for s in sentiments:
        if not G.has_edge(s["source"], s["target"]):
            continue
        sentiment_payload = {
            "type": s["sentiment"].value,
            "evidence": [
                {"text": text, "position": pos}
                for text, pos in s["evidence"]
            ],
        }
        for _key, edge in G[s["source"]][s["target"]].items():
            if "sentiments" not in edge:
                edge["sentiments"] = []
            edge["sentiments"].append(sentiment_payload)

    return G