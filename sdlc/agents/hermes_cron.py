#!/usr/bin/env python3
"""
Hermes Cron Agent — 24/7 Background Scheduler
===============================================
Uses hermes3 (free local Ollama model) for lightweight background tasks.
Runs independently of Discord bots — no Discord connection needed.

Jobs:
  Every 1h   — project_health_check   (status of active projects)
  Every 6h   — dna_freshness_check    (alert if DNA > 7 days old)
  Every 24h  — daily_cost_summary     (total cost report → Obsidian)
  Every 24h  — obsidian_sync          (sync all DNA + lessons to vault)
  Every 168h — weekly_pattern_review  (extract patterns from outputs)

Usage:
  python agents/hermes_cron.py                  # run forever
  python agents/hermes_cron.py --run-now hourly # run a specific job once
  DB_PATH=/path/to/sdlc.db python agents/hermes_cron.py
"""

import os
import sys
import json
import time
import asyncio
import logging
import argparse
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'), override=True)

import schedule

from shared.storage import Storage
from shared.model_router import CostTracker, MODELS
from shared.llm_client import LLMClient
from shared.obsidian_client import get_obsidian
from shared.dna_bootstrap import get_dna_bootstrap

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("hermes_cron")

# ─── Hermes LLM — free Ollama model for lightweight tasks ────────────────────

def _get_hermes_client() -> LLMClient:
    """Return LLMClient for hermes3 (Ollama, free, no API key)."""
    cfg = MODELS.get("ollama/hermes3")
    if cfg is None:
        # Create a minimal config if not in MODELS
        from shared.model_router import ModelConfig, ModelTier
        cfg = ModelConfig(
            provider="ollama",
            model_id="hermes3:3b",
            tier=ModelTier.FREE,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            max_tokens=4096,
            description="hermes3 local",
        )
    return LLMClient(model_config=cfg, model_key="ollama/hermes3")


async def _ask_hermes(prompt: str, system: str = "", max_tokens: int = 1024) -> str:
    """Run a quick question through hermes3."""
    client = _get_hermes_client()
    try:
        return await client.complete(
            system_prompt=system or "You are a helpful SDLC system status assistant. Be concise.",
            user_message=prompt,
            max_tokens=max_tokens,
            role="hermes",
            use_dna=False,
        )
    except Exception as e:
        logger.warning(f"[Hermes] LLM call failed: {e}")
        return f"[hermes unavailable: {e}]"


# ─── Shared state ─────────────────────────────────────────────────────────────

_storage: Optional[Storage] = None
_tracker: Optional[CostTracker] = None
_job_history: list[dict] = []  # in-memory log for web dashboard

MAX_HISTORY = 200  # keep last N entries


def _storage_inst() -> Storage:
    global _storage
    if _storage is None:
        _storage = Storage()
    return _storage


def _tracker_inst() -> CostTracker:
    global _tracker
    if _tracker is None:
        _tracker = CostTracker()
    return _tracker


def _log_job(job_name: str, status: str, summary: str):
    entry = {
        "job":       job_name,
        "status":    status,
        "summary":   summary,
        "timestamp": datetime.utcnow().isoformat(),
    }
    _job_history.append(entry)
    if len(_job_history) > MAX_HISTORY:
        _job_history.pop(0)

    # Persist to Obsidian cron log
    try:
        get_obsidian().save_cron_log(job_name, status, summary)
    except Exception as e:
        logger.debug(f"[Cron] Obsidian log failed: {e}")

    # Persist to local JSON file for web API
    _flush_history()


