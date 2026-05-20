#!/usr/bin/env python3
"""
Recovery Worker — Quota-Aware Pause/Resume
==========================================
Polls paused SDLC tasks and requeues them once their cooldown expires.

Does NOT execute tasks. Role agents pick up re-queued (pending) tasks on their
next poll cycle and handle all Discord/Web notifications themselves.

Tick logic (runs every RECOVERY_POLL_SECONDS, default 300):
  1. list_paused_sdlc_tasks(now)  — tasks whose retry_after_at has passed
     (manual_token_fix tasks are never returned — they stay paused until
      an operator calls /resume or rotates the API key)
  2. Cross-check active provider cooldowns:
       - Exact match  (provider, model)  → model-specific cooldown
       - Broad match  (provider, "")     → provider-wide cooldown
     If still cooling: push task's retry_after_at forward to match cooldown, defer.
  3. resume_paused_sdlc_task(task_id) → status='pending', all pause fields cleared
  4. prune_expired_cooldowns()      — clean stale rows from provider_cooldowns table

Usage:
  python agents/recovery_worker.py                   # run forever
  python agents/recovery_worker.py --run-now         # one tick and exit
  python agents/recovery_worker.py --dry-run         # read-only tick and exit
  RECOVERY_POLL_SECONDS=120 python agents/recovery_worker.py
"""

import os
import sys
import json
import asyncio
import logging
import argparse
import signal
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

from shared.storage import Storage
from shared.web_bridge import get_bridge

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("recovery_worker")

DEFAULT_POLL_SECONDS = int(os.getenv("RECOVERY_POLL_SECONDS", "300"))

# ─── History (in-memory + disk) ──────────────────────────────────────────────

_tick_history: list[dict] = []
MAX_HISTORY = 200


