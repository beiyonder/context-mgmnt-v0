#Big note: make sure tree-sitter == 0.21.3
import os
import sys
import argparse
from pathlib import Path
from collections import defaultdict, namedtuple
from time import time
import networkx as nx
from tree_sitter_languages import get_language, get_parser
from pygments.lexers import guess_lexer_for_filename
from pygments.token import Token
from tqdm import tqdm

# Map file extension to language name
EXT_TO_LANG = {
    '.py': 'python',
}

# Tree-sitter query for Python to extract definitions and references
PY_TAGS_QUERY = """
((function_definition name: (identifier) @name.definition.function))
((class_definition name: (identifier) @name.definition.class))
((identifier) @name.reference)
"""

# Define a Tag tuple to store symbol information
Tag = namedtuple("Tag", "rel_fname fname line name kind")

def find_src_files(paths):
    """Recursively find source files in the given paths."""
    src_files = []
    for path in paths:
        path = Path(path)
        if path.is_dir():
            for root, _, files in os.walk(path):
                for file in files:
                    if Path(file).suffix.lower() in EXT_TO_LANG:
                        src_files.append(os.path.join(root, file))
        elif path.is_file() and path.suffix.lower() in EXT_TO_LANG:
            src_files.append(str(path))
    return sorted(set(src_files))

def filename_to_lang(fname):
    """Map filename extension to language name."""
    ext = Path(fname).suffix.lower()
    return EXT_TO_LANG.get(ext)

def get_mtime(fname):
    """Get file modification time, return None if file not found."""
    try:
        return os.path.getmtime(fname)
    except FileNotFoundError:
        print(f"Warning: File not found: {fname}")
        return None

def get_tags_py(fname, rel_fname, cache=None):
    """Extract tags (definitions and references) from a Python file."""
    # Check cache
    file_mtime = get_mtime(fname)
    if file_mtime is None:
        return []
    if cache is not None and fname in cache and cache[fname]['mtime'] == file_mtime:
        return cache[fname]['data']

    lang = filename_to_lang(fname)
    if lang != 'python':
        return []

    # Parse with Tree-Sitter
    parser = get_parser('python')
    language = get_language('python')
    try:
        with open(fname, 'r', encoding='utf-8', errors='replace') as f:
            code = f.read()
    except FileNotFoundError:
        print(f"Error: File {fname} not found.")
        return []

    tree = parser.parse(bytes(code, 'utf-8'))
    root = tree.root_node
    query = language.query(PY_TAGS_QUERY)
    captures = query.captures(root)
    
    tags = []
    saw_kinds = set()
    for node, tag_name in captures:
        if tag_name.startswith('name.definition.'):
            kind = 'def'
        elif tag_name.startswith('name.reference'):
            kind = 'ref'
        else:
            continue
        saw_kinds.add(kind)
        tags.append(Tag(rel_fname, fname, node.start_point[0], node.text.decode('utf-8'), kind))

    # Fallback to Pygments for references if no refs found
    if 'def' in saw_kinds and 'ref' not in saw_kinds:
        try:
            lexer = guess_lexer_for_filename(fname, code)
            tokens = list(lexer.get_tokens(code))
            tokens = [token[1] for token in tokens if token[0] in Token.Name]
            for token in tokens:
                tags.append(Tag(rel_fname, fname, -1, token, 'ref'))
        except Exception as e:
            print(f"Warning: Pygments failed for {fname}: {e}")

    # Update cache
    if cache is not None:
        cache[fname] = {'mtime': file_mtime, 'data': tags}

    return tags

def get_tags(fname, rel_fname, cache=None):
    """Get tags for a file based on its language."""
    lang = filename_to_lang(fname)
    if lang == 'python':
        return get_tags_py(fname, rel_fname, cache)
    return []

