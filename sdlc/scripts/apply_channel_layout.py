"""
- Delete old/shared channels: #approvals, #room-output, #room-timelog
- Update topics of all existing channels to match new config
Run: python3 scripts/apply_channel_layout.py
"""
import os, sys, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import discord
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from shared.channel_config import DISCORD_CATEGORIES

GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
TOKEN    = os.getenv("CEO_DISCORD_TOKEN", "")

DELETE_CHANNELS = {"approvals", "room-output", "room-timelog"}


async def main():
    client = discord.Client(intents=discord.Intents.default())

    @client.event
    async def on_ready():
        guild = client.get_guild(GUILD_ID)
        if not guild:
            print(f"❌ Guild {GUILD_ID} not found"); await client.close(); return

        existing = {ch.name: ch for ch in guild.text_channels}

        # ── Step 1: Delete old shared channels ───────────────────────
        print("\n── Deleting old channels ────────────────────────────")
        for name in DELETE_CHANNELS:
            ch = existing.get(name)
            if ch:
                await ch.delete(reason="Replaced by per-role channels")
                print(f"  🗑️  #{name} deleted")
            else:
                print(f"  ⏭️  #{name} not found, skipping")

        # ── Step 2: Update topics of existing channels ────────────────
        print("\n── Updating channel topics ──────────────────────────")
        existing = {ch.name: ch for ch in guild.text_channels}  # refresh

        updated = 0
        for block in DISCORD_CATEGORIES:
            for ch_def in block["channels"]:
                name  = ch_def["name"]
                topic = ch_def["topic"]
                ch    = existing.get(name)
                if ch is None:
                    print(f"  ⏭️  #{name} — not found")
                    continue
                if ch.topic == topic:
                    print(f"  ✅ #{name} — already correct")
                    continue
                try:
                    await ch.edit(topic=topic)
                    print(f"  ✏️  #{name} — topic updated")
                    updated += 1
                    await asyncio.sleep(0.4)
                except Exception as e:
                    print(f"  ❌ #{name} — {e}")

        print(f"\n🎉 Done — {updated} topics updated.")
        await client.close()

    await client.start(TOKEN)

asyncio.run(main())
