"""Portal Inmobiliario rental scraper — pipeline entry point.

  python main.py ids     --region metropolitana          # stage 1: listing IDs + card prices
  python main.py ids     --commune providencia nunoa
  python main.py details                                  # stage 2: new listings from the latest IDs file
  python main.py details --ids-file data/raw/listing_ids_....csv --limit 20
  python main.py run     --region metropolitana          # stage 1 then stage 2
  python main.py export                                   # rebuild details.csv from details.jsonl
  python main.py clean                                    # stage 3: details.csv -> data/clean/listings_clean.csv
"""

import argparse
import sys

import clean
import collect_ids
import config
import fetch_details


def _add_targets(p: argparse.ArgumentParser) -> None:
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--region", help=f"Region to scrape. Valid options: {', '.join(config.REGIONS)}")
    g.add_argument("--commune", nargs="+", metavar="SLUG",
                   help="One or more commune slugs (e.g. las-condes providencia nunoa).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Portal Inmobiliario rental scraper.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ids = sub.add_parser("ids", help="Stage 1: collect listing IDs and card prices.")
    _add_targets(p_ids)

    p_det = sub.add_parser("details", help="Stage 2: fetch detail pages for listings not yet scraped.")
    p_det.add_argument("--ids-file", help="Stage-1 CSV to read (default: the latest one).")
    p_det.add_argument("--limit", type=int, help="Fetch at most N listings (for testing).")

    p_run = sub.add_parser("run", help="Stage 1 followed by stage 2.")
    _add_targets(p_run)
    p_run.add_argument("--limit", type=int, help="Stage 2: fetch at most N listings.")

    sub.add_parser("export", help="Rebuild details.csv from details.jsonl.")
    sub.add_parser("clean", help="Stage 3: clean details.csv into data/clean/listings_clean.csv.")

    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass

    args = parser.parse_args()

    if args.command in ("ids", "run"):
        try:
            communes, regions = config.resolve_targets(args.region, args.commune)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        ids_file = collect_ids.run(communes, regions)
        if args.command == "run":
            fetch_details.run(ids_file, args.limit)
    elif args.command == "details":
        fetch_details.run(args.ids_file, args.limit)
    elif args.command == "export":
        fetch_details.export_csv()
    elif args.command == "clean":
        try:
            clean.run()
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
