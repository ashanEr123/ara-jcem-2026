"""Verify the release overlay, not unrelated existing repository files."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
expected = json.loads((root/'R2_RELEASE_SHA256.json').read_text())
bad = []
for name, digest in expected.items():
    p = root/name
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
        bad.append(name)
if bad:
    raise SystemExit('Missing or changed files: ' + ', '.join(bad))
print(f'Verified {len(expected)} release files.')
