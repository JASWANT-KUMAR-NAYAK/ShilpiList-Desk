"""Run the fixed evaluation set and write eval/results.csv.

eval/test_set.csv columns: id, craft, material, dimensions, images (semicolon-separated paths)
material and dimensions may be left empty; fill in the real facts for a fair test.
Run the same file twice, once per model (baseline vs fine-tuned), by changing LLM_MODEL.
Usage: LLM_MODEL=gemma4 python -m eval.run_eval --label baseline
"""
import argparse
import csv
import statistics
from pathlib import Path

from app import llm
from app.main import _validate_content
from app.prompts import build_prompt
from app.scoring import score_listing
from scripts.day1_check import load_small


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True, help="e.g. baseline or tuned")
    ap.add_argument("--set", default="eval/test_set.csv")
    args = ap.parse_args()

    rows_out = []
    with open(args.set, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            paths = [p for p in row["images"].split(";") if p]
            prompt = build_prompt(row, "simple")
            try:
                content, meta = llm.generate(prompt, [load_small(p) for p in paths])
                scores = score_listing(_validate_content(content), row["craft"])
                ok = True
            except Exception as e:  # keep going; failures are part of the result
                meta, scores, ok = {"latency_ms": None}, {}, False
                print(f"{row['id']}: failed: {e}")
            rows_out.append({"id": row["id"], "craft": row["craft"], "ok": ok,
                             "latency_ms": meta.get("latency_ms"), **scores})

    out = Path(f"eval/results_{args.label}.csv")
    if rows_out:
        keys = sorted({k for r in rows_out for k in r})
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows_out)
    done = [r for r in rows_out if r["ok"]]
    print(f"{len(done)}/{len(rows_out)} valid listings")
    for lang in ("en", "hi", "or"):
        shares = [r[f"{lang}_script_share"] for r in done]
        hits = [r[f"{lang}_term_hit"] for r in done]
        if shares:
            print(f"{lang}: mean script share {statistics.mean(shares):.2f}, "
                  f"glossary hit rate {sum(hits) / len(hits):.0%}")
    lat = [r["latency_ms"] for r in done if r["latency_ms"]]
    if lat:
        print(f"median latency {statistics.median(lat) / 1000:.1f}s")


if __name__ == "__main__":
    main()
