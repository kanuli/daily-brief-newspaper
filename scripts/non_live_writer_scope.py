"""Review the precise non-Live write sets required for a safe Publisher cutover."""
from datetime import date
from pathlib import PurePosixPath
import re

DAY = r"(\d{4}-\d{2}-\d{2})"
ARCHIVE_EDITION = r"editions/" + DAY + r"\.html"
DAILY_TOPIC = r"data/topic-more/" + DAY + r"\.json"
VOCAB = r"data/vocab/" + DAY + r"\.json"
KNOWN = {
    "daily-today-recovery.yml": ({"data/latest.json", "data/archive.json"}, (ARCHIVE_EDITION, DAILY_TOPIC)),
    "daily-archive-self-heal.yml": ({"data/archive.json"}, (ARCHIVE_EDITION,)),
    "daily-japanese-vocab.yml": ({"data/vocab/latest.json"}, (VOCAB,)),
    "stock-publication-maintenance.yml": ({"data/stocks-latest.json"}, ()),
}
MAX_PATHS = 128


def scope_review(workflow, files):
    """Inputs are Git metadata for a proposed exact transition, never a grant."""
    if workflow not in KNOWN or not 0 < len(files) <= MAX_PATHS:
        raise ValueError("unknown non-Live writer or empty/oversized proposed change")
    fixed, patterns = KNOWN[workflow]
    checked = set()
    for row in files:
        path = row["filename"]
        if (not isinstance(path, str) or PurePosixPath(path).as_posix() != path or path.startswith("/")
                or any(bit in {"", ".", ".."} for bit in path.split("/"))
                or row["status"] not in {"added", "modified"} or "previous_filename" in row
                or path.casefold() in checked):
            raise ValueError("non-Live change has an unsafe or ambiguous Git path")
        if path not in fixed:
            for pattern in patterns:
                match = re.fullmatch(pattern, path)
                if match:
                    date.fromisoformat(match[1])
                    break
            else:
                raise ValueError("file is outside the non-Live data scope: " + path)
        checked.add(path.casefold())
    return {"workflow": workflow, "confirmedProposedPaths": sorted(checked),
            "writeAuthorized": False, "liveMutationPermitted": False}
