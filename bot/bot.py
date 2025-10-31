import os
import io
import httpx
import discord
from discord import app_commands
from discord.ext import commands

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="-p ", intents=intents)

class SlotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="send_slot", description="Send a configured slot image to the configured channel")
    @app_commands.describe(guild_id="Guild ID to use (copy from dashboard)", slot="Slot number 2-25")
    async def send_slot(self, interaction: discord.Interaction, guild_id: str, slot: int):
        await interaction.response.defer(thinking=True)
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{BACKEND_URL}/api/guilds/{guild_id}/channel")
            if r.status_code != 200:
                await interaction.followup.send("Could not fetch guild configuration.")
                return
            channel_id = r.json().get("channel_id")
            if not channel_id:
                await interaction.followup.send("No channel configured for this guild in dashboard. Please set channel first.")
                return
            gen = await client.get(f"{BACKEND_URL}/api/generate/{guild_id}/{slot}", timeout=120)
            if gen.status_code != 200:
                await interaction.followup.send(f"Failed to generate slot {slot}.")
                return
            content_type = gen.headers.get("content-type","image/png")
            ext = "gif" if "gif" in content_type else "png"
            data = gen.content
        try:
            channel = await self.bot.fetch_channel(int(channel_id))
        except Exception as e:
            await interaction.followup.send(f"Failed to fetch channel: {e}")
            return
        file = discord.File(io.BytesIO(data), filename=f"slot_{slot}.{ext}")
        await channel.send(file=file)
        await interaction.followup.send(f"Sent slot {slot} to <#{channel_id}>")

    @app_commands.command(name="send_all_slots", description="Send all slots 2-25 to configured channel")
    @app_commands.describe(guild_id="Guild ID to use (copy from dashboard)")
    async def send_all_slots(self, interaction: discord.Interaction, guild_id: str):
        await interaction.response.defer(thinking=True)
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{BACKEND_URL}/api/guilds/{guild_id}/channel")
            if r.status_code != 200:
                await interaction.followup.send("Could not fetch guild configuration.")
                return
            channel_id = r.json().get("channel_id")
            if not channel_id:
                await interaction.followup.send("No channel configured.")
                return
            try:
                channel = await self.bot.fetch_channel(int(channel_id))
            except Exception as e:
                await interaction.followup.send(f"Failed to fetch channel: {e}")
                return
            for s in range(2, 26):
                gen = await client.get(f"{BACKEND_URL}/api/generate/{guild_id}/{s}", timeout=120)
                if gen.status_code != 200:
                    continue
                content_type = gen.headers.get("content-type","image/png")
                ext = "gif" if "gif" in content_type else "png"
                data = gen.content
                file = discord.File(io.BytesIO(data), filename=f"slot_{s}.{ext}")
                await channel.send(file=file)
        await interaction.followup.send("Sent all slots.")

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    await bot.tree.sync()
    print("Slash commands synced.")

async def main():
    async with bot:
        await bot.add_cog(SlotCog(bot))
        await bot.start(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
