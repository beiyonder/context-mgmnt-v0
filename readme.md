# RepoMap-ish Symbol Ranker

Scans Python files, extracts symbol definitions and references using Tree-sitter (make sure it's `tree-sitter==0.21.3`), builds a directed graph of symbol usage, and runs personalized PageRank to figure out which files matter most. Outputs a rough LLM-friendly context blob.


# But why?
LLM friendly context:
Unlike raw code, which can overwhelm LLMs with tokens (e.g., thousands of lines), the output is a distilled summary of key symbols and their locations.

Token Efficiency:
The output is compact (154 tokens), preserving LLM context window space for user queries or additional data.

Indexing:
This is a precursor to a full indexing system for RAG.

Graph-Based Ranking:
The PageRank algorithm prioritizes important files based on symbol references, ensuring the LLM sees the most relevant parts first

How it helps apna llm:
Architectural Understanding,
Reduced Cognitive Load,
Contextual Relevance

# What next? -- full-blown context mgmnt sys

Current: Only processes Python files.
Goal: Handle codebases, docs, emails, and database schemas.

Current: In-memory tags with simple dictionary cache.
Goal: Store indexed data in a structured, queryable format.


Current: Extracts definitions and references with basic graph connections.
Goal: Deeper analysis of code relationships and semantics.

RAG Retrieval::
Current: Static output with no query mechanism.
Goal: Query-based retrieval of relevant context.
sentence-transformers, top-k relevant items


Current: Outputs context but doesn’t interact with an LLM.
Goal: Prepare prompts, send to LLM, and process responses.


Example output:

```
Scanning files...
Parsing files: 100%|██████████| 4/4 [00:00<00:00, 25.00it/s]

--- Repo Map Context (approx. 200 tokens) ---
aider\utils.py:
  line 16: def IgnorantTemporaryDirectory(suffix=None, prefix=None, dir=None):
  line 17: docstring: A context manager for temporary directories...
  line 62: def GitTemporaryDirectory():
  line 63: docstring: Creates a temporary git repository...

--- LLM Response ---
To create a temporary git repository, use the `GitTemporaryDirectory` function from `aider\utils.py`. Here's an example:

from aider.utils import GitTemporaryDirectory

with GitTemporaryDirectory() as repo_dir:
    # Use repo_dir as a temporary git repository
    print(f"Repository created at {repo_dir}")
```







