# PageRank Computation (`rank_graph`)
(AI-refined summary)
## Function

```python
def rank_graph(G, personalization=None):
    """Rank graph nodes using PageRank."""
    if len(G) == 0:
        return {}
    try:
        if personalization:
            return nx.pagerank(G, weight='weight', personalization=personalization, dangling=personalization)
        return nx.pagerank(G, weight='weight')
    except ZeroDivisionError:
        print("Warning: PageRank failed, returning empty ranks.")
        return {}
```

Uses NetworkX’s `pagerank` function, which implements the PageRank algorithm.

---

## Algorithm Overview

Each node (file) starts with an initial rank (e.g., 1/N for N nodes).

Iteratively updates ranks based on incoming edges:

```
Rank(v) = (1-d)/N + d * Σ(Rank(u) * Weight(u→v) / OutDegree(u))
```

- **d**: Damping factor (default 0.85 in NetworkX), simulates random jumps.
- **Weight(u→v)**: Edge weight (e.g., 1.0 or 10.0).
- **OutDegree(u)**: Sum of weights of outgoing edges from node u.

---

## Personalization

Personalization modifies the random jump probability:

- Normally, a random jump lands on any node with probability 1/N.
- With personalization, jump probability is proportional to `personalization[fname]` (0 for unlisted files).

Example:  
If `personalization['aider\\utils.py'] = 10` and others are 0, random jumps favor `aider\\utils.py`.

---

## Dangling Nodes

Nodes with no outgoing edges use the same personalization vector to distribute their rank.

---

## Output

A dictionary mapping files to their PageRank scores, e.g.:

```python
{'aider\\utils.py': 0.4, 'aider\\commands.py': 0.3}
```

---

## Error Handling

Returns empty dict if PageRank fails (e.g., due to disconnected graphs).

---

## Example Scenario

**Files:**
- `aider\\utils.py`: Defines `make_repo`, `IgnorantTemporaryDirectory`.
- `aider\\commands.py`: References `make_repo`.
- `aider\\linter.py`: No references.

**Graph:**
- **Nodes:** `aider\\utils.py`, `aider\\commands.py`, `aider\\linter.py`
- **Edges:**
    - `aider\\commands.py` → `aider\\utils.py` (weight=1.0, for `make_repo` reference)
    - `aider\\utils.py` → `aider\\utils.py` (weight=0.1, for `IgnorantTemporaryDirectory` self-edge)
    - `aider\\linter.py` → `aider\\linter.py` (weight=0.1, isolated)

**Personalization:**  
If `aider\\commands.py` is in `chat_fnames`,  
`personalization = {'aider\\commands.py': 33.33}` (100/3 files).

**PageRank:**
- `aider\\utils.py` gets high rank due to incoming edge from `aider\\commands.py`.
- `aider\\commands.py` gets boosted rank due to personalization.
- `aider\\linter.py` gets low rank (only self-edge, no personalization).

**Result:**  
`{'aider\\utils.py': 0.5, 'aider\\commands.py': 0.4, 'aider\\linter.py': 0.1}` (values illustrative).

---

## Usage in Formatting

The ranks are used in `format_context` to sort files:

```python
files_by_rank = sorted(set(tag.rel_fname for tag in tags), key=lambda f: -ranked.get(f, 0))
```

Files with higher PageRank appear first in the output, ensuring the LLM sees the most important files (e.g., `aider\\utils.py` with many references).

---

## Why This Matters

- **Importance Ranking:** Files central to the codebase (e.g., `utils.py` with widely used functions) get higher ranks, guiding the LLM to focus on critical modules.
- **Context Relevance:** Personalization ensures user-relevant files (e.g., `chat_fnames`) are prioritized, aligning with user intent.
- **Scalability:** The graph structure handles large repositories by summarizing relationships concisely.

