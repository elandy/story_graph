from pathlib import Path

from pyvis.network import Network

from story_graph.graph.relationship_groups import get_relation_color, get_relation_group


def _edge_positions(data):
    """Collect all evidence positions for an edge (relation + sentiments)."""
    positions = []
    for ev in data.get("relation_evidence", []):
        pos = ev.get("position") if isinstance(ev, dict) else None
        if pos is not None:
            positions.append(pos)
    for s in data.get("sentiments", []):
        for ev in s.get("evidence", []):
            pos = ev.get("position") if isinstance(ev, dict) else None
            if pos is not None:
                positions.append(pos)
    return positions


def _iter_edges(G):
    """Yield (u, v, key, data) for each edge; works with MultiDiGraph and DiGraph."""
    if G.is_multigraph():
        for u, v, key, data in G.edges(keys=True, data=True):
            yield u, v, key, data
    else:
        for u, v, data in G.edges(data=True):
            yield u, v, data.get("relation", ""), data


def visualize_graph(G, output_file="story_graph.html", total_chunks=None):
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

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

    # compute max position for the slider (span all chunks 0..total_chunks-1)
    max_position = 0
    for _u, _v, _key, data in _iter_edges(G):
        positions = _edge_positions(data)
        if positions:
            max_position = max(max_position, max(positions))
    if total_chunks is not None and total_chunks > 0:
        max_position = max(max_position, total_chunks - 1)

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

    # add edges with id and minPosition for time slider
    for u, v, key, data in _iter_edges(G):

        relation = data.get("relation", key)

        sentiments = data.get("sentiments", [])

        relation_evidence = data.get("relation_evidence", [])

        raw_positions = _edge_positions(data)
        positions = sorted(set(raw_positions)) if raw_positions else []
        min_position = min(positions) if positions else 0
        group = get_relation_group(relation)

        edge_id = f"{u}__{v}__{key}"

        # Get color for the relation
        edge_color = get_relation_color(relation.lower())

        # build tooltip text (plain text, since HTML tags are rendered literally)
        tooltip = f"Relation: {relation}\n"

        if relation_evidence:
            tooltip += "Evidence:\n"
            for ev in relation_evidence:
                pos = ev.get("position")
                line = ev.get("text", ev) if isinstance(ev, dict) else ev
                if pos is not None:
                    tooltip += f"- [chunk {pos}] {line}\n"
                else:
                    tooltip += f"- {line}\n"

        if sentiments:
            tooltip += "Sentiments:\n"
            for s in sentiments:
                tooltip += f"- {s['type']}\n"
                for ev in s["evidence"]:
                    pos = ev.get("position") if isinstance(ev, dict) else None
                    line = ev.get("text", ev) if isinstance(ev, dict) else ev
                    if pos is not None:
                        tooltip += f"  - [chunk {pos}] {line}\n"
                    else:
                        tooltip += f"  - {line}\n"

        net.add_edge(
            u,
            v,
            id=edge_id,
            label=relation,
            title=tooltip,
            color=edge_color,
            minPosition=min_position,
            positions=positions,
            group=group,
            position=data.get("position"),
            end_position=data.get("end_position"),
        )

    net.write_html(str(output_path))

    # inject time slider into generated HTML
    _inject_time_slider(output_path, max_position)


def _inject_time_slider(html_path: Path, max_position: int) -> None:
    html = html_path.read_text(encoding="utf-8")

    slider_div = f'''            <div id="time-slider-container" class="card-header" style="padding: 1rem; background: #333;">
                <label for="timeSlider" style="color: #eee;">Story progression (chunk):</label>
                <input type="range" id="timeSlider" min="0" max="{max_position}" value="{max_position}" style="width: 300px; margin-left: 10px; vertical-align: middle;">
                <span id="timeValue" style="color: #eee; margin-left: 10px;">{max_position}</span>
            </div>
            '''

    marker = '<div id="mynetwork" class="card-body"></div>'
    if marker in html and slider_div not in html:
        html = html.replace(marker, slider_div + "\n            " + marker)

    slider_js = """
              (function() {
                var slider = document.getElementById('timeSlider');
                var timeValue = document.getElementById('timeValue');
                if (!slider || !timeValue) return;
                function updateVisibility(t) {
                  var tVal = parseInt(t, 10);
                  var edgeList = edges.get();
                  var pairGroups = {};
                  edgeList.forEach(function(e) {
                    var pair = e.from + "\\u0000" + e.to;
                    if (!pairGroups[pair]) pairGroups[pair] = {};
                    var g = e.group != null ? e.group : e.id;
                    if (!pairGroups[pair][g]) pairGroups[pair][g] = [];
                    pairGroups[pair][g].push(e);
                  });
                  var showEdgeIds = {};
                  var visibleEdgeIds = {};
                  var edgeUpdates = [];
                  edgeList.forEach(function(e) {
                    var show = false;
                    var start = e.position;
                    var end = e.end_position;
                    if (start != null && tVal >= start && (end == null || tVal < end)) {
                      show = true;
                    }
                    if (show) { visibleEdgeIds[e.from] = true; visibleEdgeIds[e.to] = true; }
                    edgeUpdates.push({ id: e.id, hidden: !show });
                  });
                  edges.update(edgeUpdates);
                  var nodeList = nodes.get();
                  var nodeUpdates = nodeList.map(function(n) {
                    return { id: n.id, hidden: !visibleEdgeIds[n.id] };
                  });
                  nodes.update(nodeUpdates);
                }
                slider.addEventListener('input', function() {
                  timeValue.textContent = slider.value;
                  updateVisibility(slider.value);
                });
                updateVisibility(slider.value);
              })();
    """

    draw_marker = "drawGraph();"
    if draw_marker in html and "updateVisibility" not in html:
        html = html.replace(draw_marker, draw_marker + "\n" + slider_js)

    html_path.write_text(html, encoding="utf-8")
