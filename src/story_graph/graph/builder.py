import networkx as nx


def build_graph(registry, relationships, sentiments):

    G = nx.DiGraph()

    # add character nodes
    for key, name in registry.characters.items():
        G.add_node(key, label=name, aliases=list(registry.aliases[key]))

    # add relationship edges
    for r in relationships:

        G.add_edge(
            r["source"],
            r["target"],
            relation=r["relation"].value,
            relation_evidence=list(r["evidence"]),
        )

    # attach sentiments
    for s in sentiments:

        if G.has_edge(s["source"], s["target"]):

            edge = G[s["source"]][s["target"]]

            if "sentiments" not in edge:
                edge["sentiments"] = []

            edge["sentiments"].append({
                "type": s["sentiment"].value,
                "evidence": list(s["evidence"])
            })

    return G