def build_graph(tags, chat_fnames=None, mentioned_idents=None):
    """Build a directed graph from tags for ranking with personalization."""
    if chat_fnames is None:
        chat_fnames = set()
    if mentioned_idents is None:
        mentioned_idents = set()

    defines = defaultdict(set)
    references = defaultdict(list)
    definitions = defaultdict(set)
    personalization = {}

    # Initialize personalization
    fnames = {tag.rel_fname for tag in tags}
    if fnames:
        default_pers = 100 / len(fnames)
        for fname in fnames:
            pers = 0.0
            if fname in chat_fnames:
                pers += default_pers
            if any(ident in fname for ident in mentioned_idents):
                pers += default_pers
            if pers > 0:
                personalization[fname] = pers

    # Collect definitions and references
    for tag in tags:
        if tag.kind == 'def':
            defines[tag.name].add(tag.rel_fname)
            definitions[(tag.rel_fname, tag.name)].add(tag)
        elif tag.kind == 'ref':
            references[tag.name].append(tag.rel_fname)

    G = nx.MultiDiGraph()

    # Add self-edges for definitions without references
    for ident in defines:
        if ident not in references:
            for definer in defines[ident]:
                G.add_edge(definer, definer, weight=0.1, ident=ident)

    # Add edges for references to definitions
    idents = set(defines.keys()).intersection(set(references.keys()))
    for ident in idents:
        definers = defines[ident]
        for referencer in references[ident]:
            weight = 1.0
            if referencer in chat_fnames or any(ident in referencer for ident in mentioned_idents):
                weight *= 10.0
            for definer in definers:
                G.add_edge(referencer, definer, weight=weight, ident=ident)

    return G, definitions, personalization

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

def token_count(text):
    """Estimate token count (approximate as words/4)."""
    if not text:
        return 0
    words = len(text.split())
    return words // 4

def format_context(ranked, definitions, tags, max_tokens=1024):
    """Format the ranked results as a markdown-like summary within token limit."""
    lines = []
    files_by_rank = sorted(set(tag.rel_fname for tag in tags), key=lambda f: -ranked.get(f, 0))
    
    for rel_fname in files_by_rank:
        file_defs = [tag for tag in tags if tag.rel_fname == rel_fname and tag.kind == 'def']
        if not file_defs:
            continue
        lines.append(f'\n{rel_fname}:')
        for tag in sorted(file_defs, key=lambda t: t.line):
            lines.append(f'  line {tag.line + 1}: def {tag.name}')
        
        # Check token count
        current_text = '\n'.join(lines)
        if token_count(current_text) > max_tokens:
            # Truncate to fit token limit
            while lines and token_count('\n'.join(lines)) > max_tokens:
                lines.pop()
            break

    return '\n'.join(lines)

def main():
    """Main function to process files and generate repo map context."""
    parser = argparse.ArgumentParser(description='Standalone RepoMap/LLM context demo')
    parser.add_argument('paths', nargs='*', help='Source code files or directories to analyze')
    parser.add_argument('--chat-files', nargs='*', default=[], help='Files actively being edited (prioritized)')
    parser.add_argument('--max-tokens', type=int, default=1024, help='Maximum tokens for output')
    args = parser.parse_args()

    # Initialize cache
    tags_cache = {}

    # Find source files
    if not args.paths:
        example_files = [
            'aider/repomap.py',
            'aider/linter.py',
            'aider/commands.py',
            'aider/utils.py',
        ]
        print('No paths provided. Using example files:')
        for f in example_files:
            print(' ', f)
        args.paths = example_files

    print("Scanning files...")
    src_files = find_src_files(args.paths)
    if not src_files:
        print("No source files found.")
        return

    # Extract tags
    all_tags = []
    for fname in tqdm(src_files, desc="Parsing files"):
        try:
            rel_fname = os.path.relpath(fname)
            tags = get_tags(fname, rel_fname, cache=tags_cache)
            all_tags.extend(tags)
        except Exception as e:
            print(f"Error processing {fname}: {e}")

    if not all_tags:
        print("No symbols found in the provided files.")
        return

    # Build graph and compute rankings
    chat_fnames = set(os.path.relpath(f) for f in find_src_files(args.chat_files))
    mentioned_idents = set()  # Could be extended via args
    G, definitions, personalization = build_graph(all_tags, chat_fnames, mentioned_idents)
    ranked = rank_graph(G, personalization)

    # Format the repo map context
    context = format_context(ranked, definitions, all_tags, max_tokens=args.max_tokens)
    
    # Output the repo map context
    print(f'\n--- Repo Map Context (approx. {token_count(context)} tokens) ---')
    print(context)

if __name__ == '__main__':
    main()