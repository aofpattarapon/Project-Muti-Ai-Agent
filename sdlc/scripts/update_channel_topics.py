"""
Update topics of existing Discord channels to match new channel_config rules.
Does NOT create new channels — only edits topics of channels that already exist.
Run: python3 scripts/update_channel_topics.py
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import discord
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
TOKEN    = os.getenv("CEO_DISCORD_TOKEN", "")

from shared.channel_config import DISCORD_CATEGORIES


async def update_topics():
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        guild = client.get_guild(GUILD_ID)
        if not guild:
            print(f"❌ Guild {GUILD_ID} not found")
            await client.close()
            return

        # Build lookup: channel name → channel object
        existing = {ch.name: ch for ch in guild.text_channels}
        updated = 0
        skipped = 0

        for block in DISCORD_CATEGORIES:
            print(f"\n📁 {block['name']}")
            for ch_def in block["channels"]:
                name  = ch_def["name"]
                topic = ch_def["topic"]
                ch    = existing.get(name)

                if ch is None:
                    print(f"    ⏭️  #{name} — not found, skipping")
                    skipped += 1
                    continue

                if ch.topic == topic:
                    print(f"    ✅ #{name} — topic already up to date")
                    continue

                try:
                    await ch.edit(topic=topic)
                    print(f"    ✏️  #{name} — topic updated")
                    updated += 1
                    await asyncio.sleep(0.5)  # rate limit
                except discord.Forbidden:
                    print(f"    🚫 #{name} — no permission to edit")
                except Exception as e:
                    print(f"    ❌ #{name} — error: {e}")

        print(f"\n🎉 Done — {updated} topics updated, {skipped} channels not found.")
        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(update_topics())
