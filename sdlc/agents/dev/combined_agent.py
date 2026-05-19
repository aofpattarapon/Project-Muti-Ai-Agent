"""
DEV Agent entry point for PM2.
Uses the existing DevAgent (role_name="dev") — frontend+backend in one phase.
"""
import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'), override=False)

from agents.dev.agent import DEVAgent


def main():
    token = os.getenv("FRONTEND_DISCORD_TOKEN") or os.getenv("DEV_DISCORD_TOKEN")
    if not token:
        raise ValueError("FRONTEND_DISCORD_TOKEN (or DEV_DISCORD_TOKEN) not set in .env")
    agent = DEVAgent()
    agent.run(token)


if __name__ == "__main__":
    main()
