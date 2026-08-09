#!/usr/bin/env python3
"""Conservative, failure-isolated price updater for the static dashboard.

The official pricing pages are not stable APIs. Parsers therefore only update
known model rows when all expected values can be found and validated. Existing
prices are retained on HTTP, markup, parsing, or validation failures.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import math
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
PRICES_PATH = ROOT / "data" / "prices.json"
HISTORY_PATH = ROOT / "data" / "history.json"
TIMEOUT = (10, 35)
USER_AGENT = "ai-model-prices-dashboard/1.0 (+GitHub Actions; public pricing monitor)"
PRICE_FIELDS = ("input", "cached_input", "output")
LOG = logging.getLogger("price-updater")


@dataclass(frozen=True)
class ProviderSpec:
    provider_id: str
    url: str
    parser: Callable[[str], dict[str, dict[str, float]]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def money_values(text: str) -> list[float]:
    return [float(value.replace(",", "")) for value in re.findall(r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)", text)]


def normalized_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text.replace("\xa0", " ").replace("−", "-").replace("–", "-"))


def anchored_block(text: str, anchor: str, next_anchors: list[str], span: int = 2600) -> str:
    start = text.lower().find(anchor.lower())
    if start < 0:
        raise ValueError(f"missing anchor: {anchor}")
    end = min(len(text), start + span)
    tail = text[start + len(anchor) : end]
    for candidate in next_anchors:
        pos = tail.lower().find(candidate.lower())
        if pos >= 0:
            end = min(end, start + len(anchor) + pos)
    return text[start:end]


def parse_openai(text: str) -> dict[str, dict[str, float]]:
    models = [
        ("openai:gpt-5.6-sol", "GPT-5.6 Sol"),
        ("openai:gpt-5.6-terra", "GPT-5.6 Terra"),
        ("openai:gpt-5.6-luna", "GPT-5.6 Luna"),
    ]
    result = {}
    anchors = [name for _, name in models]
    for model_id, name in models:
        try:
            block = anchored_block(text, name, [a for a in anchors if a != name], 1800)
            match = re.search(
                r"Pricing.*?Input\s*\$\s*([0-9.]+).*?Cached Input\s*\$\s*([0-9.]+).*?Output\s*\$\s*([0-9.]+)",
                block,
                re.I,
            )
            if match:
                result[model_id] = dict(zip(PRICE_FIELDS, map(float, match.groups())))
        except ValueError:
            continue
    return result


def parse_anthropic(text: str) -> dict[str, dict[str, float]]:
    models = [
        ("anthropic:claude-opus-4.7", "Claude Opus 4.7"),
        ("anthropic:claude-sonnet-4.6", "Claude Sonnet 4.6"),
        ("anthropic:claude-haiku-4.5", "Claude Haiku 4.5"),
    ]
    result = {}
    anchors = [name for _, name in models]
    for model_id, name in models:
        try:
            block = anchored_block(text, name, [a for a in anchors if a != name], 2400)
            row_pos = re.search(r"Standard\s+(?:Global\s+)?(?:All|[≤<]=?\s*200K)", block, re.I)
            values = money_values(block[row_pos.start() :] if row_pos else block)
            # Current HTML table order: input, 5m write, 1h write, cache hit, output.
            if len(values) >= 5:
                result[model_id] = {"input": values[0], "cached_input": values[3], "output": values[4]}
        except ValueError:
            continue
    return result


def parse_google(text: str) -> dict[str, dict[str, float]]:
    models = [
        ("google:gemini-3.5-flash", "Gemini 3.5 Flash"),
        ("google:gemini-3-flash-preview", "Gemini 3 Flash Preview"),
        ("google:gemini-2.5-pro", "Gemini 2.5 Pro"),
    ]
    result = {}
    anchors = [name for _, name in models]
    for model_id, name in models:
        try:
            block = anchored_block(text, name, [a for a in anchors if a != name], 4200)
            standard = block[block.lower().find("standard") :]
            input_match = re.search(r"Input price[^$]{0,220}\$\s*([0-9.]+)", standard, re.I)
            output_match = re.search(r"Output price[^$]{0,220}\$\s*([0-9.]+)", standard, re.I)
            cache_match = re.search(r"Context caching price[^$]{0,240}\$\s*([0-9.]+)", standard, re.I)
            if input_match and output_match and cache_match:
                result[model_id] = {
                    "input": float(input_match.group(1)),
                    "cached_input": float(cache_match.group(1)),
                    "output": float(output_match.group(1)),
                }
        except ValueError:
            continue
    return result


def parse_xai(text: str) -> dict[str, dict[str, float]]:
    models = [
        ("xai:grok-4.5", "grok-4.5"),
        ("xai:grok-build-0.1", "grok-build-0.1"),
        ("xai:grok-4.3", "grok-4.3"),
    ]
    result = {}
    anchors = [anchor for _, anchor in models]
    for model_id, anchor in models:
        try:
            block = anchored_block(text, anchor, [a for a in anchors if a != anchor], 900)
            values = money_values(block)
            # The official row is short-context input/cached/output, then long-context equivalents.
            if len(values) >= 3:
                result[model_id] = dict(zip(PRICE_FIELDS, values[:3]))
        except ValueError:
            continue
    return result


def parse_deepseek(text: str) -> dict[str, dict[str, float]]:
    if "deepseek-v4-flash" not in text.lower() or "deepseek-v4-pro" not in text.lower():
        return {}
    match = re.search(
        r"INPUT TOKENS \(CACHE HIT\)\s*\$\s*([0-9.]+)\s*\$\s*([0-9.]+).*?"
        r"INPUT TOKENS \(CACHE MISS\)\s*\$\s*([0-9.]+)\s*\$\s*([0-9.]+).*?"
        r"OUTPUT TOKENS\s*\$\s*([0-9.]+)\s*\$\s*([0-9.]+)",
        text,
        re.I,
    )
    if not match:
        return {}
    flash_hit, pro_hit, flash_input, pro_input, flash_output, pro_output = map(float, match.groups())
    return {
        "deepseek:deepseek-v4-flash": {"input": flash_input, "cached_input": flash_hit, "output": flash_output},
        "deepseek:deepseek-v4-pro": {"input": pro_input, "cached_input": pro_hit, "output": pro_output},
    }


def parse_alibaba(text: str) -> dict[str, dict[str, float]]:
    models = [
        ("alibaba:qwen3.7-max", "qwen3.7-max"),
        ("alibaba:qwen3.6-flash", "qwen3.6-flash"),
        ("alibaba:qwen3.5-flash", "qwen3.5-flash"),
    ]
    result = {}
    all_anchors = [anchor for _, anchor in models]
    for model_id, anchor in models:
        try:
            block = anchored_block(text, anchor, [a for a in all_anchors if a != anchor], 2600)
            international = re.search(r"International.{0,700}", block, re.I)
            values = money_values(international.group(0) if international else block)
            if len(values) >= 2:
                # Alibaba documents cache hits as 10% of input for supported models.
                result[model_id] = {"input": values[0], "cached_input": values[0] * 0.1, "output": values[1]}
        except ValueError:
            continue
    return result


SPECS = [
    ProviderSpec("openai", "https://developers.openai.com/api/docs/models/compare", parse_openai),
    ProviderSpec("anthropic", "https://platform.claude.com/docs/en/about-claude/pricing", parse_anthropic),
    ProviderSpec("google", "https://ai.google.dev/gemini-api/docs/pricing", parse_google),
    ProviderSpec("xai", "https://docs.x.ai/developers/pricing", parse_xai),
    ProviderSpec("deepseek", "https://api-docs.deepseek.com/quick_start/pricing", parse_deepseek),
    ProviderSpec("alibaba", "https://www.alibabacloud.com/help/en/model-studio/model-pricing", parse_alibaba),
]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def atomic_json_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)


def fetch(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=TIMEOUT, headers={"Accept-Language": "en-US,en;q=0.9"})
    response.raise_for_status()
    if len(response.content) < 1000:
        raise ValueError(f"response unexpectedly short ({len(response.content)} bytes)")
    return normalized_text(response.text)


def valid_price_set(values: dict[str, float], old: dict) -> tuple[bool, str | None]:
    for field in PRICE_FIELDS:
        value = values.get(field)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or value > 10000:
            return False, f"invalid {field}={value!r}"
        previous = old.get(field)
        if previous and value:
            ratio = max(value / previous, previous / value)
            if ratio > 25:
                return False, f"suspicious {field} change factor {ratio:.1f}"
    if values["cached_input"] > values["input"] * 2:
        return False, "cached input exceeds 2x regular input"
    return True, None


def update(selected: set[str] | None = None, dry_run: bool = False) -> int:
    prices = load_json(PRICES_PATH)
    history = load_json(HISTORY_PATH)
    before_prices = copy.deepcopy(prices)
    before_history = copy.deepcopy(history)
    now = utc_now()
    model_index = {model["id"]: model for model in prices["models"]}
    provider_index = {provider["id"]: provider for provider in prices["providers"]}
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    changed_count = 0

    for spec in SPECS:
        if selected and spec.provider_id not in selected:
            continue
        provider = provider_index[spec.provider_id]
        provider["last_checked_at"] = now
        provider["source_url"] = spec.url
        try:
            text = fetch(session, spec.url)
            parsed = spec.parser(text)
            if not parsed:
                raise ValueError("parser returned no recognized model prices")
            accepted = 0
            rejected: list[str] = []
            for model_id, values in parsed.items():
                old = model_index.get(model_id)
                if old is None:
                    rejected.append(f"unknown model {model_id}")
                    continue
                ok, reason = valid_price_set(values, old)
                if not ok:
                    rejected.append(f"{model_id}: {reason}")
                    continue
                accepted += 1
                changes = {
                    field: {"from": old[field], "to": round(values[field], 9)}
                    for field in PRICE_FIELDS
                    if not math.isclose(float(old[field]), float(values[field]), rel_tol=0, abs_tol=1e-9)
                }
                if changes:
                    previous = {field: old[field] for field in PRICE_FIELDS}
                    for field in PRICE_FIELDS:
                        old[field] = round(values[field], 9)
                    old["updated_at"] = now
                    history["events"].append(
                        {
                            "timestamp": now,
                            "provider": spec.provider_id,
                            "model_id": model_id,
                            "changes": changes,
                            "previous": previous,
                            "current": {field: old[field] for field in PRICE_FIELDS},
                            "source_url": spec.url,
                        }
                    )
                    changed_count += 1
            if accepted == 0:
                raise ValueError("all parsed rows failed validation: " + "; ".join(rejected))
            provider["status"] = "ok" if not rejected else "partial"
            provider["last_success_at"] = now
            provider["error"] = "; ".join(rejected)[:500] or None
            LOG.info("%s: accepted %d row(s), rejected %d", spec.provider_id, accepted, len(rejected))
        except Exception as exc:  # provider failures must never stop other providers
            provider["status"] = "error"
            provider["error"] = f"{type(exc).__name__}: {exc}"[:500]
            LOG.warning("%s retained previous prices: %s", spec.provider_id, provider["error"])

    prices["last_checked_at"] = now
    if changed_count:
        prices["last_updated_at"] = now
    history["events"] = history.get("events", [])[-5000:]

    if dry_run:
        LOG.info("dry run: %d model price change(s); no files written", changed_count)
        return 0

    if prices != before_prices:
        atomic_json_write(PRICES_PATH, prices)
    if history != before_history:
        atomic_json_write(HISTORY_PATH, history)
    LOG.info("finished: %d model price change(s)", changed_count)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Update AI token pricing from official public pages.")
    parser.add_argument("--provider", action="append", choices=[spec.provider_id for spec in SPECS])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    try:
        return update(set(args.provider) if args.provider else None, args.dry_run)
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        LOG.error("fatal local data error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
