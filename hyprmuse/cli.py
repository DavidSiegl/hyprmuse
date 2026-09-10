"""Command line interface for hyprmuse."""

import argparse
import sys

from . import config, library, render, select
from .sources import AUTO_ORDER, REGISTRY, SourceError, get_source
from .sources.base import Candidate


def _err(msg: str) -> int:
    print(f"hyprmuse: {msg}", file=sys.stderr)
    return 1


def _progress(msg: str) -> None:
    print(f"  {msg}", file=sys.stderr)


def _gather(query: str, source: str, lang: str) -> list[Candidate]:
    """Candidates from one named source, or from every source in auto order."""
    names = [source] if source else AUTO_ORDER
    found: list[Candidate] = []
    for name in names:
        try:
            hits = get_source(name).search(query, lang)
        except SourceError as exc:
            if source:
                raise
            print(f"  ({name} unavailable: {exc})", file=sys.stderr)
            continue
        found.extend(hits)
        if source:
            break
    return found


def _choose(cands: list[Candidate], assume_yes: bool) -> Candidate | None:
    if not cands:
        return None
    if assume_yes or len(cands) == 1 or not sys.stdin.isatty():
        return cands[0]
    print("\nMatches:", file=sys.stderr)
    for i, c in enumerate(cands, 1):
        hint = f"  ({c.hint})" if c.hint else ""
        print(f"  {i:2}. [{c.source}/{c.domain}] {c.name}{hint}", file=sys.stderr)
    try:
        raw = input("\nPick a number (blank to cancel): ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not raw.isdigit() or not 1 <= int(raw) <= len(cands):
        return None
    return cands[int(raw) - 1]


def cmd_search(args) -> int:
    cands = _gather(args.query, args.source, args.lang)
    if not cands:
        return _err(f"no matches for {args.query!r}")
    for c in cands:
        hint = f"  ({c.hint})" if c.hint else ""
        print(f"[{c.source}/{c.domain}] {c.name}{hint}\n    {c.source}:{c.source_id}")
    return 0


def cmd_add(args) -> int:
    try:
        cands = _gather(args.query, args.source, args.lang)
    except SourceError as exc:
        return _err(str(exc))
    cand = _choose(cands, args.yes)
    if cand is None:
        return _err(f"no match chosen for {args.query!r}")
    print(f"Harvesting {cand.name} from {cand.source}…", file=sys.stderr)
    try:
        subject = get_source(cand.source).fetch(cand, _progress)
    except SourceError as exc:
        return _err(str(exc))
    path = library.save(subject)
    print(f"Saved {len(subject.items)} items for {subject.name} -> {path}")
    return 0


def cmd_list(args) -> int:
    subjects = library.load_all()
    if not subjects:
        print("No subjects yet. Try: hyprmuse add \"Franz Kafka\"")
        return 0
    width = max(len(s.name) for s in subjects)
    total = 0
    for s in subjects:
        total += len(s.items)
        kind = "atomic" if s.items and s.items[0].atomic else "sliceable"
        print(f"{s.name:{width}}  {len(s.items):5} items  {s.domain:11} "
              f"{s.lang:3} {kind:10} {library.subject_key(s.source, s.source_id)}")
    print(f"\n{len(subjects)} subjects, {total} items total")
    return 0


def cmd_remove(args) -> int:
    matches = library.find(args.token)
    if not matches:
        return _err(f"no subject matching {args.token!r}")
    if len(matches) > 1:
        names = ", ".join(library.subject_key(m.source, m.source_id) for m in matches)
        return _err(f"{args.token!r} is ambiguous: {names}")
    subject = matches[0]
    library.remove(subject)
    print(f"Removed {subject.name}")
    return 0


def cmd_update(args) -> int:
    targets = library.load_all() if args.all else library.find(args.token or "")
    if not targets:
        return _err("nothing to update")
    failed = 0
    for subj in targets:
        cand = Candidate(source=subj.source, source_id=subj.source_id,
                         name=subj.name, domain=subj.domain, lang=subj.lang,
                         url=subj.url)
        print(f"Updating {subj.name} ({subj.source})…", file=sys.stderr)
        try:
            fresh = get_source(subj.source).fetch(cand, _progress)
        except SourceError as exc:
            print(f"  failed: {exc}", file=sys.stderr)
            failed += 1
            continue
        library.save(fresh)
        print(f"  {len(fresh.items)} items")
    return 1 if failed and failed == len(targets) else 0


def cmd_sources(args) -> int:
    for name in AUTO_ORDER:
        src = REGISTRY[name]
        kind = "atomic" if src.produces_atomic else "sliceable"
        print(f"{name:11} {src.domain:11} {kind}")
    return 0


def cmd_quote(args) -> int:
    cfg = config.load_config()
    num_lines = args.lines if args.lines is not None else cfg["lines"]
    width = args.width if args.width is not None else cfg["width"]
    max_lines = args.max_lines if args.max_lines is not None else cfg["max_lines"]
    max_chars = args.max_chars if args.max_chars is not None else cfg["max_chars"]

    fit = select.Fit(width=width, max_lines=max_lines, max_chars=max_chars)
    chosen = select.pick(cfg, num_lines=num_lines, subject=args.subject,
                         domain=args.domain, source=args.source, seed=args.seed,
                         fit=fit)
    if chosen is None:
        print("No quotes stored yet — run: hyprmuse add \"Franz Kafka\"")
        return 0
    print(render.render(chosen, width=width, max_lines=max_lines,
                        show_note=args.note))
    return 0



def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hyprmuse",
        description="Random quotes from musicians, authors and poets, for hyprlock.")
    sub = p.add_subparsers(dest="cmd")

    def add_search_flags(sp):
        sp.add_argument("--source", default="", choices=sorted(REGISTRY) + [""],
                        help="restrict to one source (default: try all)")
        sp.add_argument("--lang", default="en",
                        help="language edition, for wikiquote (e.g. de)")

    sp = sub.add_parser("add", help="harvest a new subject")
    sp.add_argument("query")
    add_search_flags(sp)
    sp.add_argument("--yes", "-y", action="store_true",
                    help="take the best match without prompting")
    sp.set_defaults(func=cmd_add)

    sp = sub.add_parser("search", help="look up subjects without harvesting")
    sp.add_argument("query")
    add_search_flags(sp)
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("list", help="show stored subjects")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("remove", help="delete a stored subject")
    sp.add_argument("token", help="source:id or part of the name")
    sp.set_defaults(func=cmd_remove)

    sp = sub.add_parser("update", help="re-harvest stored subjects")
    sp.add_argument("token", nargs="?", default="")
    sp.add_argument("--all", action="store_true")
    sp.set_defaults(func=cmd_update)

    sp = sub.add_parser("sources", help="list available sources")
    sp.set_defaults(func=cmd_sources)


    sp = sub.add_parser("quote", help="print a random quote (default command)")
    sp.add_argument("--lines", type=int, default=None,
                    help="lines to take from sliceable items")
    sp.add_argument("--width", type=int, default=None, help="wrap width, 0 disables")
    sp.add_argument("--max-lines", type=int, default=None,
                    help="most lines after wrapping; shorter picks are preferred")
    sp.add_argument("--max-chars", type=int, default=None,
                    help="most characters after wrapping, 0 disables")
    sp.add_argument("--subject", default="", help="restrict to one subject")
    sp.add_argument("--domain", default="", help="restrict to a domain")
    sp.add_argument("--source", default="", help="restrict to a source")
    sp.add_argument("--note", action="store_true", help="include the citation note")
    sp.add_argument("--seed", type=int, default=None, help="deterministic pick")
    sp.set_defaults(func=cmd_quote)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    # Bare `hyprmuse` prints a quote, so hyprlock can call it with no arguments.
    if not argv or (argv[0].startswith("-") and argv[0] not in ("-h", "--help")):
        argv.insert(0, "quote")
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except SourceError as exc:
        return _err(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
