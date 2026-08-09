#!/usr/bin/env python3
"""Discover and update AI token prices from official public pricing tables.

The sources are web pages, not stable machine APIs. Every provider is isolated:
a failed or incomplete parser never deletes working prices. Newly listed models
are added automatically; models missing from three complete scans are retained
but marked as not listed.
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
from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).resolve().parents[1]
PRICES_PATH = ROOT / "data" / "prices.json"
HISTORY_PATH = ROOT / "data" / "history.json"
TIMEOUT = (10, 40)
USER_AGENT = "ai-model-prices-dashboard/2.0 (+GitHub Actions; public pricing monitor)"
PRICE_FIELDS = ("input", "cached_input", "output")
MISSING_LIMIT = 3
LOG = logging.getLogger("price-updater")


@dataclass(frozen=True)
class Page:
    html: str
    text: str


@dataclass(frozen=True)
class ProviderSpec:
    provider_id: str
    url: str
    minimum_models: int
    parser: Callable[[Page], dict[str, dict]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def money_values(text: str) -> list[float]:
    return [float(value.replace(",", "")) for value in re.findall(r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)", text)]


def first_money(text: str) -> float | None:
    values = money_values(text)
    return values[0] if values else None


def normalized_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text.replace("\xa0", " ").replace("−", "-").replace("–", "-"))


def clean_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def slugify(value: str) -> str:
    value = value.lower().replace("≤", "-").replace("≥", "-")
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-")


def title_from_id(model_id: str) -> str:
    parts = model_id.replace("_", "-").split("-")
    rendered = []
    for part in parts:
        lower = part.lower()
        if lower in {"gpt", "tts", "api", "vl", "omni"}:
            rendered.append(lower.upper())
        elif lower == "qwen":
            rendered.append("Qwen")
        elif lower == "grok":
            rendered.append("Grok")
        else:
            rendered.append(part.capitalize() if part.isalpha() else part)
    return " ".join(rendered)


def model_record(
    provider: str,
    model_id: str,
    name: str,
    input_price: float,
    cached_price: float | None,
    output_price: float,
    tier: str,
    context_note: str,
    availability: str = "active",
    price_comparable: bool = True,
) -> tuple[str, dict]:
    canonical = slugify(model_id)
    local_id = f"{provider}:{canonical}"
    cached = input_price if cached_price is None else cached_price
    return local_id, {
        "id": local_id,
        "provider": provider,
        "name": clean_space(name),
        "model_id": canonical,
        "input": float(input_price),
        "cached_input": float(cached),
        "output": float(output_price),
        "tier": tier,
        "context_note": clean_space(context_note)[:240],
        "availability": availability,
        "active": availability not in {"retired", "not_listed"},
        "price_comparable": price_comparable,
    }


def table_rows(table: Tag) -> list[list[str]]:
    return [
        [clean_space(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
        for row in table.find_all("tr")
    ]


def parse_openai(page: Page) -> dict[str, dict]:
    soup = BeautifulSoup(page.html, "html.parser")
    result: dict[str, dict] = {}

    # The first flagship table is the Standard, short-context table. Later
    # siblings contain Batch, Flex and Fast rates for the same models.
    flagship = None
    category = None
    for table in soup.find_all("table"):
        rows = table_rows(table)
        header = " | ".join(rows[1] if len(rows) > 1 and rows[0] and rows[0][0] == "" else rows[0]) if rows else ""
        if flagship is None and all(label in header for label in ("Model", "Input", "Cached input", "Cache writes", "Output")):
            flagship = rows
        if category is None and header.startswith("Category | Model | Input | Cached input | Output"):
            category = rows

    if flagship:
        for cells in flagship:
            if len(cells) < 5 or not re.fullmatch(r"(?:gpt|o)[a-z0-9._-]+", cells[0], re.I):
                continue
            input_price, cached_price, output_price = first_money(cells[1]), first_money(cells[2]), first_money(cells[4])
            if input_price is None or output_price is None:
                continue
            item_id, item = model_record(
                "openai", cells[0], title_from_id(cells[0]), input_price, cached_price, output_price,
                "standard · short context", "Standard API token pricing; long-context rates may differ."
            )
            result[item_id] = item

    if category:
        for cells in category:
            if len(cells) < 5 or cells[0] in {"Category", ""}:
                continue
            input_price, cached_price, output_price = first_money(cells[2]), first_money(cells[3]), first_money(cells[4])
            if input_price is None or output_price is None:
                continue
            model_id = cells[1]
            item_id, item = model_record(
                "openai", model_id, title_from_id(model_id), input_price, cached_price, output_price,
                "standard", f"{cells[0]} model; first listed text-token rate."
            )
            result[item_id] = item
    return result


def _date_qualified_name(name: str) -> tuple[str, bool]:
    match = re.search(r"\s+(through|starting)\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})$", name)
    if not match:
        return name, True
    boundary = datetime.strptime(match.group(2), "%B %d, %Y").date()
    today = datetime.now(timezone.utc).date()
    eligible = today <= boundary if match.group(1) == "through" else today >= boundary
    return name[: match.start()], eligible


def parse_anthropic(page: Page) -> dict[str, dict]:
    soup = BeautifulSoup(page.html, "html.parser")
    result: dict[str, dict] = {}
    pricing_rows = None
    for table in soup.find_all("table"):
        rows = table_rows(table)
        header = " | ".join(rows[0]) if rows else ""
        if all(label in header for label in ("Model", "Base Input Tokens", "Cache Hits", "Output Tokens")):
            pricing_rows = rows
            break
    if not pricing_rows:
        return result

    for cells in pricing_rows[1:]:
        if len(cells) < 6 or not cells[0].lower().startswith("claude"):
            continue
        raw_name = cells[0]
        availability = "active"
        if "retired" in raw_name.lower():
            availability = "retired"
        elif "limited availability" in raw_name.lower():
            availability = "limited"
        display = re.sub(r"\s*\([^)]*(?:retired|limited availability)[^)]*\)\s*", " ", raw_name, flags=re.I).strip()
        display, eligible = _date_qualified_name(display)
        if not eligible:
            continue
        values = [first_money(cell) for cell in cells[1:6]]
        if values[0] is None or values[3] is None or values[4] is None:
            continue
        model_id = slugify(display)
        item_id, item = model_record(
            "anthropic", model_id, display, values[0], values[3], values[4],
            "Claude API · standard global", "Base input, cache-hit and output token rates.", availability
        )
        result[item_id] = item
    return result


def _next_before_h2(heading: Tag, wanted: str) -> Tag | None:
    for node in heading.next_elements:
        if node is heading:
            continue
        if isinstance(node, Tag) and node.name == "h2":
            return None
        if isinstance(node, Tag) and node.name == wanted:
            return node
    return None


def parse_google(page: Page) -> dict[str, dict]:
    soup = BeautifulSoup(page.html, "html.parser")
    result: dict[str, dict] = {}
    for heading in soup.find_all("h2"):
        code = _next_before_h2(heading, "code")
        table = _next_before_h2(heading, "table")
        if code is None or table is None:
            continue
        model_id = clean_space(code.get_text(" ", strip=True))
        if not model_id.startswith("gemini-"):
            continue
        # These rows quote output per generated image, not per 1M output
        # tokens, so they cannot participate in the token-price calculator.
        if "-image" in model_id:
            continue
        rows = table_rows(table)
        input_price = output_price = cached_price = None
        rate_notes: list[str] = []
        for cells in rows:
            if len(cells) < 2:
                continue
            label = cells[0].lower()
            paid = cells[-1]
            if label.startswith("input price") and input_price is None:
                input_price = first_money(paid)
                rate_notes.append(cells[0])
            elif label.startswith("output price") and output_price is None:
                output_price = first_money(paid)
                rate_notes.append(cells[0])
            elif label.startswith("context caching price") and cached_price is None:
                cached_price = first_money(paid)
        if input_price is None or output_price is None:
            continue
        name = clean_space(heading.get_text(" ", strip=True)).replace("🍌", "").strip()
        availability = "preview" if "preview" in f"{name} {model_id}".lower() else "active"
        cache_note = "cache rate listed" if cached_price is not None else "no separate cache rate listed"
        item_id, item = model_record(
            "google", model_id, name, input_price, cached_price, output_price,
            "paid standard", f"First listed paid token rate ({cache_note}); modalities and thresholds may differ.", availability
        )
        result[item_id] = item
    return result


def parse_xai(page: Page) -> dict[str, dict]:
    soup = BeautifulSoup(page.html, "html.parser")
    result: dict[str, dict] = {}
    for table in soup.find_all("table"):
        rows = table_rows(table)
        header = " | ".join(rows[0:2][0] + (rows[1] if len(rows) > 1 else [])) if rows else ""
        if not all(label in header for label in ("Model", "Context", "Input", "Cached", "Output")):
            continue
        for cells in rows:
            if len(cells) < 5:
                continue
            match = re.search(r"\b(grok-[a-z0-9._-]+)", cells[0], re.I)
            if not match:
                continue
            model_id = match.group(1)
            prices = [first_money(cell) for cell in cells[2:5]]
            if any(value is None for value in prices):
                continue
            context = cells[1] if len(cells) > 1 else ""
            item_id, item = model_record(
                "xai", model_id, title_from_id(model_id), prices[0], prices[1], prices[2],
                "standard · short context", f"Context: {context}; long-context rates may differ."
            )
            result[item_id] = item
        if result:
            break
    return result


def parse_deepseek(page: Page) -> dict[str, dict]:
    soup = BeautifulSoup(page.html, "html.parser")
    table = soup.find("table")
    if table is None:
        return {}
    rows = table_rows(table)
    if not rows or len(rows[0]) < 2 or rows[0][0] != "MODEL":
        return {}
    models = rows[0][1:]
    versions = models[:]
    hit = miss = output = None
    for cells in rows[1:]:
        label = cells[0].upper() if cells else ""
        if label == "MODEL VERSION":
            versions = cells[1:]
        elif "INPUT TOKENS (CACHE HIT)" in " ".join(cells).upper():
            hit = [first_money(cell) for cell in cells[-len(models):]]
        elif "INPUT TOKENS (CACHE MISS)" in label:
            miss = [first_money(cell) for cell in cells[1:1 + len(models)]]
        elif "OUTPUT TOKENS" in label:
            output = [first_money(cell) for cell in cells[1:1 + len(models)]]
    if not hit or not miss or not output:
        return {}
    result: dict[str, dict] = {}
    for index, model_id in enumerate(models):
        if index >= len(hit) or index >= len(miss) or index >= len(output):
            continue
        if hit[index] is None or miss[index] is None or output[index] is None:
            continue
        version = versions[index] if index < len(versions) else model_id
        item_id, item = model_record(
            "deepseek", model_id, title_from_id(version), miss[index], hit[index], output[index],
            "standard", "Official DeepSeek API; promotions or time-based rates may change."
        )
        result[item_id] = item
    return result


def parse_alibaba(page: Page) -> dict[str, dict]:
    soup = BeautifulSoup(page.html, "html.parser")
    candidates: dict[str, dict] = {}
    for table in soup.find_all("table"):
        rows = table_rows(table)
        if not rows:
            continue
        header = " | ".join(rows[0])
        if not all(label in header for label in ("Model ID", "Deployment scope", "Input price", "Output price")):
            continue
        # Multimodal tables expose several input/output columns. They are not
        # directly comparable to the text-token rows in this dashboard.
        if "audio" in header.lower():
            continue
        for cells in rows[1:]:
            if len(cells) < 4:
                continue
            model_match = re.match(r"^((?:qwen|qwq)[a-z0-9._-]*)\b", cells[0], re.I)
            if not model_match:
                continue
            if not any(scope.lower() == "international" for scope in cells[1:3]):
                continue
            model_id = model_match.group(1)
            local_id = f"alibaba:{slugify(model_id)}"
            if local_id in candidates:
                continue
            values = money_values(" | ".join(cells))
            if len(values) < 2:
                continue
            # Skip multimodal rows with separate audio prices; simple text rows
            # contain one input and one output dollar value.
            if len(values) > 2:
                continue
            input_price, output_price = values[0], values[1]
            supports_cache = "context cach" in cells[0].lower()
            cached_price = input_price * 0.1 if supports_cache else None
            bracket = next((cell for cell in cells if "token" in cell.lower() and any(ch in cell for ch in "≤<>")), "")
            availability = "preview" if "preview" in model_id.lower() else "active"
            cache_note = "cache hit approximated at documented 10%" if supports_cache else "no separate cache rate listed"
            item_id, item = model_record(
                "alibaba", model_id, title_from_id(model_id), input_price, cached_price, output_price,
                "international", f"Lowest listed International tier {bracket}; {cache_note}.", availability
            )
            candidates[item_id] = item

    # Keep only the current Qwen generation and one generation back. Alibaba's
    # wide catalogue includes specialist, historical and snapshot endpoints;
    # keeping every one makes price comparison less useful than a curated view.
    result: dict[str, dict] = {}
    for item_id, item in candidates.items():
        model_id = item["model_id"].lower()
        if re.search(r"-20\d{2}-\d{2}-\d{2}$", model_id) or model_id.endswith("-preview"):
            continue
        if not re.match(r"^qwen3\.7-", model_id):
            continue
        result[item_id] = item

    # The official capability documentation lists Qwen3.8-Max, while the public
    # USD per-token price table has not caught up. Include it for discoverability
    # but deliberately exclude it from numeric cost/value rankings.
    item_id, item = model_record(
        "alibaba", "qwen3.8-max", "Qwen3.8 Max", 0, 0, 0,
        "Qwen Cloud / Model Studio", "Officially listed as available; public USD token price is not listed yet.",
        "preview", price_comparable=False,
    )
    result[item_id] = item
    return result


MOONSHOT_PRICING_URLS = (
    "https://platform.kimi.ai/docs/pricing/chat-k3.md",
    "https://platform.kimi.ai/docs/pricing/chat-k27-code.md",
    "https://platform.kimi.ai/docs/pricing/chat-k26.md",
)


def parse_moonshot(_: Page) -> dict[str, dict]:
    """Read Moonshot's public Markdown tables for its current Kimi models."""
    result: dict[str, dict] = {}
    for url in MOONSHOT_PRICING_URLS:
        response = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        if len(response.content) < 500:
            raise ValueError(f"Moonshot pricing response unexpectedly short: {url}")
        for model_id, cached, input_price, output_price, context in re.findall(
            r'\["(kimi-[^"]+)", "1M tokens",.*?\$"\}(\d+(?:\.\d+)?)</>,.*?\$"\}(\d+(?:\.\d+)?)</>,.*?\$"\}(\d+(?:\.\d+)?)</>, "([^"]+)"\]',
            response.text,
            re.S,
        ):
            item_id, item = model_record(
                "moonshot", model_id, title_from_id(model_id), float(input_price), float(cached), float(output_price),
                "standard", f"Official Moonshot API pricing; context {context}."
            )
            result[item_id] = item
    return result


