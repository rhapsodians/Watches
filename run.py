#!/usr/bin/env python3
"""
WatchBot — UK pre-owned watch market search automation.

Usage:
  python run.py search [--dry-run] [--ref REFERENCE]
  python run.py verify --brand BRAND --ref REFERENCE
  python run.py verify --url RETAIL_URL
"""
from __future__ import annotations
import argparse
import logging
import sys
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("watchbot")


def cmd_search(args) -> None:
    from watchbot.config_loader import load_watches, load_settings
    from watchbot.state import ListingStore
    from watchbot.runner import SearchRunner, build_scrapers
    from watchbot.reporter import generate_report
    from watchbot.notifier import send_email

    settings = load_settings()
    watches = load_watches()

    if args.ref:
        watches = [w for w in watches if w.reference == args.ref]
        if not watches:
            logger.error("Reference '%s' not found in config/watches.yaml", args.ref)
            sys.exit(1)

    store = ListingStore(settings["state"]["db_path"])
    store.prune_stale(settings["state"]["listing_ttl_days"])

    scrapers = build_scrapers(settings)
    runner = SearchRunner(scrapers, store, dry_run=args.dry_run)

    logger.info("Starting search for %d watch(es) across %d sources", len(watches), len(scrapers))
    results = runner.run(watches)

    total = sum(len(r.listings) for r in results)
    new = sum(len(r.new_listings) for r in results)
    exact_new = sum(sum(1 for l in r.new_listings if l.is_exact_ref_match) for r in results)

    logger.info("Done — %d total listing(s), %d new, %d exact ref matches", total, new, exact_new)

    html = generate_report(results, settings["reporting"]["output_dir"])
    logger.info("Report written to %s/", settings["reporting"]["output_dir"])

    store.log_run(len(watches), total, new, "; ".join(e for r in results for e in r.errors))
    store.close()

    if not args.dry_run:
        send_email(html, results, settings["notifications"]["email"])
    else:
        logger.info("Dry run — email not sent.")


def cmd_verify(args) -> None:
    from watchbot.verifier import verify_reference, verify_from_url
    if hasattr(args, "url") and args.url:
        verify_from_url(args.url)
    else:
        if not args.brand or not args.ref:
            print("Error: --brand and --ref are required for verify.")
            sys.exit(1)
        verify_reference(args.brand, args.ref)


def main() -> None:
    parser = argparse.ArgumentParser(description="WatchBot — UK pre-owned watch search")
    sub = parser.add_subparsers(dest="command")

    # search subcommand
    p_search = sub.add_parser("search", help="Run daily search")
    p_search.add_argument("--dry-run", action="store_true", help="Don't send email or write state")
    p_search.add_argument("--ref", help="Search only this reference number")

    # verify subcommand
    p_verify = sub.add_parser("verify", help="Verify a watch reference before adding to config")
    p_verify.add_argument("--brand", help="Brand name")
    p_verify.add_argument("--ref", help="Manufacturer reference number")
    p_verify.add_argument("--url", help="Retail product URL to resolve")

    args = parser.parse_args()

    if args.command == "search":
        cmd_search(args)
    elif args.command == "verify":
        cmd_verify(args)
    else:
        # Default to search if no subcommand given
        args.dry_run = False
        args.ref = None
        cmd_search(args)


if __name__ == "__main__":
    main()
