#!/usr/bin/env python3
"""Create an MDD-collector project from the skill's template.

    python init_project.py <project dir> --out-folder "<where to save the MDDs>"
        [--owner "Name / firm"] [--funds-workbook <path>] [--exclude REGEX]
        [--schedule "Mondays 07:00 (Windows Task Scheduler)"] [--example-registry]

Copies the collector code, Windows scripts, an empty source registry, HANDOVER.md and CLAUDE.md into the
project, plus the skill's reference notes into docs/. With --example-registry the 192-fund example
registry is copied to config/mdd_sources_example.yaml so entries can be lifted from it. Never overwrites
an existing HANDOVER.md, CLAUDE.md or config/mdd_sources.yaml: an existing project keeps its memory and
fund list, and only the code is refreshed.
"""

from __future__ import annotations

import argparse
import shutil
from datetime import date
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL / "assets" / "project"
KEEP_IF_PRESENT = {"HANDOVER.md", "CLAUDE.md", "config/mdd_sources.yaml"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--out-folder", required=True, help="folder the owner chose for the MDDs and trackers")
    ap.add_argument("--owner", default="(fill in)")
    ap.add_argument("--funds-workbook", default="none")
    ap.add_argument("--exclude", default="none")
    ap.add_argument("--schedule", default="not set up yet (see docs/scheduling.md)")
    ap.add_argument("--example-registry", action="store_true")
    args = ap.parse_args()

    dest = Path(args.project).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    kept, written = [], []
    for src in sorted(TEMPLATE.rglob("*")):
        if src.is_dir() or "__pycache__" in src.parts:
            continue
        rel = src.relative_to(TEMPLATE).as_posix()
        target = dest / rel
        if rel in KEEP_IF_PRESENT and target.exists():
            kept.append(rel)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        written.append(rel)
    for ref in ("manager-notes.md", "registry-fields.md", "tracker-and-checks.md", "scheduling.md"):
        shutil.copyfile(SKILL / "references" / ref, dest / "docs" / ref)
    if args.example_registry:
        shutil.copyfile(SKILL / "assets" / "sa_mdd_sources_example.yaml", dest / "config" / "mdd_sources_example.yaml")

    handover = dest / "HANDOVER.md"
    if "HANDOVER.md" in written:
        text = handover.read_text(encoding="utf-8")
        for key, value in {"OWNER": args.owner, "PROJECT_DIR": str(dest), "OUT_FOLDER": args.out_folder,
                           "FUNDS_WORKBOOK": args.funds_workbook, "EXCLUDE": args.exclude,
                           "SCHEDULE": args.schedule, "DATE": date.today().isoformat()}.items():
            text = text.replace("{{" + key + "}}", value)
        handover.write_text(text, encoding="utf-8")
    (dest / "logs").mkdir(exist_ok=True)
    print(f"project: {dest}")
    print(f"  written: {len(written)} files" + (f"; kept existing: {', '.join(kept)}" if kept else ""))
    print(f"  MDD folder: {args.out_folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
