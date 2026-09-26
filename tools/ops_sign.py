#!/usr/bin/env python
"""Sign an ops file so the system accepts it.

    python tools/ops_sign.py ops/pending/2026-09-27-blog.json

Adds (or replaces) the "signature" key in place using OPS_SIGNING_KEY
(or, in DEBUG, the key derived from SECRET_KEY). Read AGENTS.md
"Ops-file protocol" for the full contract.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "skeleton.settings")

import django  # noqa: E402

django.setup()

from core import opsmanager  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python tools/ops_sign.py <file.json>")
        raise SystemExit(1)
    path = Path(sys.argv[1])
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc.pop("signature", None)
    doc["signature"] = opsmanager.sign_doc(doc)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ok, status, reason = opsmanager.validate_doc(doc)
    print(f"signed {path.name}; validation: {'OK' if ok else f'{status}: {reason}'}")


if __name__ == "__main__":
    main()
