"""List all channels in the Discord server grouped by category."""
import os, sys, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import discord
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
TOKEN    = os.getenv("CEO_DISCORD_TOKEN", "")

NEW_CHANNELS = {
    "ceo-input","project-dashboard",
    "ceo-inbox","pm-inbox","ba-inbox","sa-inbox","uxui-inbox","dev-inbox","qa-inbox","devops-inbox",
    "ceo-room","pm-room","ba-room","sa-room","uxui-room","dev-room","qa-room","devops-room",
    "ceo-approve","pm-approve","ba-approve","sa-approve","uxui-approve","dev-approve","qa-approve","devops-approve",
    "room-output","room-timelog",
    "room-all-role-for-discus","report-agent","report-output",
}

async def main():
    client = discord.Client(intents=discord.Intents.default())

    @client.event
    async def on_ready():
        guild = client.get_guild(GUILD_ID)
        if not guild:
            print(f"Guild {GUILD_ID} not found"); await client.close(); return

        # Group by category
        no_cat = [ch for ch in guild.text_channels if ch.category is None]
        cats   = {}
        for ch in guild.text_channels:
            if ch.category:
                cats.setdefault(ch.category.name, []).append(ch)

        print(f"\n{'='*55}")
        print(f" ALL CHANNELS IN: {guild.name}")
        print(f"{'='*55}")

        if no_cat:
            print("\n[No Category]")
            for ch in no_cat:
                tag = "✅" if ch.name in NEW_CHANNELS else "⚠️ OLD"
                print(f"  {tag}  #{ch.name}")

        for cat_name, channels in cats.items():
            print(f"\n[{cat_name}]")
            for ch in channels:
                tag = "✅" if ch.name in NEW_CHANNELS else "⚠️ OLD"
                print(f"  {tag}  #{ch.name}")

        old = [ch for ch in guild.text_channels if ch.name not in NEW_CHANNELS]
        print(f"\n{'='*55}")
        print(f" Total channels : {len(guild.text_channels)}")
        print(f" ✅ New/Active  : {len(guild.text_channels) - len(old)}")
        print(f" ⚠️  Old/Unused  : {len(old)}")
        if old:
            print(f"\n Old channels: {', '.join('#'+c.name for c in old)}")
        print(f"{'='*55}")
        await client.close()

    await client.start(TOKEN)

asyncio.run(main())