def _flush_history():
    try:
        out_dir = Path(os.getenv("OUTPUT_BASE_PATH", "/app/outputs")) / "cron"
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "job_history.json", "w", encoding="utf-8") as f:
            json.dump(_job_history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.debug(f"[Cron] History flush failed: {e}")


# ─── Job: project_health_check (every 1h) ────────────────────────────────────

async def job_project_health_check():
    logger.info("[Job] project_health_check ▶")
    try:
        storage = _storage_inst()
        projects = storage.list_active_projects()
        if not projects:
            _log_job("project_health_check", "ok", "No active projects")
            return

        lines = [f"Active projects: {len(projects)}\n"]
        stalled = []
        for p in projects:
            task = storage.get_task_by_project_role(p.id, p.current_role)
            age_h = 0
            if task and task.started_at:
                try:
                    started = datetime.fromisoformat(task.started_at)
                    age_h = (datetime.utcnow() - started).total_seconds() / 3600
                except Exception:
                    pass
            status = task.status if task else "unknown"
            lines.append(f"- {p.name} [{p.current_role.upper()}] status={status} age={age_h:.1f}h")
            if age_h > 12 and status not in ("completed", "approved"):
                stalled.append(p.name)

        summary = "\n".join(lines)
        if stalled:
            summary += f"\n\n⚠️ STALLED (>12h): {', '.join(stalled)}"
            # Ask hermes for a brief diagnosis
            diagnosis = await _ask_hermes(
                f"These SDLC projects appear stalled for >12h:\n{stalled}\n"
                "Give 2-sentence recommendation in English.",
                max_tokens=200,
            )
            summary += f"\n\nHermes recommendation:\n{diagnosis}"

        _log_job("project_health_check", "ok" if not stalled else "warn", summary)
        logger.info(f"[Job] project_health_check ✅ ({len(projects)} projects, {len(stalled)} stalled)")
    except Exception as e:
        _log_job("project_health_check", "error", str(e))
        logger.error(f"[Job] project_health_check ❌ {e}")


# ─── Job: daily_cost_summary (every 24h) ─────────────────────────────────────

async def job_daily_cost_summary():
    logger.info("[Job] daily_cost_summary ▶")
    try:
        tracker = _tracker_inst()
        summary_data = tracker.today_summary()
        total_cost = summary_data.get("total_cost_usd", 0)
        total_tokens = summary_data.get("total_tokens", 0)
        by_role = summary_data.get("by_role", {})

        lines = [
            f"# Daily Cost Summary — {datetime.utcnow().strftime('%Y-%m-%d')}",
            f"",
            f"**Total cost:** ${total_cost:.4f} USD",
            f"**Total tokens:** {total_tokens:,}",
            f"",
            "## By Role",
        ]
        for role, data in by_role.items():
            lines.append(f"- **{role.upper()}**: ${data.get('cost', 0):.4f} | {data.get('tokens', 0):,} tokens")

        if total_cost > 1.0:
            advice = await _ask_hermes(
                f"Daily LLM cost is ${total_cost:.2f}. "
                f"Token breakdown: {json.dumps(by_role, default=str)[:400]}. "
                "Suggest 1-2 specific ways to reduce cost without losing quality.",
                max_tokens=300,
            )
            lines += ["", "## Hermes Cost Advice", advice]

        summary = "\n".join(lines)
        get_obsidian().write_note(
            f"05-Cron-Logs/cost-{datetime.utcnow().strftime('%Y-%m-%d')}.md",
            summary,
        )
        _log_job("daily_cost_summary", "ok", f"${total_cost:.4f} | {total_tokens:,} tokens")
        logger.info(f"[Job] daily_cost_summary ✅ ${total_cost:.4f}")
    except Exception as e:
        _log_job("daily_cost_summary", "error", str(e))
        logger.error(f"[Job] daily_cost_summary ❌ {e}")


# ─── Job: dna_freshness_check (every 6h) ────────────────────────────────────

async def job_dna_freshness_check():
    logger.info("[Job] dna_freshness_check ▶")
    try:
        dna = get_dna_bootstrap()
        stale_roles = []
        missing_roles = []
        roles = ["ceo", "pm", "ba", "sa", "uxui", "dev", "qa", "devops"]
        for role in roles:
            entry = dna.get_dna(role)
            if not entry:
                missing_roles.append(role)
                continue
            updated = entry.get("updated_at", "")
            if updated:
                try:
                    age_days = (datetime.utcnow() - datetime.fromisoformat(updated)).days
                    if age_days > 7:
                        stale_roles.append(f"{role} ({age_days}d)")
                except Exception:
                    pass

        parts = []
        if missing_roles:
            parts.append(f"Missing DNA: {', '.join(missing_roles)}")
        if stale_roles:
            parts.append(f"Stale DNA (>7 days): {', '.join(stale_roles)}")

        status = "ok" if not parts else "warn"
        summary = "; ".join(parts) if parts else f"All {len(roles)} roles have fresh DNA"
        _log_job("dna_freshness_check", status, summary)
        logger.info(f"[Job] dna_freshness_check ✅ {summary}")
    except Exception as e:
        _log_job("dna_freshness_check", "error", str(e))
        logger.error(f"[Job] dna_freshness_check ❌ {e}")


# ─── Job: obsidian_sync (every 24h) ──────────────────────────────────────────

async def job_obsidian_sync():
    logger.info("[Job] obsidian_sync ▶")
    try:
        obs = get_obsidian()
        dna = get_dna_bootstrap()
        synced = 0

        # Ensure vault structure exists
        obs.initialize_vault()

        # Sync all cached DNA to vault
        for entry in dna.list_cached_roles():
            role = entry["role"]
            dna_data = dna.get_dna(role)
            if dna_data:
                obs.save_role_dna(role, {**dna_data, "_model_used": entry.get("model", "unknown")})
                synced += 1

        _log_job("obsidian_sync", "ok", f"Synced {synced} DNA entries to vault")
        logger.info(f"[Job] obsidian_sync ✅ {synced} entries synced")
    except Exception as e:
        _log_job("obsidian_sync", "error", str(e))
        logger.error(f"[Job] obsidian_sync ❌ {e}")


# ─── Job: gold_price_monitor (every 5 min) ───────────────────────────────────

async def job_gold_price_monitor():
    """ดึงราคาทองคำ XAU/USD แบบ real-time และตรวจสอบ significant moves"""
    logger.info("[Job] gold_price_monitor ▶")
    try:
        import urllib.request, json as _json
        # Yahoo Finance unofficial endpoint (no API key)
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1m&range=5m"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read())
        result  = data["chart"]["result"][0]
        meta    = result["meta"]
        price   = meta.get("regularMarketPrice", 0)
        prev    = meta.get("previousClose", price)
        chg_pct = ((price - prev) / prev * 100) if prev else 0
        high    = meta.get("regularMarketDayHigh", price)
        low     = meta.get("regularMarketDayLow", price)

        summary = (
            f"XAU/USD: ${price:,.2f}  |  "
            f"Δ {chg_pct:+.2f}%  |  "
            f"H:{high:,.2f} / L:{low:,.2f}"
        )
        status = "warn" if abs(chg_pct) >= 0.5 else "ok"

        if abs(chg_pct) >= 0.5:
            alert = await _ask_hermes(
                f"Gold (XAU/USD) moved {chg_pct:+.2f}% to ${price:,.2f}. "
                "Give a 1-sentence market context and 1-sentence trading implication.",
                max_tokens=150,
            )
            summary += f"\n⚠️ Significant move! Hermes: {alert}"

        _log_job("gold_price_monitor", status, summary)
        logger.info(f"[Job] gold_price_monitor ✅ {summary}")
    except Exception as e:
        _log_job("gold_price_monitor", "error", str(e))
        logger.warning(f"[Job] gold_price_monitor ⚠️ {e}")


# ─── Job: gold_trading_signal (every 15 min) ─────────────────────────────────

async def job_gold_trading_signal():
    """วิเคราะห์ technical indicators สำหรับ XAU/USD และสร้าง trading signal"""
    logger.info("[Job] gold_trading_signal ▶")
    try:
        import urllib.request, json as _json
        # Fetch 1h OHLCV data (60 candles)
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1h&range=3d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read())

        result  = data["chart"]["result"][0]
        closes  = result["indicators"]["quote"][0].get("close", [])
        closes  = [c for c in closes if c is not None]

        if len(closes) < 20:
            _log_job("gold_trading_signal", "skip", "Not enough data for analysis")
            return

        # Simple indicators (no ta-lib dependency)
        def ema(prices, period):
            k = 2 / (period + 1)
            e = [prices[0]]
            for p in prices[1:]:
                e.append(p * k + e[-1] * (1 - k))
            return e

        ema9  = ema(closes, 9)[-1]
        ema21 = ema(closes, 21)[-1]
        price = closes[-1]

        # RSI-14
        gains = losses = 0
        for i in range(1, 15):
            d = closes[-i] - closes[-i-1]
            if d > 0: gains += d
            else:     losses -= d
        rsi = 100 - (100 / (1 + (gains/14) / (losses/14 + 1e-9)))

        # Signal
        trend   = "UP" if ema9 > ema21 else "DOWN"
        signal  = "BUY" if (trend == "UP" and rsi < 65) else \
                  "SELL" if (trend == "DOWN" and rsi > 35) else "HOLD"

        summary = (
            f"Price: ${price:,.2f}  |  EMA9: {ema9:,.2f}  EMA21: {ema21:,.2f}  "
            f"RSI14: {rsi:.1f}  |  Trend: {trend}  →  Signal: **{signal}**"
        )

        analysis = await _ask_hermes(
            f"Gold XAU/USD signal analysis:\n{summary}\n"
            "Give a 2-sentence trading recommendation with specific entry/stop-loss levels.",
            max_tokens=200,
        )
        summary += f"\nHermes: {analysis}"
        _log_job("gold_trading_signal", "ok", summary)
        logger.info(f"[Job] gold_trading_signal ✅ {signal} @ ${price:,.2f}")
    except Exception as e:
        _log_job("gold_trading_signal", "error", str(e))
        logger.warning(f"[Job] gold_trading_signal ⚠️ {e}")


