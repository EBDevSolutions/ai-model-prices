#!/usr/bin/env python3
"""Supplement benchmark coverage with exact raw rows published by BenchLM.

Official vendor/model-card evidence always wins. BenchLM is used only when an
exact provider + model identity match exists and verified, non-generated rows
are present. An ``estimated`` BenchAlign position does not invalidate its raw
verified rows; the label and uncertainty are retained on the category summary.
"""

from __future__ import annotations

import copy
import json
import logging
import re
import tempfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
PRICES_PATH = ROOT / "data" / "prices.json"
BENCHMARKS_PATH = ROOT / "data" / "benchmarks.json"
SOURCE_URL = "https://benchlm.ai/data/models.json"
TIMEOUT = (10, 60)
USER_AGENT = "ai-model-prices-dashboard/2.1 (+GitHub Actions; benchmark attribution)"
LOG = logging.getLogger("benchmark-updater")

PROVIDER_CREATORS = {
    "openai": {"openai"},
    "anthropic": {"anthropic"},
    "google": {"google", "google deepmind"},
    "xai": {"xai"},
    "deepseek": {"deepseek"},
    "alibaba": {"alibaba", "alibaba cloud", "qwen"},
    "moonshot": {"moonshot ai", "moonshot"},
}

# Only directly comparable benchmark names are mapped. In particular,
# LiveCodeBench Pro is not silently relabelled as LiveCodeBench.
RAW_SCORE_PATHS = {
    "mmlu_pro": (("knowledge", "mmluPro"),),
    "gpqa_diamond": (("knowledge", "gpqaDiamond"), ("knowledge", "gpqa")),
    "hle_no_tools": (("knowledge", "hleNoTools"),),
    "livecodebench": (("coding", "liveCodeBench"),),
    "livecodebench_pro": (("coding", "liveCodeBenchPro"),),
    "swe_bench_verified": (("coding", "sweVerified"),),
    "swe_bench_pro": (("coding", "swePro"),),
    "terminal_bench": (("coding", "terminalBench2"), ("agentic", "terminalBench2")),
    "frontier_swe": (("coding", "frontierSwe"),),
    "browsecomp": (("agentic", "browseComp"),),
    "osworld_verified": (("agentic", "osWorldVerified"),),
    "tau2_bench": (("agentic", "tau2Bench"),),
}

EXPLICIT_ALIASES = {
    "moonshot:kimi-k3": "kimi-3",
}


def slug(value: str) -> str:
    value = value.casefold().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def creator_matches(price_model: dict, bench_model: dict) -> bool:
    expected = PROVIDER_CREATORS.get(price_model.get("provider"), set())
    return slug(bench_model.get("creator", "")) in {slug(item) for item in expected}


def find_bench_model(price_model: dict, by_key: dict[str, dict]) -> dict | None:
    explicit = EXPLICIT_ALIASES.get(price_model.get("id", ""))
    candidates = [explicit, slug(price_model.get("model_id", "")), slug(price_model.get("name", ""))]
    for candidate in candidates:
        bench_model = by_key.get(candidate or "")
        if bench_model and creator_matches(price_model, bench_model):
            return bench_model
    return None


