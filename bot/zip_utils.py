from __future__ import annotations

import os
import zipfile
from pathlib import Path
from typing import Iterable


def zip_dir(
    *,
    src_dir: Path,
    dest_zip: Path,
    exclude_names: Iterable[str] = (),
) -> None:
    src_dir = src_dir.resolve()
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    exclude = set(exclude_names)

    with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(src_dir):
            root_path = Path(root)
            for fname in files:
                if fname in exclude:
                    continue
                fpath = root_path / fname
                # Job folders may contain symlinks created inside the container (mounted /workspace).
                # On the host these can be broken (e.g., pointing to /workspace), which breaks zipping.
                if fpath.is_symlink():
                    continue
                rel = fpath.relative_to(src_dir)
                zf.write(fpath, arcname=str(rel))


