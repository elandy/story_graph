def print_graph(G):

    print("\n--- Story Graph ---\n")

    for u, v, key, data in G.edges(keys=True, data=True):

        print(f"{u} -> {v}")

        print(" relation:", data.get("relation", key))

        if "sentiments" in data:
            for s in data["sentiments"]:
                print(" sentiment:", s["type"])

        print()