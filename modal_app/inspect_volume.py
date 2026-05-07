"""Tiny Modal app to peek at parquet schemas in slm-data volume.

Avoids local disk hits for inspecting remote data.
"""
from __future__ import annotations

import json
import modal


app = modal.App("slm-learning-inspect-volume")
image = modal.Image.debian_slim().pip_install("pyarrow", "pandas")
data_volume = modal.Volume.from_name("slm-data")


@app.function(
    image=image,
    volumes={"/data": data_volume},
    timeout=120,
    cpu=2,
    memory=4096,
)
def schema(parquet_path: str, head: int = 1) -> dict:
    import pyarrow.parquet as pq
    table = pq.read_table(parquet_path)
    rows = table.slice(0, head).to_pylist()
    sample = {}
    for k, v in (rows[0].items() if rows else {}):
        s = str(v) if v is not None else None
        sample[k] = s[:300] + ("..." if s and len(s) > 300 else "")
    return {
        "path": parquet_path,
        "num_rows": table.num_rows,
        "columns": [{"name": f.name, "type": str(f.type)} for f in table.schema],
        "sample_row_truncated": sample,
    }


@app.local_entrypoint()
def main(path: str) -> None:
    out = schema.remote(path)
    print(json.dumps(out, indent=2))
