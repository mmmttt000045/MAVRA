#!/usr/bin/env python3
"""Mirror the manuscript (overleaf/ of the main repo) into the paper repo icde-2027-paper.

overleaf/ is the single source. Read both entries and their \\input / \\includegraphics
dependencies directly, along with references.bib and build.sh. No ZIP is generated or read.
The paper repo's own README.md, .gitignore, .gitattributes, and remote-only files are retained.
Text files are written with LF.

The paper repo's origin/main must still be the commit recorded in
docs/development/paper-sync.json; otherwise someone (e.g. Overleaf) pushed edits that a sync
would overwrite: merge them into overleaf/ first, or pass --force.

    python3 tools/sync-paper-repo.py --repo <clone>                  # dry run
    python3 tools/sync-paper-repo.py --repo <clone> --apply          # write files
    python3 tools/sync-paper-repo.py --repo <clone> --apply --push   # + commit, push, record
"""
import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "overleaf"
RECORD = ROOT / "docs" / "development" / "paper-sync.json"
KEEP = {"README.md", ".gitignore", ".gitattributes"}  # owned by the paper repo
BINARY = {".pdf", ".png", ".jpg", ".zip"}


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def lf(rel: str, data: bytes) -> bytes:
    return data if Path(rel).suffix in BINARY else data.replace(b"\r\n", b"\n")


def manuscript_files() -> dict[str, bytes]:
    """Collect the compilation dependency closure without an archive."""
    files = {Path("references.bib"), Path("build.sh")}

    def checked(name: str, extension: str) -> Path:
        path = Path(name if Path(name).suffix else name + extension)
        if path.is_absolute() or ".." in path.parts:
            sys.exit(f"Dependency outside the paper directory: {path}")
        absolute = (SRC / path).resolve()
        if not absolute.is_relative_to(SRC.resolve()) or not absolute.is_file():
            sys.exit(f"Missing or external paper dependency: {path}")
        return path

    def collect(path: Path, stack: tuple[Path, ...] = ()) -> None:
        if path in stack:
            sys.exit(f"Circular paper input: {path}")
        if path in files:
            return
        files.add(path)
        source = (SRC / path).read_text(encoding="utf-8")
        for name in re.findall(r"\\input\{([^}]+)\}", source):
            collect(checked(name, ".tex"), (*stack, path))
        for name in re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", source):
            files.add(checked(name, ".pdf"))

    for entry in ("main.tex", "main-bilingual.tex"):
        collect(checked(entry, ".tex"))
    return {path.as_posix(): lf(path.as_posix(), (SRC / path).read_bytes())
            for path in sorted(files) if path.as_posix() not in KEEP}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--force", action="store_true", help="sync although the paper repo moved")
    a = ap.parse_args()
    dst = a.repo.resolve()
    if not (dst / ".git").exists():
        sys.exit(f"{dst} is not a git checkout")
    if a.push and not a.apply:
        sys.exit("--push needs --apply")
    if a.apply and git(dst, "status", "--porcelain"):
        sys.exit("paper checkout has local changes; preserve or commit them before syncing")

    record = json.loads(RECORD.read_text(encoding="utf-8"))
    git(dst, "fetch", "-q", "origin")
    remote = git(dst, "rev-parse", "origin/main")
    if remote != record["remote_commit"] and not a.force:
        print(git(dst, "log", "--oneline", f"{record['remote_commit']}..origin/main"))
        sys.exit("paper repo has commits since the last sync (listed above): merge them into "
                 "overleaf/ first, or rerun with --force")

    if a.apply:
        if git(dst, "branch", "--show-current") != "main":
            sys.exit("paper checkout must be on main before applying a sync")
        git(dst, "merge", "--ff-only", "origin/main")
    want = manuscript_files()

    have = set(git(dst, "ls-files").splitlines())
    changed = sorted(n for n in want if n in have and
                     (not (dst / n).is_file() or lf(n, (dst / n).read_bytes()) != want[n]))
    added = sorted(n for n in want if n not in have)
    preserved = sorted(have - set(want) - KEEP)
    for title, names in (("changed", changed), ("added", added), ("preserved", preserved)):
        print(f"{title} ({len(names)}):", *names, sep="\n  ")

    if not a.apply:
        return 0
    for n in changed + added:
        (dst / n).parent.mkdir(parents=True, exist_ok=True)
        (dst / n).write_bytes(want[n])

    if a.push:
        if changed or added:
            git(dst, "add", "--", *(changed + added))
        if subprocess.call(["git", "-C", str(dst), "diff", "--cached", "--quiet"]) == 0:
            print("paper repo already up to date")
            return 0
        head = git(ROOT, "rev-parse", "--short", "HEAD")
        git(dst, "commit", "-q", "-m", f"Sync manuscript from agent4db-adapter {head}")
        git(dst, "push", "-q", "origin", "HEAD:main")
        commit = git(dst, "rev-parse", "HEAD")
        record.update(
            date=datetime.date.today().isoformat(), status="pushed", previous_head=remote,
            remote_commit=commit, source_commit=git(ROOT, "rev-parse", "HEAD"),
            changed_paths=changed + added, deletions=[], preserve_remote_only=True,
            delivery_mode="github_only", source_package=None,
            commit_url=f"{record['repository_url']}/commit/{commit}",
        )
        record.pop("source_package_sha256", None)
        RECORD.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"pushed {commit}; recorded in {RECORD.relative_to(ROOT)} (commit that file)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