def raw_score(bench_model: dict, paths: tuple[tuple[str, str], ...]) -> float | None:
    benchmarks = bench_model.get("benchmarks") or {}
    for category, key in paths:
        value = (benchmarks.get(category) or {}).get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def is_benchlm_evidence(record: dict, benchmark_id: str) -> bool:
    evidence = (record.get("score_sources") or {}).get(benchmark_id) or {}
    return str(evidence.get("source_url", "")).startswith("https://benchlm.ai/")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    prices = load_json(PRICES_PATH)
    original = load_json(BENCHMARKS_PATH)
    updated = copy.deepcopy(original)

    response = requests.get(SOURCE_URL, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    response.raise_for_status()
    source = response.json()
    items = source.get("items")
    if not isinstance(items, list) or len(items) < 100:
        raise RuntimeError("BenchLM models.json is incomplete; keeping existing benchmark data")

    eligible = []
    for item in items:
        coverage = item.get("coverage") or {}
        if (
            (coverage.get("verifiedBenchmarkCount") or 0) > 0
            and (coverage.get("generatedBenchmarkCount") or 0) == 0
        ):
            eligible.append(item)

    by_key: dict[str, dict] = {}
    for item in eligible:
        for key in (item.get("slug"), item.get("canonicalModelKey")):
            if key:
                by_key[slug(str(key))] = item

    models = updated.setdefault("models", {})
    matched = imported = 0
    benchmark_ids = [item["id"] for item in updated.get("benchmarks", [])]

    for price_model in prices.get("models", []):
        bench_model = find_bench_model(price_model, by_key)
        if not bench_model:
            continue
        matched += 1
        direct_scores = {
            benchmark_id: raw_score(bench_model, paths)
            for benchmark_id, paths in RAW_SCORE_PATHS.items()
        }
        record = models.setdefault(
            price_model["id"],
            {
                "scores": {benchmark_id: None for benchmark_id in benchmark_ids},
                "conditions": "Raw benchmark rows aggregated by BenchLM; see the model evidence page.",
                "source_url": bench_model["url"],
                "source_type": "independent_aggregator",
            },
        )
        record.setdefault("scores", {})
        record.setdefault("score_sources", {})
        for benchmark_id in benchmark_ids:
            record["scores"].setdefault(benchmark_id, None)

        for benchmark_id, value in direct_scores.items():
            if value is None:
                continue
            current = record["scores"].get(benchmark_id)
            # Fill missing cells and refresh only cells already owned by BenchLM.
            if current is not None and not is_benchlm_evidence(record, benchmark_id):
                continue
            label = next(
                (item["label"] for item in updated.get("benchmarks", []) if item["id"] == benchmark_id),
                benchmark_id,
            )
            record["scores"][benchmark_id] = value
            record["score_sources"][benchmark_id] = {
                "source_url": bench_model["url"],
                "source_type": "independent_aggregator",
                "conditions": (
                    f"{label}; raw BenchLM row for {bench_model['model']}. "
                    f"Evidence: {bench_model['evidenceStatus']}; verified rows for model: "
                    f"{bench_model['coverage']['verifiedBenchmarkCount']}."
                ),
            }
            imported += 1

        bench_scores = bench_model.get("scores") or {}
        coverage = bench_model.get("coverage") or {}
        verified_categories = bench_scores.get("verifiedDisplayCategoryScores") or {}
        interval = bench_model.get("scoreInterval90") or {}
        record["benchlm_summary"] = {
            "overall": bench_scores.get("verifiedDisplayScore"),
            "categories": {
                "coding": verified_categories.get("coding"),
                "agentic": verified_categories.get("agentic"),
                "knowledge": verified_categories.get("knowledge"),
                "reasoning": verified_categories.get("reasoning"),
            },
            "evidence_status": bench_model.get("evidenceStatus"),
            "score_confidence": coverage.get("scoreConfidence"),
            "verified_benchmark_count": coverage.get("verifiedBenchmarkCount"),
            "interval_90": {"lower": interval.get("lower"), "upper": interval.get("upper")},
            "source_url": bench_model.get("url"),
            "model_key": bench_model.get("canonicalModelKey"),
        }

    updated["benchlm"] = {
        "source_url": SOURCE_URL,
        "dataset_url": "https://benchlm.ai/data",
        "license": "MIT",
        "generated_at": source.get("generatedAt"),
        "source_last_updated": source.get("sourceLastUpdated"),
        "policy": "Exact provider/model matches; verified non-generated rows; raw named benchmarks plus clearly labelled verified category summaries; vendor evidence has priority.",
        "matched_models": matched,
    }

    if updated == original:
        LOG.info("BenchLM build unchanged; no file update needed")
        return 0
    save_json_atomic(BENCHMARKS_PATH, updated)
    LOG.info("Matched %s models and processed %s raw score cells", matched, imported)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
