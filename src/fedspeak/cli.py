"""Command line entry point: `fedspeak` or `python -m fedspeak`.

  fedspeak                 run the analysis (same as `fedspeak run`)
  fedspeak run
  fedspeak fetch [--start-year 1993] [--end-year 2026] [--force]
                           download minutes and write their cleaned text to data/text
  fedspeak extract [--force]
                           rebuild data/text from the downloaded HTML
  fedspeak audit [--per-keyword 30]
                           build output/audit/audit.html, a page for labelling sampled hits
  fedspeak audit --labels <csv>
                           compare those labels with each scoring method
  fedspeak verify [sources|context]
                           sources: compare PDF and HTML text for every meeting that has both
                           context: score every hit with a word window and with sentences
"""

import argparse

from fedspeak.config import (
    END_DATE, FETCH_START_YEAR, HITS_CSV, KEYWORDS, MANIFEST_CSV, OUTPUT_CSV, SNIPPETS_PER_KEYWORD,
    START_DATE, TEXT_DIR,
)


def run():
    from fedspeak.dashboard import build_dashboard
    from fedspeak.pipeline import process_minutes
    from fedspeak.report import export_snippets, print_summary
    from fedspeak.stance import scorer_from_config

    stance = scorer_from_config()
    try:
        df, hits = process_minutes(TEXT_DIR, KEYWORDS, START_DATE, END_DATE, MANIFEST_CSV, stance=stance)
    finally:
        if stance:
            stance.close()

    if df.empty:
        print("No data to process. Exiting.")
        return

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    hits.to_csv(HITS_CSV, index=False)
    print(f"Saved {len(df)} meetings to {OUTPUT_CSV}")
    print(f"Saved {len(hits)} keyword hits to {HITS_CSV}\n")
    print(df[["date"] + KEYWORDS + [f"{kw}_sentiment" for kw in KEYWORDS]].to_string(index=False))

    build_dashboard(df, KEYWORDS)
    print_summary(df, KEYWORDS)

    # Most sentiment-charged snippets for every keyword, as a sanity check
    for kw in KEYWORDS:
        export_snippets(hits, kw, top_n=SNIPPETS_PER_KEYWORD)


def extract(force=False, dates=None):
    from fedspeak.extract import build_text_corpus

    written = build_text_corpus(MANIFEST_CSV, TEXT_DIR, dates=dates, force=force)
    print(f"Wrote {written} text files to {TEXT_DIR}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fedspeak", description="FOMC minutes keyword and sentiment analysis.")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="run the analysis on the minutes text (default)")
    fetch = sub.add_parser("fetch", help="download minutes from federalreserve.gov and extract their text")
    fetch.add_argument("--start-year", type=int, default=FETCH_START_YEAR)
    fetch.add_argument("--end-year", type=int, default=None, help="default: current year")
    fetch.add_argument("--force", action="store_true", help="download and extract again even if files exist")
    ext = sub.add_parser("extract", help="rebuild data/text from the downloaded HTML")
    ext.add_argument("--force", action="store_true", help="overwrite existing text files")
    aud = sub.add_parser("audit", help="build the human audit page, or score labels from it")
    aud.add_argument("--labels", help="labels CSV downloaded from the audit page; prints agreement per method")
    aud.add_argument("--per-keyword", type=int, default=None, help="hits sampled per keyword (default 30)")
    ver = sub.add_parser("verify", help="verification checks; results in output/verify/")
    ver.add_argument("check", nargs="?", default="sources", choices=["sources", "context"],
                     help="sources: PDF vs HTML text (default); context: window vs sentence scoring")
    args = parser.parse_args(argv)

    if args.command == "fetch":
        from fedspeak.fetch import fetch_minutes
        records = fetch_minutes(args.start_year, args.end_year, force=args.force)
        extract(force=args.force, dates={r.meeting_date for r in records})
    elif args.command == "extract":
        extract(force=args.force)
    elif args.command == "audit" and args.labels:
        from fedspeak.audit import score_audit
        score_audit(args.labels)
    elif args.command == "audit":
        from fedspeak.audit import AUDIT_PER_KEYWORD, build_audit
        path, n = build_audit(per_keyword=args.per_keyword or AUDIT_PER_KEYWORD)
        print(f"Audit page with {n} hits: {path}\nOpen it in a browser, label the hits, download the labels, then run:\n"
              f"  uv run fedspeak audit --labels <downloaded file>")
    elif args.command == "verify" and args.check == "context":
        from fedspeak.verify import VERIFY_DIR, compare_context_modes, print_context_summary
        print_context_summary(compare_context_modes())
        print(f"\nDetails: {VERIFY_DIR / 'context_modes.csv'}")
    elif args.command == "verify":
        from fedspeak.verify import VERIFY_DIR, compare_sources, print_comparison_summary
        print_comparison_summary(compare_sources())
        print(f"\nDetails: {VERIFY_DIR / 'pdf_vs_html.csv'}  Extracted text: {VERIFY_DIR / 'text'}")
    else:
        run()


if __name__ == "__main__":
    main()
