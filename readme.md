# RepoMap-ish Symbol Ranker

Scans Python files, extracts symbol definitions and references using Tree-sitter (make sure it's `tree-sitter==0.21.3`), builds a directed graph of symbol usage, and runs personalized PageRank to figure out which files matter most. Outputs a rough LLM-friendly context blob.
