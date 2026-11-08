"""Command line entry point: `fedspeak` or `python -m fedspeak`."""

from fedspeak.config import KEYWORDS, OUTPUT_CSV, PDF_DIR
from fedspeak.dashboard import build_dashboard
from fedspeak.pipeline import process_pdfs
from fedspeak.report import export_snippets, print_summary


def main():
    df, all_snippets = process_pdfs(PDF_DIR, KEYWORDS)

    if df.empty:
        print("No data to process. Exiting.")
        return

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved to {OUTPUT_CSV}\n")
    print(df[["date"] + KEYWORDS + [f"{kw}_sentiment" for kw in KEYWORDS]].to_string(index=False))

    build_dashboard(df, KEYWORDS)
    print_summary(df, KEYWORDS)

    # Inspect top snippets for a keyword of interest
    export_snippets(all_snippets, "uncertainty", top_n=10)


if __name__ == "__main__":
    main()