# ─── Job: gold_daily_report (every 24h) ──────────────────────────────────────

async def job_gold_daily_report():
    """สรุปผล trading performance ประจำวัน + market summary"""
    logger.info("[Job] gold_daily_report ▶")
    try:
        import urllib.request, json as _json
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d&range=7d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read())

        result  = data["chart"]["result"][0]
        meta    = result["meta"]
        closes  = result["indicators"]["quote"][0].get("close", [])
        closes  = [c for c in closes if c is not None]
        price   = meta.get("regularMarketPrice", closes[-1] if closes else 0)
        wk_chg  = ((price - closes[0]) / closes[0] * 100) if closes else 0

        # Also check deployed trading bot results if exists
        bot_output = Path(os.getenv("OUTPUT_BASE_PATH", "outputs")) / "trading_bot" / "daily_results.json"
        bot_summary = ""
        if bot_output.exists():
            try:
                with open(bot_output) as f:
                    bot_data = _json.load(f)
                pnl   = bot_data.get("pnl_usd", 0)
                trades= bot_data.get("total_trades", 0)
                wins  = bot_data.get("win_rate", 0)
                bot_summary = f"\n\n**Bot Performance:**\n- PnL: ${pnl:+.2f}\n- Trades: {trades}\n- Win Rate: {wins:.1f}%"
            except Exception:
                pass

        market_ctx = (
            f"Gold 7-day closes: {[f'{c:.0f}' for c in closes[-7:]]}\n"
            f"Current: ${price:,.2f} | 7-day change: {wk_chg:+.2f}%"
        )
        report_text = await _ask_hermes(
            f"Generate a concise daily gold market report:\n{market_ctx}\n"
            "Include: 1) Market summary 2) Key levels to watch 3) Outlook for next session.",
            system="You are a professional gold market analyst. Be specific with price levels.",
            max_tokens=500,
        )

        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        full_report = (
            f"# Gold Trading Daily Report — {date_str}\n\n"
            f"**XAU/USD:** ${price:,.2f}  |  7-day Δ: {wk_chg:+.2f}%\n"
            f"{bot_summary}\n\n"
            f"## Market Analysis\n{report_text}"
        )
        try:
            get_obsidian().write_note(f"06-Trading/daily-{date_str}.md", full_report)
        except Exception:
            pass

        summary = f"XAU/USD ${price:,.2f} ({wk_chg:+.2f}% 7d){bot_summary[:80] if bot_summary else ''}"
        _log_job("gold_daily_report", "ok", summary)
        logger.info(f"[Job] gold_daily_report ✅ {summary}")
    except Exception as e:
        _log_job("gold_daily_report", "error", str(e))
        logger.warning(f"[Job] gold_daily_report ⚠️ {e}")


