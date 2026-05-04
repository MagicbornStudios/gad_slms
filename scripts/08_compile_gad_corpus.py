import os
from pathlib import Path

def get_planning_files(root_dir: Path):
    planning_dir = root_dir / ".planning"
    files = []
    
    if not planning_dir.exists():
        return files
        
    for ext in ["*.xml", "*.md", "*.json"]:
        files.extend(list(planning_dir.rglob(ext)))
        
    # Also grab soul files to understand agent personas
    souls_dir = root_dir / "narrative" / "souls"
    if souls_dir.exists():
        files.extend(list(souls_dir.glob("*.md")))
        
    return files

def main():
    root_dir = Path(__file__).resolve().parents[1]
    files = get_planning_files(root_dir)
    
    out_dir = root_dir / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "gad_corpus.txt"
    
    total_chars = 0
    with open(out_file, "w", encoding="utf-8") as out_f:
        for fpath in files:
            try:
                content = fpath.read_text(encoding="utf-8")
                # Add clear structural markers so the SLM learns file structures
                rel_path = fpath.relative_to(root_dir).as_posix()
                
                block = f"<|file_start|>\nPath: {rel_path}\n\n{content}\n<|file_end|>\n\n"
                out_f.write(block)
                total_chars += len(block)
            except Exception as e:
                print(f"Skipping {fpath}: {e}")
                
    print(f"Compiled {len(files)} GAD planning files into {out_file}")
    print(f"Total Corpus Size: {total_chars:,} characters")

if __name__ == "__main__":
    main()
