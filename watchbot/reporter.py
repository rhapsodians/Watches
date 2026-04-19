from __future__ import annotations
import os
from datetime import datetime, date
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from watchbot.models import SearchResult


def generate_report(results: list[SearchResult], output_dir: str = "reports") -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    run_dt = datetime.utcnow()
    run_date = run_dt.strftime("%Y-%m-%d")
    run_time = run_dt.strftime("%H:%M")

    total_listings = sum(len(r.listings) for r in results)
    total_new = sum(len(r.new_listings) for r in results)
    total_exact_new = sum(
        sum(1 for l in r.new_listings if l.is_exact_ref_match)
        for r in results
    )

    # Pre-compute seen (non-new) listings for each result so the template doesn't need custom filters
    for result in results:
        new_keys = {l.dedup_key for l in result.new_listings}
        result.seen_listings = [l for l in result.listings if l.dedup_key not in new_keys]

    env = Environment(
        loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates")),
        autoescape=True,
    )

    # Add a custom filter so Jinja2 can check membership
    def not_in_filter(value, collection):
        return value not in collection

    env.filters["not_in"] = not_in_filter

    tmpl = env.get_template("report.html.j2")
    html = tmpl.render(
        run_date=run_date,
        run_time=run_time,
        results=results,
        total_listings=total_listings,
        total_new=total_new,
        total_exact_new=total_exact_new,
    )

    out_path = os.path.join(output_dir, f"{run_date}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    return html
