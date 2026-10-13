"""Reproducible report ablations on public tapes (seed 25)."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gameday_lab.client import ResilientClient
from gameday_lab.factory import build_client
from gameday_lab.sim.config import load_config
from gameday_lab.sim.engine import run_scenario


class UnsafeToolRouting(ResilientClient):
    """Ablation only: route tool calls to providers without tool support."""

    def ladder(self, task: str) -> list[str]:
        return list(self.order)


def measure(cfg, scenario: str, client: str = "resilient", unsafe: bool = False) -> dict:
    agent = (UnsafeToolRouting(cfg.provider_infos(), cfg.fallback_order, cfg.client, seed=1)
             if unsafe else build_client(client, cfg))
    metrics = run_scenario(cfg, scenario, agent, seed=25).metrics()
    keys = ("availability", "latency_p95_s", "amplification", "retry_ratio", "recovery_s",
            "give_up_reasons", "incompatible_routes", "faq_availability", "cache_hit_ratio",
            "wrong_answers", "wrong_answers_by_reason", "outdated_answers", "stale_served",
            "cost_per_good_turn")
    return {key: metrics[key] for key in keys if key in metrics}


def main() -> None:
    base = load_config()
    cache_base = load_config(scenarios_path="configs/scenarios_cache.yaml")
    result: dict[str, dict] = {}
    breaker_off = {**base.client, "max_attempts_per_provider": 5,
                   "breaker": {**base.client["breaker"], "min_calls": 1_000_000_000}}
    unlimited_budget = {**breaker_off, "retry_budget_ratio": 100,
                        "retry_budget_max_tokens": 1e9, "retry_budget_min_per_s": 1e6}
    for scenario in ("G2_overload_storm", "G3_brownout"):
        result[f"budget_{scenario}"] = {
            "limited": measure(replace(base, client=breaker_off), scenario),
            "unlimited": measure(replace(base, client=unlimited_budget), scenario),
        }
    for scenario in ("G6_provider_outage", "G4_slow_region"):
        result[f"timeout_{scenario}"] = {
            "default": measure(base, scenario),
            "30s": measure(replace(base, client={**base.client, "attempt_timeout_s": 30}), scenario),
        }
    result["tool_filter_G6"] = {
        "enabled": measure(base, "G6_provider_outage"),
        "disabled": measure(base, "G6_provider_outage", unsafe=True),
    }
    for threshold in (0.80, base.cache["similarity_threshold"], 0.97):
        cfg = replace(cache_base, cache={**cache_base.cache, "similarity_threshold": threshold})
        result[f"cache_threshold_{threshold}"] = measure(cfg, "C1_faq_outage", "cached")
    for ttl in (30, 60, 300):
        cfg = replace(cache_base, cache={**cache_base.cache, "ttl_s": ttl})
        result[f"cache_ttl_{ttl}"] = measure(cfg, "C1_faq_outage", "cached")
    cfg = replace(cache_base, cache={**cache_base.cache, "max_stale_s": 0})
    result["cache_no_stale"] = measure(cfg, "C1_faq_outage", "cached")
    out = Path("reports/experiments.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