# ─── Job: weekly_pattern_review (every 168h = 7d) ───────────────────────────

async def job_weekly_pattern_review():
    logger.info("[Job] weekly_pattern_review ▶")
    try:
        obs = get_obsidian()
        # Search recent outputs for patterns
        recent_outputs = obs.list_notes("03-Outputs")[-20:]
        if not recent_outputs:
            _log_job("weekly_pattern_review", "ok", "No outputs to review")
            return

        samples = []
        for path in recent_outputs[:5]:
            content = obs.read_note(path)
            if content:
                samples.append(f"[{path}]\n{content[:400]}")

        if not samples:
            _log_job("weekly_pattern_review", "ok", "No output content found")
            return

        review = await _ask_hermes(
            "Review these SDLC agent outputs and identify:\n"
            "1. Recurring quality issues\n"
            "2. Successful patterns worth repeating\n"
            "3. One improvement suggestion per role found\n\n"
            + "\n\n".join(samples),
            system="You are an SDLC quality reviewer. Be specific and actionable. Max 400 words.",
            max_tokens=600,
        )

        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        obs.save_lesson(
            title=f"Weekly Pattern Review {date_str}",
            content=review,
            tags=["auto", "pattern-review", "hermes"],
        )
        _log_job("weekly_pattern_review", "ok", f"Reviewed {len(samples)} outputs, lesson saved")
        logger.info("[Job] weekly_pattern_review ✅ lesson saved to Obsidian")
    except Exception as e:
        _log_job("weekly_pattern_review", "error", str(e))
        logger.error(f"[Job] weekly_pattern_review ❌ {e}")


# ─── Async job runner wrapper ─────────────────────────────────────────────────

