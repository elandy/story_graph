def print_graph(G):

    print("\n--- Story Graph ---\n")

    for u, v, data in G.edges(data=True):

        print(f"{u} -> {v}")

        print(" relation:", data.get("relation"))

        if "sentiments" in data:
            for s in data["sentiments"]:
                print(" sentiment:", s["type"])

        print()