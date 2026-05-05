import os
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MONOREPO_DIR = Path("C:/Users/benja/Documents/custom_portfolio")
OUTPUT_FILE = ROOT / "data" / "monorepo_corpus.txt"
REGISTRY_FILE = ROOT / "data" / "gad_supported_stacks.json"

MAX_CORPUS_SIZE = 10 * 1024 * 1024  # 10 MB limit to prevent OOM
EXCLUDE_DIRS = {".git", "node_modules", "dist", "build", ".next", "coverage", "vendor", ".DS_Store"}

def get_allowed_extensions(registry):
    # Map supported languages to file extensions
    lang_to_ext = {
        "typescript": [".ts", ".tsx"],
        "javascript": [".js", ".jsx", ".mjs", ".cjs"],
        "python": [".py"],
        "css": [".css"],
        "html": [".html"],
        "bash": [".sh", ".bash"],
        "sql": [".sql"]
    }
    
    allowed = {".xml", ".md", ".mdx", ".json"} # Always allow GAD artifacts and configs
    
    for lang in registry.get("supported_languages", []):
        exts = lang_to_ext.get(lang.lower(), [])
        for ext in exts:
            allowed.add(ext)
            
    return allowed

def gather_files(base_dir: Path, allowed_exts: set) -> list[Path]:
    target_files = []
    
    if not base_dir.exists():
        print(f"Warning: Base directory {base_dir} does not exist!")
        return target_files

    for root, dirs, files in os.walk(base_dir):
        # Mutate dirs in place to prevent os.walk from visiting excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix.lower() in allowed_exts:
                target_files.append(file_path)
                
    return target_files

def main():
    if not REGISTRY_FILE.exists():
        raise FileNotFoundError(f"Missing Domain Registry: {REGISTRY_FILE}")
        
    registry = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    allowed_exts = get_allowed_extensions(registry)
    
    print(f"Ingesting monorepo at {MONOREPO_DIR}...")
    print(f"Domain Registry allows extensions: {', '.join(allowed_exts)}")
    
    all_files = gather_files(MONOREPO_DIR, allowed_exts)
    print(f"Found {len(all_files)} potential source files.")
    
    # Shuffle files so we get a diverse sample across the monorepo up to the 10MB limit
    random.seed(42)
    random.shuffle(all_files)
    
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    total_bytes = 0
    ingested_count = 0
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out_f:
        # Write the training directives from the registry as the absolute system prompt
        out_f.write("<|system_directives|>\n")
        for directive in registry.get("training_directives", []):
            out_f.write(f"- {directive}\n")
        out_f.write("<|end_system_directives|>\n\n")
        
        for fpath in all_files:
            if total_bytes >= MAX_CORPUS_SIZE:
                break
                
            try:
                content = fpath.read_text(encoding="utf-8")
                
                # Skip massive generated files or minified bundles that slipped through
                if len(content) > 500000:
                    continue
                    
                rel_path = fpath.relative_to(MONOREPO_DIR).as_posix()
                block = f"<|file_start|>\nPath: {rel_path}\n\n{content}\n<|file_end|>\n\n"
                
                out_f.write(block)
                total_bytes += len(block.encode("utf-8"))
                ingested_count += 1
                
            except Exception as e:
                # Silently skip binary files or encoding errors
                pass

    print(f"Success! Ingested {ingested_count} files.")
    print(f"Corpus generated at: {OUTPUT_FILE}")
    print(f"Final Size: {total_bytes / (1024*1024):.2f} MB")

if __name__ == "__main__":
    main()
