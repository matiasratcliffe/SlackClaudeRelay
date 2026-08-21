# Design — add-traversal-assembly

- `spreading_activation(seeds, max_hops, decay, threshold)`: priority frontier by activation;
  `act(v) += act(u)*decay^hop*edge_weight/outdeg(u)`; visit both primary and secondary edges; stop a
  path below threshold; global max-hop backstop. Returns `{node_id: activation}` + edge trace.
- `personalized_pagerank(seeds, damping, iters)`: power iteration over the candidate adjacency with
  restart vector = normalized seed weights (pure Python; small subgraph).
- Both run over a bounded neighborhood pulled from the store (`children`/edges up to max-hops).
- `assemble(query, budget, strategy)`: entry points → mechanical layer → rank (activation/PPR score,
  tie-break recency) → greedily fill budget → render markdown (title, body, in-edges) → return
  `AssemblyResult{nodes, edges, markdown, path}`.
- Hub summary read-first is a documented hook (`summary` field); regeneration is out of scope now.
