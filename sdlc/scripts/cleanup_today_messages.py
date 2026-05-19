"""
Delete all Discord messages from today (2026-05-15) only.
Messages before 2026-05-15 are untouched.
Run: python3 scripts/cleanup_today_messages.py
"""
import os
import sys
import asyncio
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import discord
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
TOKEN    = os.getenv("CEO_DISCORD_TOKEN", "")

# Delete messages ON or AFTER this date (UTC midnight)
CUTOFF = datetime(2026, 5, 15, 0, 0, 0, tzinfo=timezone.utc)


async def cleanup():
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        guild = client.get_guild(GUILD_ID)
        if not guild:
            print(f"❌ Guild {GUILD_ID} not found")
            await client.close()
            return

        total_deleted = 0

        for channel in guild.text_channels:
            channel_deleted = 0
            try:
                async for msg in channel.history(limit=None, after=CUTOFF):
                    try:
                        await msg.delete()
                        channel_deleted += 1
                        total_deleted += 1
                        await asyncio.sleep(0.5)  # rate limit safety
                    except discord.Forbidden:
                        pass
                    except discord.NotFound:
                        pass
                    except Exception as e:
                        print(f"    ⚠️  Could not delete msg {msg.id}: {e}")

                if channel_deleted:
                    print(f"  🗑️  #{channel.name}: {channel_deleted} messages deleted")
                else:
                    print(f"  ✅ #{channel.name}: nothing to delete")

            except discord.Forbidden:
                print(f"  🚫 #{channel.name}: no read permission, skipping")
            except Exception as e:
                print(f"  ❌ #{channel.name}: error — {e}")

        print(f"\n🎉 Done — {total_deleted} messages deleted from 2026-05-15 onwards.")
        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(cleanup())
