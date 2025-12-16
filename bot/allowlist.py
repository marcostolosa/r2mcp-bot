from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Set


@dataclass(frozen=True)
class Allowlist:
    allowed_user_ids: Set[int]

    def is_allowed(self, user_id: int) -> bool:
        return user_id in self.allowed_user_ids


def load_allowlist(path: Path) -> Allowlist:
    data = json.loads(path.read_text(encoding="utf-8"))
    ids = data.get("allowed_user_ids", [])
    allowed: Set[int] = set()
    for raw in ids:
        try:
            allowed.add(int(raw))
        except Exception:
            continue
    return Allowlist(allowed_user_ids=allowed)


