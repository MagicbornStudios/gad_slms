import re
import json
from pathlib import Path
import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
CORPUS_FILE = ROOT / "data" / "monorepo_corpus.txt"
GRAPH_FILE = ROOT / "data" / "knowledge_graph.gml"

def parse_corpus_to_graph(corpus_text: str) -> nx.DiGraph:
    """Parses the monorepo corpus text and builds a dependency graph."""
    graph = nx.DiGraph()
    
    # Split by <|file_start|>
    file_blocks = corpus_text.split("<|file_start|>\nPath: ")
    
    for block in file_blocks[1:]: # Skip the first empty/system directive block
        try:
            # Extract file path
            path_end = block.find("\n\n")
            if path_end == -1:
                continue
                
            file_path = block[:path_end].strip()
            content = block[path_end+2:]
            
            # Clean up the end tag
            content = content.split("\n<|file_end|>")[0]
            
            # Add node
            graph.add_node(file_path, type="file", size=len(content))
            
            # Simple heuristic extraction: Find imports
            # Match python: `import X` or `from X import Y`
            # Match JS/TS: `import X from 'Y'` or `require('Y')`
            imports = set()
            
            # TS/JS imports
            for match in re.finditer(r"import\s+.*?\s+from\s+['\"](.*?)['\"]", content):
                imports.add(match.group(1))
            
            # Python imports
            for match in re.finditer(r"^(?:from\s+([a-zA-Z0-9_\.]+)\s+)?import\s+([a-zA-Z0-9_\.\, ]+)", content, re.MULTILINE):
                if match.group(1):
                    imports.add(match.group(1))
                else:
                    for imp in match.group(2).split(","):
                        imports.add(imp.strip())
                        
            # Add edges
            for imp in imports:
                graph.add_node(imp, type="module")
                graph.add_edge(file_path, imp, relation="imports")
                
        except Exception as e:
            print(f"Error parsing block: {e}")
            
    return graph

def query_graph(entity: str) -> str:
    """The Tool Call interface for Dr. Stein to use."""
    if not GRAPH_FILE.exists():
        return json.dumps({"error": "Knowledge graph not built yet."})
        
    G = nx.read_gml(GRAPH_FILE)
    
    # Fuzzy match entity
    matched_nodes = [n for n in G.nodes() if entity.lower() in n.lower()]
    
    if not matched_nodes:
        return json.dumps({"error": f"Entity '{entity}' not found in the monorepo graph."})
        
    result = {}
    for node in matched_nodes[:3]: # Limit to top 3 matches to save tokens
        successors = list(G.successors(node))
        predecessors = list(G.predecessors(node))
        result[node] = {
            "depends_on": successors[:10],
            "imported_by": predecessors[:10]
        }
        
    return json.dumps(result)

def main():
    if not CORPUS_FILE.exists():
        print("Error: monorepo_corpus.txt not found. Run scripts/13_ingest_monorepo.py first.")
        return
        
    print("Building Knowledge Graph (Graphify)...")
    corpus_text = CORPUS_FILE.read_text(encoding="utf-8")
    
    G = parse_corpus_to_graph(corpus_text)
    
    print(f"Graph built successfully! Nodes: {G.number_of_nodes()} | Edges: {G.number_of_edges()}")
    
    # Save graph
    GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
    nx.write_gml(G, GRAPH_FILE)
    print(f"Saved Knowledge Graph to {GRAPH_FILE}")
    
    # Test query
    print("\nTesting graph tool query for 'chat_screen':")
    print(query_graph("chat_screen"))

if __name__ == "__main__":
    main()
