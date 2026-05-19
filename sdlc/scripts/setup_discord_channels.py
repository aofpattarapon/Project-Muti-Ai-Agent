"""
Creates all Discord channels for the Multi-AI-Agent SDLC pipeline (new layout).
Run: python3 scripts/setup_discord_channels.py
"""
import os
import sys
import asyncio

# Ensure SDLC root is on path before any local imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import discord
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
TOKEN    = os.getenv("CEO_DISCORD_TOKEN", "")

from shared.channel_config import DISCORD_CATEGORIES


async def setup():
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        guild = client.get_guild(GUILD_ID)
        if not guild:
            print(f"❌ Guild {GUILD_ID} not found")
            await client.close()
            return

        existing_ch  = {ch.name for ch in guild.channels}
        existing_cat = {cat.name: cat for cat in guild.categories}
        created = 0

        for block in DISCORD_CATEGORIES:
            cat_name = block["name"]
            if cat_name not in existing_cat:
                cat = await guild.create_category(cat_name)
                existing_cat[cat_name] = cat
                print(f"  📁 Created category: {cat_name}")
            else:
                cat = existing_cat[cat_name]

            for ch in block["channels"]:
                if ch["name"] not in existing_ch:
                    await guild.create_text_channel(ch["name"], category=cat, topic=ch["topic"])
                    print(f"    ✅ #{ch['name']}")
                    created += 1
                else:
                    print(f"    ⏭️  #{ch['name']} exists")

        print(f"\n🎉 Done — {created} new channels created.")
        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(setup())