def _run_async(coro):
    """Run async job from synchronous schedule context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(coro)
        else:
            loop.run_until_complete(coro)
    except RuntimeError:
        asyncio.run(coro)


# ─── Schedule setup ───────────────────────────────────────────────────────────

def register_jobs():
    schedule.every(1).hours.do(lambda: _run_async(job_project_health_check()))
    schedule.every(6).hours.do(lambda: _run_async(job_dna_freshness_check()))
    schedule.every(24).hours.do(lambda: _run_async(job_daily_cost_summary()))
    schedule.every(24).hours.do(lambda: _run_async(job_obsidian_sync()))
    schedule.every(168).hours.do(lambda: _run_async(job_weekly_pattern_review()))
    # ── Gold Trading Bot jobs ─────────────────────────────────────────────────
    schedule.every(5).minutes.do(lambda: _run_async(job_gold_price_monitor()))
    schedule.every(15).minutes.do(lambda: _run_async(job_gold_trading_signal()))
    schedule.every(24).hours.do(lambda: _run_async(job_gold_daily_report()))

    logger.info("📅 Cron jobs registered:")
    logger.info("  Every  1h  — project_health_check")
    logger.info("  Every  6h  — dna_freshness_check")
    logger.info("  Every 24h  — daily_cost_summary")
    logger.info("  Every 24h  — obsidian_sync")
    logger.info("  Every  7d  — weekly_pattern_review")
    logger.info("  Every  5m  — gold_price_monitor      🥇")
    logger.info("  Every 15m  — gold_trading_signal     🥇")
    logger.info("  Every 24h  — gold_daily_report       🥇")


# ─── Named jobs map for --run-now ────────────────────────────────────────────

NAMED_JOBS = {
    "health":        job_project_health_check,
    "cost":          job_daily_cost_summary,
    "dna":           job_dna_freshness_check,
    "sync":          job_obsidian_sync,
    "patterns":      job_weekly_pattern_review,
    "gold_price":    job_gold_price_monitor,
    "gold_signal":   job_gold_trading_signal,
    "gold_report":   job_gold_daily_report,
}


# ─── Status API helpers (called by web API route) ────────────────────────────

def get_job_history(limit: int = 50) -> list[dict]:
    """Return recent job history (newest first)."""
    history = list(reversed(_job_history))[:limit]
    # Also try reading from disk if in-memory is empty (e.g., after restart)
    if not history:
        try:
            out_dir = Path(os.getenv("OUTPUT_BASE_PATH", "/app/outputs")) / "cron"
            hist_file = out_dir / "job_history.json"
            if hist_file.exists():
                with open(hist_file, encoding="utf-8") as f:
                    history = list(reversed(json.load(f)))[:limit]
        except Exception:
            pass
    return history


def get_next_runs() -> dict[str, str]:
    """Return next scheduled run time per job tag."""
    result = {}
    for job in schedule.jobs:
        tag = str(job.tags)
        next_run = job.next_run
        result[tag] = next_run.isoformat() if next_run else "unknown"
    return result


# ─── Main entry point ────────────────────────────────────────────────────────

async def _run_once(job_name: str):
    fn = NAMED_JOBS.get(job_name)
    if fn is None:
        print(f"❌ Unknown job '{job_name}'. Available: {', '.join(NAMED_JOBS)}")
        sys.exit(1)
    print(f"▶ Running job: {job_name}")
    await fn()
    print("✅ Done")


def main():
    parser = argparse.ArgumentParser(description="Hermes Cron Agent")
    parser.add_argument(
        "--run-now",
        metavar="JOB",
        help=f"Run a specific job immediately and exit. Jobs: {', '.join(NAMED_JOBS)}",
    )
    parser.add_argument(
        "--no-startup-run",
        action="store_true",
        help="Skip running jobs immediately on startup",
    )
    args = parser.parse_args()

    if args.run_now:
        asyncio.run(_run_once(args.run_now))
        return

    logger.info("🤖 Hermes Cron Agent starting…")
    register_jobs()

    # Run initial checks on startup
    if not args.no_startup_run:
        logger.info("▶ Running startup checks…")
        asyncio.run(job_dna_freshness_check())
        asyncio.run(job_obsidian_sync())

    # Graceful shutdown
    def _shutdown(sig, frame):
        logger.info("🛑 Hermes Cron Agent shutting down")
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("✅ Hermes Cron Agent running — press Ctrl+C to stop")
    while True:
        schedule.run_pending()
        time.sleep(30)  # check every 30s


if __name__ == "__main__":
    main()