def _flush_history():
    try:
        out_dir = Path(os.getenv("OUTPUT_BASE_PATH", "/app/outputs")) / "recovery"
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "tick_history.json", "w", encoding="utf-8") as f:
            json.dump(_tick_history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.debug(f"[Recovery] History flush failed: {e}")


def _write_runtime_status(stats: dict, paused_count: int, ready_count: int, cooldowns: list):
    """Write runtime_status.json — read by /api/runtime/cooldowns and /api/runtime/recovery."""
    try:
        out_dir = Path(os.getenv("OUTPUT_BASE_PATH", "/app/outputs")) / "recovery"
        out_dir.mkdir(parents=True, exist_ok=True)
        status = {
            "last_tick": stats["timestamp"],
            "worker_alive": True,
            "paused_count": paused_count,
            "ready_to_resume_count": ready_count,
            "cooldowns": cooldowns,
            "last_stats": {
                "requeued": stats["requeued"],
                "deferred": stats["deferred"],
                "pruned": stats["pruned"],
            },
        }
        with open(out_dir / "runtime_status.json", "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.debug(f"[Recovery] runtime_status write failed: {e}")


def _record_tick(stats: dict, paused_count: int = 0, ready_count: int = 0, cooldowns: list = None):
    _tick_history.append(stats)
    if len(_tick_history) > MAX_HISTORY:
        _tick_history.pop(0)
    _flush_history()
    _write_runtime_status(stats, paused_count, ready_count, cooldowns or [])


# ─── Core recovery class ──────────────────────────────────────────────────────

class RecoveryWorker:
    """
    Stateless recovery engine. Inject a Storage instance; call tick() repeatedly.
    dry_run=True reads DB but writes nothing.
    """

    def __init__(self, storage: Storage, dry_run: bool = False):
        self.storage = storage
        self.dry_run = dry_run

    async def tick(self) -> dict:
        """
        One recovery cycle.

        Returns a stats dict:
          {
            "timestamp": "2026-05-20T14:00:00",
            "requeued":  ["task-abc", ...],   # tasks moved to pending
            "deferred":  ["task-xyz", ...],   # still in provider cooldown
            "pruned":    3,                   # expired cooldown rows removed
            "dry_run":   False,
          }
        """
        now = datetime.utcnow().isoformat()

        # 1. Tasks whose retry_after_at has passed (manual_token_fix excluded by storage)
        ready_tasks = self.storage.list_paused_sdlc_tasks(now)
        ready_count = len(ready_tasks)

        # 2. Build active cooldown index: (provider, model) → retry_after_at
        active_cooldowns = self.storage.get_active_provider_cooldowns(now)
        active_cds: dict[tuple, str] = {
            (cd["provider"], cd["model"]): cd["retry_after_at"]
            for cd in active_cooldowns
        }

        requeued: list[str] = []
        deferred: list[str] = []

        for task in ready_tasks:
            cd_until = self._provider_cooldown_for(task, active_cds)

            if cd_until:
                # Provider still cooling — push task's deadline forward so it
                # won't show up again until the provider cooldown also expires.
                logger.info(
                    f"[Recovery] Task {task.id} deferred — "
                    f"provider '{task.pause_provider}' in cooldown until {cd_until[:19]}"
                )
                if not self.dry_run:
                    self.storage.update_task_retry_after(task.id, cd_until)
                deferred.append(task.id)
            else:
                logger.info(
                    f"[Recovery] Task {task.id} requeued "
                    f"({task.pause_reason} on '{task.pause_provider}')"
                )
                if not self.dry_run:
                    self.storage.resume_paused_sdlc_task(task.id)
                    await get_bridge().post_event(
                        role_key=task.role or "system",
                        event_type="agent.task.resumed.auto",
                        task_name=task.title or task.id,
                        status="pending",
                        summary=(
                            f"Task {task.id} auto-requeued by recovery worker: "
                            f"{task.pause_reason} cooldown expired."
                        ),
                        sdlc_task_id=task.id,
                        project_id=task.project_id,
                        metadata=dict(
                            pause_reason=task.pause_reason,
                            pause_provider=task.pause_provider,
                        ),
                        actor="recovery_worker",
                    )
                requeued.append(task.id)

        # 3. Prune stale cooldown rows
        pruned = 0
        if not self.dry_run:
            pruned = self.storage.prune_expired_cooldowns(now)

        # 4. Count all paused tasks (for runtime_status.json)
        paused_count = self._count_all_paused()

        stats = {
            "timestamp": now[:19],
            "requeued":  requeued,
            "deferred":  deferred,
            "pruned":    pruned,
            "dry_run":   self.dry_run,
        }

        if requeued or deferred or pruned:
            logger.info(
                f"[Recovery] tick done — "
                f"requeued={len(requeued)} deferred={len(deferred)} pruned={pruned}"
                + (" [DRY RUN]" if self.dry_run else "")
            )

        return stats, paused_count, ready_count, active_cooldowns

    # ── helpers ───────────────────────────────────────────────────────────────

    def _count_all_paused(self) -> int:
        """Count total paused tasks in DB (all policies, all retry times)."""
        try:
            import sqlite3 as _sq
            with _sq.connect(self.storage.db_path) as conn:
                return conn.execute(
                    "SELECT COUNT(*) FROM sdlc_tasks WHERE status='paused'"
                ).fetchone()[0]
        except Exception:
            return 0

    @staticmethod
    def _provider_cooldown_for(task, active_cds: dict) -> str:
        """
        Return the active cooldown deadline (ISO str) for this task's provider,
        or "" if none applies.

        Checks in order:
          1. (provider, model)  — model-specific cooldown
          2. (provider, "")     — provider-wide cooldown (model="")
        If task.pause_provider is empty, no cooldown applies (return "").
        """
        if not task.pause_provider:
            return ""
        return (
            active_cds.get((task.pause_provider, task.pause_model), "")
            or active_cds.get((task.pause_provider, ""), "")
        )


# ─── Singleton storage ────────────────────────────────────────────────────────

_storage_instance: Storage | None = None


def _get_storage() -> Storage:
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = Storage()
    return _storage_instance


# ─── Run modes ────────────────────────────────────────────────────────────────

async def run_once(dry_run: bool = False):
    worker = RecoveryWorker(_get_storage(), dry_run=dry_run)
    stats, paused_count, ready_count, cooldowns = await worker.tick()
    _record_tick(stats, paused_count, ready_count, cooldowns)
    label = "[DRY RUN] " if dry_run else ""
    print(
        f"{label}requeued={len(stats['requeued'])} "
        f"deferred={len(stats['deferred'])} "
        f"pruned={stats['pruned']}"
    )
    if stats["requeued"]:
        print("  Requeued:", ", ".join(stats["requeued"]))
    if stats["deferred"]:
        print("  Deferred:", ", ".join(stats["deferred"]))


async def run_forever(poll_seconds: int):
    logger.info(f"✅ Recovery Worker running — poll every {poll_seconds}s (Ctrl+C to stop)")
    worker = RecoveryWorker(_get_storage())

    # Run immediately on startup
    stats, paused_count, ready_count, cooldowns = await worker.tick()
    _record_tick(stats, paused_count, ready_count, cooldowns)

    while True:
        await asyncio.sleep(poll_seconds)
        stats, paused_count, ready_count, cooldowns = await worker.tick()
        _record_tick(stats, paused_count, ready_count, cooldowns)


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Recovery Worker — Quota-Aware Pause/Resume")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Run one tick and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read-only tick — show what would be requeued without mutating DB",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=DEFAULT_POLL_SECONDS,
        help=f"Poll interval in seconds (default: {DEFAULT_POLL_SECONDS}, env: RECOVERY_POLL_SECONDS)",
    )
    args = parser.parse_args()

    def _shutdown(sig, frame):
        logger.info("🛑 Recovery Worker shutting down")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    if args.run_now or args.dry_run:
        asyncio.run(run_once(dry_run=args.dry_run))
    else:
        logger.info(f"🤖 Recovery Worker starting (poll={args.poll_seconds}s)")
        asyncio.run(run_forever(args.poll_seconds))


if __name__ == "__main__":
    main()
