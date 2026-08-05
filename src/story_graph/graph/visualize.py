from pathlib import Path

from pyvis.network import Network

from story_graph.graph.relationship_groups import get_relation_color, get_relation_group

# ---- Threadbound palette (matches the upload page) ----
PAPER = "#f1e8d4"
INK = "#1b1714"
INK_SOFT = "#221c19"
FOREST = "#2f4a3c"
GOLD = "#a3792f"
WAX = "#8a3324"
MUTED = "#9a8f7d"


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
        bgcolor=INK,
        font_color=PAPER,
    )
    net.set_options(f"""
    {{
      "nodes": {{
        "shape": "dot",
        "size": 18,
        "borderWidth": 2,
        "borderWidthSelected": 3,
        "color": {{
          "background": "{FOREST}",
          "border": "{GOLD}",
          "highlight": {{ "background": "{GOLD}", "border": "{PAPER}" }},
          "hover": {{ "background": "{FOREST}", "border": "{PAPER}" }}
        }},
        "font": {{
          "color": "{PAPER}",
          "face": "Inter",
          "size": 16,
          "strokeWidth": 0
        }},
        "shadow": {{
          "enabled": true,
          "color": "rgba(0,0,0,0.45)",
          "size": 10,
          "x": 2,
          "y": 3
        }}
      }},
      "edges": {{
        "width": 1.3,
        "hoverWidth": 0.6,
        "selectionWidth": 1,
        "color": {{
          "inherit": false,
          "opacity": 0.85
        }},
        "smooth": {{
          "type": "continuous",
          "roundness": 0.15
        }},
        "arrows": {{
          "to": {{ "enabled": true, "scaleFactor": 0.45 }}
        }},
        "font": {{
          "size": 11,
          "color": "{MUTED}",
          "face": "IBM Plex Mono",
          "strokeWidth": 0,
          "align": "top",
          "background": "{INK_SOFT}"
        }}
      }},
      "physics": {{
        "forceAtlas2Based": {{
          "gravitationalConstant": -50,
          "centralGravity": 0.01,
          "springLength": 150,
          "springConstant": 0.08
        }},
        "minVelocity": 0.75,
        "solver": "forceAtlas2Based",
        "stabilization": {{ "iterations": 250 }}
      }},
      "interaction": {{
        "hover": true,
        "tooltipDelay": 120,
        "navigationButtons": true,
        "keyboard": true
      }}
    }}
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

    # inject time slider and theme into generated HTML
    _inject_time_slider(output_path, max_position)
    _inject_theme_css(output_path)


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


def _inject_theme_css(html_path: Path) -> None:
    """Reskin pyvis's default page chrome (card, slider, tooltip, nav buttons)
    to match the Story Graph Studio 'Threadbound' theme."""
    html = html_path.read_text(encoding="utf-8")

    theme_head = f'''
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,560&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
      html, body {{
        margin: 0;
        background: {INK} !important;
        font-family: "Inter", "Segoe UI", sans-serif;
      }}
      .card {{
        border: none !important;
        border-radius: 0 !important;
      }}
      .card-header, #time-slider-container {{
        background: {INK_SOFT} !important;
        border-bottom: 1px solid rgba(163, 121, 47, 0.35) !important;
        display: flex !important;
        align-items: center;
        gap: 0.85rem;
        padding: 0.9rem 1.4rem !important;
      }}
      #time-slider-container label {{
        font-family: "Fraunces", Georgia, serif;
        font-weight: 560;
        font-size: 0.95rem;
        color: {PAPER} !important;
        letter-spacing: 0.01em;
      }}
      #timeValue {{
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.85rem;
        color: {GOLD} !important;
        min-width: 2ch;
      }}
      #timeSlider {{
        -webkit-appearance: none;
        appearance: none;
        height: 4px;
        border-radius: 999px;
        background: rgba(241, 232, 212, 0.18) !important;
        outline: none;
      }}
      #timeSlider::-webkit-slider-thumb {{
        -webkit-appearance: none;
        appearance: none;
        width: 15px;
        height: 15px;
        border-radius: 50%;
        background: {GOLD};
        border: 2px solid {PAPER};
        cursor: pointer;
        margin-top: -1px;
      }}
      #timeSlider::-moz-range-thumb {{
        width: 15px;
        height: 15px;
        border-radius: 50%;
        background: {GOLD};
        border: 2px solid {PAPER};
        cursor: pointer;
        border: 2px solid {PAPER};
      }}
      #mynetwork {{
        border: none !important;
      }}
      .vis-tooltip {{
        font-family: "IBM Plex Mono", monospace !important;
        font-size: 0.78rem !important;
        line-height: 1.5 !important;
        background: {PAPER} !important;
        color: {INK} !important;
        border: 1px solid rgba(27, 23, 20, 0.15) !important;
        border-radius: 10px !important;
        padding: 0.65rem 0.8rem !important;
        box-shadow: 0 14px 30px rgba(0, 0, 0, 0.4) !important;
        max-width: 340px;
        white-space: pre-line !important;
      }}
      div.vis-network:focus {{
        outline: none !important;
      }}
      .vis-navigation .vis-button {{
        filter: invert(0.85) sepia(0.5) saturate(3) hue-rotate(3deg);
        opacity: 0.7;
      }}
      .vis-navigation .vis-button:hover {{
        opacity: 1;
      }}
    </style>
    '''

    if "</head>" in html and "Fraunces" not in html:
        html = html.replace("</head>", theme_head + "\n</head>")

    html_path.write_text(html, encoding="utf-8")