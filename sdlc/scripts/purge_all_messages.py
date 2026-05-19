"""
Delete ALL Discord messages — ใช้ bulk-delete สำหรับข้อความ < 14 วัน (เร็ว)
และ delete ทีละข้อความสำหรับข้อความเก่ากว่านั้น

Run: python3 scripts/purge_all_messages.py
"""
import os
import sys
import asyncio
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import discord
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
TOKEN    = os.getenv("CEO_DISCORD_TOKEN", "")
BULK_CUTOFF = datetime.now(timezone.utc) - timedelta(days=13, hours=23)


async def purge_channel(channel: discord.TextChannel) -> int:
    """Purge a channel using bulk-delete where possible, fallback to single-delete."""
    deleted = 0
    try:
        # Collect all messages
        all_messages = []
        async for msg in channel.history(limit=None):
            all_messages.append(msg)

        if not all_messages:
            print(f"  ✅ #{channel.name}: empty")
            return 0

        # Split into bulk-eligible (< 14 days) and old
        bulk_msgs = [m for m in all_messages if m.created_at >= BULK_CUTOFF]
        old_msgs  = [m for m in all_messages if m.created_at < BULK_CUTOFF]

        # Bulk delete in batches of 100
        for i in range(0, len(bulk_msgs), 100):
            batch = bulk_msgs[i:i + 100]
            if len(batch) == 1:
                await batch[0].delete()
            elif len(batch) > 1:
                await channel.delete_messages(batch)
            deleted += len(batch)
            await asyncio.sleep(1.0)

        # Delete old messages one by one
        for msg in old_msgs:
            try:
                await msg.delete()
                deleted += 1
                await asyncio.sleep(0.6)
            except (discord.Forbidden, discord.NotFound):
                pass

        print(f"  🗑️  #{channel.name}: {deleted} deleted ({len(bulk_msgs)} bulk + {len(old_msgs)} single)")

    except discord.Forbidden:
        print(f"  🚫 #{channel.name}: no permission")
    except Exception as e:
        print(f"  ❌ #{channel.name}: {e}")

    return deleted


async def purge():
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"\n🤖 Logged in as {client.user}")
        guild = client.get_guild(GUILD_ID)
        if not guild:
            print(f"❌ Guild {GUILD_ID} not found")
            await client.close()
            return

        total = 0
        channels = sorted(guild.text_channels, key=lambda c: c.name)
        print(f"🔍 Found {len(channels)} text channels in {guild.name}\n")

        for channel in channels:
            total += await purge_channel(channel)

        print(f"\n🎉 Done — {total} total messages deleted across all channels.")
        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    print("⚠️  This will delete ALL messages in ALL channels.")
    print(f"   Guild: {GUILD_ID}")
    confirm = input("   Type 'yes' to proceed: ").strip().lower()
    if confirm == "yes":
        asyncio.run(purge())
    else:
        print("Aborted.")
