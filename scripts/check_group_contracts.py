"""Validate configured team APIs read-only before any load or fault injection."""

import json
from pathlib import Path

from chaos_lab.contracts import check_group


def main():
    report = check_group()
    folder = Path("chaos/results")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ("contracts-" + report["round"] + ".json")).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
