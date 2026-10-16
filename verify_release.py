"""Verify current public snapshot files against the SHA-256 manifest."""
import hashlib
import json
from pathlib import Path
root = Path(__file__).resolve().parent
expected = json.loads((root / "RELEASE_SHA256.json").read_text())
bad = [name for name, digest in expected.items() if not (root / name).is_file() or hashlib.sha256((root / name).read_bytes()).hexdigest() != digest]
if bad:
    raise SystemExit("Missing or changed files: " + ", ".join(bad))
print(f"Verified {len(expected)} release files.")
