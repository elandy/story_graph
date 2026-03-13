from pyvis.network import Network


def visualize_graph(G, output_file="story_graph.html"):

    net = Network(
        height="800px",
        width="100%",
        directed=True,
        bgcolor="#222222",
        font_color="white",
    )
    net.set_options("""
    {
      "nodes": {
        "font": {
          "size": 18
        }
      },
      "edges": {
        "font": {
          "size": 12,
          "align": "middle"
        }
      },
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -50,
          "centralGravity": 0.01,
          "springLength": 150,
          "springConstant": 0.08
        },
        "minVelocity": 0.75,
        "solver": "forceAtlas2Based"
      }
    }
    """)

    # add nodes
    for node, data in G.nodes(data=True):

        label = data.get("label", node)

        aliases = ", ".join(data.get("aliases", []))

        title = f"{label}\nAliases: {aliases}"

        net.add_node(
            node,
            label=label,
            title=title,
            size=20
        )

    # add edges
    for u, v, data in G.edges(data=True):

        relation = data.get("relation", "")

        sentiments = data.get("sentiments", [])

        relation_evidence = data.get("relation_evidence", [])

        # build tooltip
        tooltip = f""

        if relation_evidence:
            tooltip += "Evidence:\n"
            for ev in relation_evidence:
                tooltip += f"- {ev}\n"

        if sentiments:
            tooltip += "Sentiments:\n"
            for s in sentiments:
                tooltip += f"{s['type']}\n"
                for ev in s["evidence"]:
                    tooltip += f"- {ev}\n"

        net.add_edge(
            u,
            v,
            label=relation,
            title=tooltip,
        )

    net.write_html(output_file)