SPECS = [
    ProviderSpec("openai", "https://developers.openai.com/api/docs/pricing", 5, parse_openai),
    ProviderSpec("anthropic", "https://platform.claude.com/docs/en/about-claude/pricing", 5, parse_anthropic),
    ProviderSpec("google", "https://ai.google.dev/gemini-api/docs/pricing", 8, parse_google),
    ProviderSpec("xai", "https://docs.x.ai/developers/pricing", 3, parse_xai),
    ProviderSpec("deepseek", "https://api-docs.deepseek.com/quick_start/pricing", 2, parse_deepseek),
    ProviderSpec("alibaba", "https://www.alibabacloud.com/help/en/model-studio/model-pricing", 2, parse_alibaba),
    ProviderSpec("moonshot", "https://platform.kimi.ai/docs/pricing/chat-k3", 4, parse_moonshot),
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


def fetch(session: requests.Session, url: str) -> Page:
    response = session.get(url, timeout=TIMEOUT, headers={"Accept-Language": "en-US,en;q=0.9"})
    response.raise_for_status()
    if len(response.content) < 1000:
        raise ValueError(f"response unexpectedly short ({len(response.content)} bytes)")
    return Page(response.text, normalized_text(response.text))


def valid_price_set(values: dict, old: dict | None = None) -> tuple[bool, str | None]:
    old = old or {}
    if values.get("price_comparable") is False:
        return True, None
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


def add_event(history: dict, now: str, provider: str, model_id: str, event_type: str, changes: dict, source: str) -> None:
    history.setdefault("events", []).append({
        "timestamp": now,
        "provider": provider,
        "model_id": model_id,
        "event_type": event_type,
        "changes": changes,
        "source_url": source,
    })


def update(selected: set[str] | None = None, dry_run: bool = False) -> int:
    prices = load_json(PRICES_PATH)
    history = load_json(HISTORY_PATH)
    before_prices = copy.deepcopy(prices)
    before_history = copy.deepcopy(history)
    # Schema v2 intentionally compares per-token rates only. Remove rows from
    # early v2 snapshots that used a per-image output unit, and remove Alibaba
    # dated/preview aliases which were mistakenly catalogued as separate models.
    excluded_ids = {
        model["id"] for model in prices.get("models", [])
        if model.get("provider") == "google" and "-image" in model.get("model_id", "")
        or model.get("provider") == "alibaba" and not re.match(
            r"^qwen3\.(?:7|8)-", model.get("model_id", "").lower()
        )
    }
    if excluded_ids:
        prices["models"] = [model for model in prices["models"] if model["id"] not in excluded_ids]
        history["events"] = [event for event in history.get("events", []) if event.get("model_id") not in excluded_ids]
    now = utc_now()
    model_index = {model["id"]: model for model in prices.get("models", [])}
    provider_index = {provider["id"]: provider for provider in prices["providers"]}
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    event_count = 0

    for spec in SPECS:
        if selected and spec.provider_id not in selected:
            continue
        provider = provider_index[spec.provider_id]
        provider["last_checked_at"] = now
        provider["source_url"] = spec.url
        try:
            parsed = spec.parser(fetch(session, spec.url))
            if len(parsed) < spec.minimum_models:
                raise ValueError(f"incomplete discovery: {len(parsed)} model(s), expected at least {spec.minimum_models}")
            accepted = 0
            rejected: list[str] = []
            seen: set[str] = set()
            for local_id, discovered in parsed.items():
                old = model_index.get(local_id)
                ok, reason = valid_price_set(discovered, old)
                if not ok:
                    rejected.append(f"{local_id}: {reason}")
                    continue
                accepted += 1
                seen.add(local_id)
                if old is None:
                    discovered.update({
                        "source_url": spec.url,
                        "first_seen_at": now,
                        "last_seen_at": now,
                        "updated_at": now,
                        "missing_checks": 0,
                    })
                    prices["models"].append(discovered)
                    model_index[local_id] = discovered
                    changes = {field: {"from": None, "to": discovered[field]} for field in PRICE_FIELDS}
                    add_event(history, now, spec.provider_id, local_id, "added", changes, spec.url)
                    event_count += 1
                    continue

                was_active = old.get("active", True)
                price_changes = {
                    field: {"from": old[field], "to": round(discovered[field], 9)}
                    for field in PRICE_FIELDS
                    if not math.isclose(float(old[field]), float(discovered[field]), rel_tol=0, abs_tol=1e-9)
                }
                for field in ("name", "model_id", "tier", "context_note", "availability", "active", "price_comparable"):
                    old[field] = discovered[field]
                for field in PRICE_FIELDS:
                    old[field] = round(discovered[field], 9)
                old.update({"source_url": spec.url, "last_seen_at": now, "missing_checks": 0})
                old.setdefault("first_seen_at", old.get("updated_at", now))
                if price_changes:
                    old["updated_at"] = now
                    add_event(history, now, spec.provider_id, local_id, "price_changed", price_changes, spec.url)
                    event_count += 1
                if not was_active and old.get("active"):
                    add_event(history, now, spec.provider_id, local_id, "reactivated", {}, spec.url)
                    event_count += 1

            complete_scan = not rejected and accepted >= spec.minimum_models
            if complete_scan:
                for old in [model for model in prices["models"] if model.get("provider") == spec.provider_id]:
                    if old["id"] in seen:
                        continue
                    old["missing_checks"] = int(old.get("missing_checks", 0)) + 1
                    if old["missing_checks"] >= MISSING_LIMIT and old.get("availability") != "not_listed":
                        old["active"] = False
                        old["availability"] = "not_listed"
                        add_event(history, now, spec.provider_id, old["id"], "not_listed", {}, spec.url)
                        event_count += 1

            provider["status"] = "ok" if not rejected else "partial"
            provider["last_success_at"] = now
            provider["error"] = "; ".join(rejected)[:500] or None
            provider["model_count"] = accepted
            LOG.info("%s: discovered %d model(s), rejected %d", spec.provider_id, accepted, len(rejected))
        except Exception as exc:  # provider failures must never stop other providers
            provider["status"] = "error"
            provider["error"] = f"{type(exc).__name__}: {exc}"[:500]
            LOG.warning("%s retained previous catalog: %s", spec.provider_id, provider["error"])

    prices["schema_version"] = 2
    prices["last_checked_at"] = now
    if event_count:
        prices["last_updated_at"] = now
    prices["models"].sort(key=lambda model: (model.get("provider", ""), not model.get("active", True), model.get("name", "").lower()))
    history["schema_version"] = 2
    history["events"] = history.get("events", [])[-5000:]

    if dry_run:
        additions = len(model_index) - len({model["id"] for model in before_prices.get("models", [])})
        LOG.info("dry run: %d new model(s), %d catalog event(s); no files written", additions, event_count)
        return 0
    if prices != before_prices:
        atomic_json_write(PRICES_PATH, prices)
    if history != before_history:
        atomic_json_write(HISTORY_PATH, history)
    LOG.info("finished: %d catalog event(s), %d total model(s)", event_count, len(prices["models"]))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover and update AI token pricing from official public pages.")
    parser.add_argument("--provider", action="append", choices=[spec.provider_id for spec in SPECS])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    try:
        return update(set(args.provider) if args.provider else None, args.dry_run)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        LOG.error("fatal local data error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
