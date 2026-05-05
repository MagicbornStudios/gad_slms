import os
import json
from pathlib import Path
import numpy as np

try:
    import faiss
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("WARNING: 'faiss-cpu' and 'sentence-transformers' must be installed for RAG.")

ROOT = Path(__file__).resolve().parents[1]
CORPUS_FILE = ROOT / "data" / "monorepo_corpus.txt"
INDEX_FILE = ROOT / "data" / "rag_index.faiss"
METADATA_FILE = ROOT / "data" / "rag_metadata.json"

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[dict]:
    """Splits raw text into semantic chunks for vectorization."""
    chunks = []
    
    # Split by file blocks first to maintain boundaries
    file_blocks = text.split("<|file_start|>\nPath: ")
    
    for block in file_blocks[1:]:
        path_end = block.find("\n\n")
        if path_end == -1:
            continue
            
        file_path = block[:path_end].strip()
        content = block[path_end+2:].split("\n<|file_end|>")[0]
        
        # Now chunk the content
        words = content.split()
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            if not chunk_words:
                break
                
            chunk_text = " ".join(chunk_words)
            chunks.append({
                "path": file_path,
                "text": chunk_text
            })
            
    return chunks

def semantic_search(query: str, top_k: int = 3) -> str:
    """The Tool Call interface for Dr. Stein to use."""
    if not INDEX_FILE.exists() or not METADATA_FILE.exists():
        return json.dumps({"error": "RAG Index not built yet."})
        
    try:
        model = SentenceTransformer("all-MiniLM-L6-v2")
        index = faiss.read_index(str(INDEX_FILE))
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            
        # Encode query
        query_vector = model.encode([query]).astype("float32")
        faiss.normalize_L2(query_vector)
        
        # Search
        distances, indices = index.search(query_vector, top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(metadata):
                chunk = metadata[idx]
                results.append({
                    "file": chunk["path"],
                    "relevance_score": float(distances[0][i]),
                    "content": chunk["text"]
                })
                
        return json.dumps(results)
    except Exception as e:
        return json.dumps({"error": f"Search failed: {e}"})

def main():
    if not CORPUS_FILE.exists():
        print("Error: monorepo_corpus.txt not found. Run scripts/13_ingest_monorepo.py first.")
        return
        
    print("Building RAG Vector Index...")
    try:
        model = SentenceTransformer("all-MiniLM-L6-v2")
    except NameError:
        print("Error: Missing packages. Please run: pip install faiss-cpu sentence-transformers")
        return
        
    corpus_text = CORPUS_FILE.read_text(encoding="utf-8")
    
    print("Chunking monorepo corpus...")
    chunks = chunk_text(corpus_text)
    print(f"Created {len(chunks)} text chunks.")
    
    # We might not want to embed 50,000 chunks immediately locally on CPU for testing.
    # We will limit to first 500 chunks for demonstration.
    max_chunks = min(500, len(chunks))
    chunks = chunks[:max_chunks]
    
    print(f"Embedding {max_chunks} chunks using all-MiniLM-L6-v2...")
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=True).astype("float32")
    
    # Normalize for cosine similarity
    faiss.normalize_L2(embeddings)
    
    # Build FAISS Index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension) # Inner product (Cosine Similarity)
    index.add(embeddings)
    
    # Save Index and Metadata
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_FILE))
    
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f)
        
    print(f"Successfully saved RAG index to {INDEX_FILE}")
    
    # Test query
    print("\nTesting semantic search for 'How does the chat screen render messages?':")
    print(semantic_search("How does the chat screen render messages?"))

if __name__ == "__main__":
    main()
