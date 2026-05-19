"""
Discord Channel Configuration — 1 Agent, 1 Role, 1 Room
"""

from dataclasses import dataclass
from typing import Optional
import discord


@dataclass
class RoleChannels:
    inbox:   str   # #{role}-inbox   — manual task assignment
    room:    str   # #{role}-room    — talk/wait with agent
    output:  str   # #{role}-output  — agent posts results here
    timelog: str   # #{role}-timelog — Jira-style time log
    approve: str   # #{role}-approve — approval (1 msg per task)


CONTROL_INPUT = "ceo-input"
CONTROL_DASH  = "project-dashboard"

ROLE_CHANNELS: dict[str, RoleChannels] = {
    "ceo":    RoleChannels("ceo-inbox",    "ceo-room",    "ceo-output",    "ceo-timelog",    "ceo-approve"),
    "pm":     RoleChannels("pm-inbox",     "pm-room",     "pm-output",     "pm-timelog",     "pm-approve"),
    "ba":     RoleChannels("ba-inbox",     "ba-room",     "ba-output",     "ba-timelog",     "ba-approve"),
    "sa":     RoleChannels("sa-inbox",     "sa-room",     "sa-output",     "sa-timelog",     "sa-approve"),
    "uxui":   RoleChannels("uxui-inbox",   "uxui-room",   "uxui-output",   "uxui-timelog",   "uxui-approve"),
    "dev":    RoleChannels("dev-inbox",    "dev-room",    "dev-output",    "dev-timelog",    "dev-approve"),
    "qa":     RoleChannels("qa-inbox",     "qa-room",     "qa-output",     "qa-timelog",     "qa-approve"),
    "devops": RoleChannels("devops-inbox", "devops-room", "devops-output", "devops-timelog", "devops-approve"),
}

WORKFLOW_ORDER = ["ceo", "pm", "ba", "sa", "uxui", "dev", "qa", "devops"]


def get_next_role(current_role: str) -> Optional[str]:
    try:
        idx = WORKFLOW_ORDER.index(current_role)
        return WORKFLOW_ORDER[idx + 1] if idx + 1 < len(WORKFLOW_ORDER) else None
    except ValueError:
        return None


async def get_guild_channel(guild: discord.Guild, name: str) -> Optional[discord.TextChannel]:
    return discord.utils.get(guild.text_channels, name=name)


# ─── Discord Category + Channel Definitions ─────────────────────────────────

DISCORD_CATEGORIES = [
    {
        "name": "🎮 CONTROL",
        "channels": [
            {"name": "ceo-input",         "topic": "👤 Assign project or task — !new ProjectName | description"},
            {"name": "project-dashboard", "topic": "📊 Summary of all pipeline processes"},
        ],
    },
    {
        "name": "📥 INBOX — Assign Tasks",
        "channels": [
            {"name": "ceo-inbox",    "topic": "📥 Manually assign task to CEO agent"},
            {"name": "pm-inbox",     "topic": "📥 Manually assign task to PM agent"},
            {"name": "ba-inbox",     "topic": "📥 Manually assign task to BA agent"},
            {"name": "sa-inbox",     "topic": "📥 Manually assign task to SA agent"},
            {"name": "uxui-inbox",   "topic": "📥 Manually assign task to UX/UI agent"},
            {"name": "dev-inbox",    "topic": "📥 Manually assign task to DEV agent"},
            {"name": "qa-inbox",     "topic": "📥 Manually assign task to QA agent"},
            {"name": "devops-inbox", "topic": "📥 Manually assign task to DevOps agent"},
        ],
    },
    {
        "name": "💬 ROOMS — Talk with Agents",
        "channels": [
            {"name": "ceo-room",    "topic": "💬 Talk with CEO agent / status updates"},
            {"name": "pm-room",     "topic": "💬 Talk with PM agent / status updates"},
            {"name": "ba-room",     "topic": "💬 Talk with BA agent / status updates"},
            {"name": "sa-room",     "topic": "💬 Talk with SA agent / status updates"},
            {"name": "uxui-room",   "topic": "💬 Talk with UX/UI agent / status updates"},
            {"name": "dev-room",    "topic": "💬 Talk with DEV agent / status updates"},
            {"name": "qa-room",     "topic": "💬 Talk with QA agent / status updates"},
            {"name": "devops-room", "topic": "💬 Talk with DevOps agent / status updates"},
        ],
    },
    {
        "name": "📤 OUTPUT — Per Role",
        "channels": [
            {"name": "ceo-output",    "topic": "📤 CEO agent output & results"},
            {"name": "pm-output",     "topic": "📤 PM agent output & results"},
            {"name": "ba-output",     "topic": "📤 BA agent output & results"},
            {"name": "sa-output",     "topic": "📤 SA agent output & results"},
            {"name": "uxui-output",   "topic": "📤 UX/UI agent output & results"},
            {"name": "dev-output",    "topic": "📤 DEV agent output & results"},
            {"name": "qa-output",     "topic": "📤 QA agent output & results"},
            {"name": "devops-output", "topic": "📤 DevOps agent output & results"},
        ],
    },
    {
        "name": "⏱️ TIMELOG — Per Role",
        "channels": [
            {"name": "ceo-timelog",    "topic": "⏱️ CEO Jira-style time log"},
            {"name": "pm-timelog",     "topic": "⏱️ PM Jira-style time log"},
            {"name": "ba-timelog",     "topic": "⏱️ BA Jira-style time log"},
            {"name": "sa-timelog",     "topic": "⏱️ SA Jira-style time log"},
            {"name": "uxui-timelog",   "topic": "⏱️ UX/UI Jira-style time log"},
            {"name": "dev-timelog",    "topic": "⏱️ DEV Jira-style time log"},
            {"name": "qa-timelog",     "topic": "⏱️ QA Jira-style time log"},
            {"name": "devops-timelog", "topic": "⏱️ DevOps Jira-style time log"},
        ],
    },
    {
        "name": "✅ APPROVALS — Per Role",
        "channels": [
            {"name": "ceo-approve",    "topic": "✅ CEO approval — reply !approve | !revise [note] | !reject [reason]"},
            {"name": "pm-approve",     "topic": "✅ PM approval — reply !approve | !revise [note] | !reject [reason]"},
            {"name": "ba-approve",     "topic": "✅ BA approval — reply !approve | !revise [note] | !reject [reason]"},
            {"name": "sa-approve",     "topic": "✅ SA approval — reply !approve | !revise [note] | !reject [reason]"},
            {"name": "uxui-approve",   "topic": "✅ UX/UI approval — reply !approve | !revise [note] | !reject [reason]"},
            {"name": "dev-approve",    "topic": "✅ DEV approval — reply !approve | !revise [note] | !reject [reason]"},
            {"name": "qa-approve",     "topic": "✅ QA approval — reply !approve | !revise [note] | !reject [reason]"},
            {"name": "devops-approve", "topic": "✅ DevOps approval — reply !approve | !revise [note] | !reject [reason]"},
        ],
    },
]
