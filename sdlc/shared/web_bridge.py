"""
WebAppBridge — Discord Bot ↔ Next.js Web App Integration

POST ไปยัง /api/agent-activity/ingest ทุกครั้งที่ agent มี lifecycle event
ทำให้ Web UI (port 3000) แสดงสถานะ real-time โดยไม่ต้องเปิด Discord

Events ที่ส่ง:
  task_started      → agent เริ่มทำงาน
  task_completed    → agent ทำเสร็จ รอ approval (status=waiting_approval)
  approved          → Human กด approve
  revision_requested → Human กด revise
  rejected          → Human กด reject
  error             → agent เจอ error

ตัวแปรใน .env:
  WEB_APP_URL=http://localhost:3000
  AGENT_SYNC_TOKEN=<same-as-reporting.agent_sync_ingest_token-in-system_configs>
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Optional

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

logger = logging.getLogger(__name__)


class WebAppBridge:
    """
    ส่ง agent lifecycle events → Next.js /api/agent-activity/ingest

    ใช้ httpx async client — ไม่ block Discord event loop
    ถ้า web app offline → log warning แต่ไม่ crash
    """

    def __init__(self):
        self._web_url   = os.getenv("WEB_APP_URL", "http://localhost:3001").rstrip("/")
        self.base_url   = self._web_url  # alias kept for existing callers
        self.token      = os.getenv("AGENT_SYNC_TOKEN", "")
        self.enabled    = bool(self.token)
        self.timeout    = 10.0  # seconds
        self._client: Optional["httpx.AsyncClient"] = None

        if not self.enabled:
            logger.warning(
                "WebAppBridge: AGENT_SYNC_TOKEN not set — "
                "agent activity will NOT be reported to the web app"
            )

    async def _get_client(self) -> "httpx.AsyncClient":
        if not _HAS_HTTPX:
            raise RuntimeError("httpx not installed — run: pip install httpx")
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    @staticmethod
    def _to_snake(payload: dict) -> dict:
        """Convert camelCase top-level keys to snake_case for the ingest API."""
        mapping = {
            "roleKey":       "role_key",
            "eventType":     "event_type",
            "taskName":      "task_name",
            "artifactRef":   "artifact_ref",
            "channelTarget": "channel_target",
        }
        return {mapping.get(k, k): v for k, v in payload.items()}

    async def _post(self, payload: dict) -> bool:
        """
        POST payload → /api/agent-activity/ingest
        ส่งคืน True ถ้าสำเร็จ, False ถ้า fail (ไม่ raise)
        """
        if not self.enabled:
            return False
        if not _HAS_HTTPX:
            logger.error("WebAppBridge: httpx not installed")
            return False

        url = f"{self.base_url}/api/agent-activity/ingest"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        try:
            client = await self._get_client()
            resp = await client.post(url, json=self._to_snake(payload), headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    logger.debug(f"WebAppBridge: POST ok — {payload.get('eventType')}")
                    return True
                else:
                    logger.warning(f"WebAppBridge: API returned success=false — {data}")
                    return False
            else:
                logger.warning(
                    f"WebAppBridge: HTTP {resp.status_code} — {resp.text[:200]}"
                )
                return False
        except Exception as e:
            logger.warning(f"WebAppBridge: POST failed ({type(e).__name__}: {e})")
            return False

    # ─── Public Event Methods ──────────────────────────────────────────────────

    async def task_started(
        self,
        role_key: str,
        project_id: str,
        project_name: str,
        task_name: str,
        model_id: str,
        revision_count: int = 0,
    ):
        """Agent เริ่มทำงาน"""
        await self._post({
            "roleKey":      role_key,
            "eventType":    "task_started",
            "taskName":     task_name,
            "status":       "in_progress",
            "summary":      (
                f"{role_key.upper()} Agent เริ่มทำงาน"
                + (f" (Revision #{revision_count})" if revision_count > 0 else "")
            ),
            "channelTarget": f"{role_key}-inbox",
            "metadata": {
                "project_id":     project_id,
                "project_name":   project_name,
                "model_id":       model_id,
                "revision_count": revision_count,
                "started_at":     datetime.utcnow().isoformat() + "Z",
            },
        })

    async def task_completed(
        self,
        role_key: str,
        project_id: str,
        project_name: str,
        task_name: str,
        summary: str,
        files: list,
        model_id: str,
        cost_usd: float,
        duration_seconds: float,
        revision_count: int = 0,
        artifact_ref: str = "",
        status: str = "waiting_approval",
        sdlc_task_id: str = "",
        discord_message_id: str = "",
        preferred_model: str = "",
        routed_model: str = "",
        fallback_used: bool = False,
        artifacts: Optional[list] = None,
        error_info: str = "",
    ):
        """Agent ทำเสร็จ — status default = waiting_approval (role_tasks) หรือ completed (sdlc_tasks)"""
        artifact_url = (
            f"{self._web_url}/api/project-logs/files"
            f"?project={project_id}&role={role_key}"
        )
        await self._post({
            "roleKey":            role_key,
            "eventType":          "task_completed",
            "taskName":           task_name,
            "status":             status,
            "summary":            summary[:1000] if summary else "",
            "artifactRef":        artifact_ref,
            "channelTarget":      f"{role_key}-output",
            # Identity fields — passed through to approval_item on waiting_approval
            "sdlc_task_id":       sdlc_task_id,
            "project_id":         project_id,
            "discord_message_id": discord_message_id,
            # Artifact registry entries
            "artifacts":          artifacts or [],
            "metadata": {
                "project_id":       project_id,
                "project_name":     project_name,
                "files":            files,
                # Model observability
                "model_id":         model_id,
                "preferred_model":  preferred_model,
                "routed_model":     routed_model,
                "fallback_used":    fallback_used,
                "cost_usd":         round(cost_usd, 6),
                "duration_seconds": round(duration_seconds, 1),
                "revision_count":   revision_count,
                "error_info":       error_info,
                "completed_at":     datetime.utcnow().isoformat() + "Z",
                "artifact_url":     artifact_url,
            },
        })

    async def approved(
        self,
        role_key: str,
        project_id: str,
        project_name: str,
        task_name: str,
        next_role: Optional[str],
        approver: str = "human",
    ):
        """Human กด !approve"""
        await self._post({
            "roleKey":      role_key,
            "eventType":    "approved",
            "taskName":     task_name,
            "status":       "approved",
            "summary":      (
                f"✅ {role_key.upper()} phase approved"
                + (f" → ส่งต่อ {next_role.upper()}" if next_role else " → Project Complete!")
            ),
            "channelTarget": f"{role_key}-approve",
            "metadata": {
                "project_id":   project_id,
                "project_name": project_name,
                "next_role":    next_role or "completed",
                "approver":     approver,
                "approved_at":  datetime.utcnow().isoformat() + "Z",
            },
        })

    async def revision_requested(
        self,
        role_key: str,
        project_id: str,
        project_name: str,
        task_name: str,
        comment: str,
        revision_count: int,
        approver: str = "human",
    ):
        """Human กด !revise"""
        await self._post({
            "roleKey":      role_key,
            "eventType":    "revision_requested",
            "taskName":     task_name,
            "status":       "rework_requested",
            "summary":      f"🔄 Revision #{revision_count} — {comment or '(ไม่มี comment)'}",
            "channelTarget": f"{role_key}-approve",
            "metadata": {
                "project_id":     project_id,
                "project_name":   project_name,
                "comment":        comment,
                "revision_count": revision_count,
                "approver":       approver,
                "requested_at":   datetime.utcnow().isoformat() + "Z",
            },
        })

    async def rejected(
        self,
        role_key: str,
        project_id: str,
        project_name: str,
        task_name: str,
        reason: str,
        approver: str = "human",
    ):
        """Human กด !reject"""
        await self._post({
            "roleKey":      role_key,
            "eventType":    "rejected",
            "taskName":     task_name,
            "status":       "rejected",
            "summary":      f"❌ Rejected at {role_key.upper()} — {reason or '(ไม่ระบุ)'}",
            "channelTarget": f"{role_key}-approve",
            "metadata": {
                "project_id":   project_id,
                "project_name": project_name,
                "reason":       reason,
                "approver":     approver,
                "rejected_at":  datetime.utcnow().isoformat() + "Z",
            },
        })

    async def error(
        self,
        role_key: str,
        project_id: str,
        project_name: str,
        task_name: str,
        error_message: str,
    ):
        """Agent เจอ error"""
        await self._post({
            "roleKey":      role_key,
            "eventType":    "error",
            "taskName":     task_name,
            "status":       "blocked",
            "summary":      f"❌ Error in {role_key.upper()}: {error_message[:300]}",
            "channelTarget": f"{role_key}-inbox",
            "metadata": {
                "project_id":   project_id,
                "project_name": project_name,
                "error":        error_message,
                "occurred_at":  datetime.utcnow().isoformat() + "Z",
            },
        })

    async def hot_cache_update(
        self,
        role_key: str,
        project_id: str,
        project_name: str,
        summary: str,
        cache_key: str = "current_project",
        status: str = "in_progress",
    ):
        """อัปเดต "Current Project" widget ใน web dashboard ทันที"""
        # A1: ingest API requires non-empty summary — fallback ป้องกัน silent reject
        if not summary or not summary.strip():
            summary = f"{project_name} — {role_key.upper()} {status}"
        await self._post({
            "roleKey":           role_key,
            "eventType":         "task_started",
            "taskName":          project_name,
            "status":            status,
            "summary":           summary,
            "channelTarget":     f"{role_key}-inbox",
            "hot_cache_key":     cache_key,
            "hot_cache_title":   project_name,
            "hot_cache_summary": summary,
            "hot_cache_scope":   "global",
            "hot_cache_status":  status,
            "metadata": {
                "project_id":   project_id,
                "project_name": project_name,
            },
        })

    async def devops_blocked(
        self,
        role_key: str,
        project_id: str,
        project_name: str,
        task_name: str,
        task_id: str,
        blocked_summary: str,
        blockers: list,
    ):
        """Notify web app of a blocked DEVOPS deployment check (infra/tooling issue).
        Logged to agent_activity_logs; does NOT create an approval_item."""
        detail = "; ".join(blockers[:3]) if blockers else blocked_summary
        await self._post({
            "roleKey":       role_key,
            "eventType":     "devops_blocked",
            "taskName":      task_name,
            "status":        "blocked",
            "summary":       f"🚫 Deployment blocked [{task_id}]: {detail}"[:500],
            "channelTarget": f"{role_key}-inbox",
            "metadata": {
                "project_id":    project_id,
                "project_name":  project_name,
                "task_id":       task_id,
                "blockers":      blockers,
                "blocked_at":    datetime.utcnow().isoformat() + "Z",
            },
        })

    async def mark_decision_processed(self, approval_id: int, status: str = "") -> bool:
        """
        Mark a web decision as processed by the bot runtime.
        Call this after successfully executing the decision in Discord so the
        item is excluded from future poll results even after a bot restart.
        """
        if not self.enabled or not approval_id:
            return False
        url = f"{self.base_url}/api/runtime/decisions/{approval_id}/processed"
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            client = await self._get_client()
            resp = await client.post(url, json={"status": status}, headers=headers)
            return resp.status_code == 200 and resp.json().get("success", False)
        except Exception as e:
            logger.warning(f"WebAppBridge.mark_decision_processed failed: {e}")
            return False

    async def fetch_web_decisions(self, role_key: str, since_id: int = 0) -> list:
        """
        ดึง approval items ที่ถูก decide ผ่าน Web UI (status != waiting_approval)
        ส่งคืน list of decision dicts ที่บอทต้องไป execute ใน Discord
        """
        if not self.enabled:
            return []
        url = f"{self.base_url}/api/runtime/decisions"
        params = f"role_key={role_key}&since_id={since_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            client = await self._get_client()
            resp = await client.get(f"{url}?{params}", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("items", [])
            return []
        except Exception as e:
            logger.warning(f"WebAppBridge.fetch_web_decisions failed: {e}")
            return []

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ─── Singleton ─────────────────────────────────────────────────────────────────

_bridge_instance: Optional[WebAppBridge] = None


def get_bridge() -> WebAppBridge:
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = WebAppBridge()
    return _bridge_instance
