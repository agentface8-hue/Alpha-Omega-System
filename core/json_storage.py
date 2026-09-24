"""Single-file JSON persistence. Does not make read/modify/write transactions atomic."""
import json
import os
import tempfile
from pathlib import Path


def atomic_write_json(path: Path, data) -> None:
    """Replace only after serialization and flush succeed; retain old file on failure."""
    path = Path(path)
    payload = json.dumps(data, indent=2, default=str)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
