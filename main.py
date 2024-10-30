import discord
from discord import app_commands
from flask import Flask, send_file
from threading import Thread
import asyncio
import aiohttp
from datetime import datetime, timedelta
from collections import deque
from waitress import serve

app = Flask(__name__)

class MyBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)
        self.cooldowns = {}
        self.queue = deque()
        self.is_processing = False

    async def setup_hook(self):
        await self.tree.sync()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
bot = MyBot(intents=intents)

ALLOWED_ROLE_ID = 1280340589971247245

async def is_valid_place_id(place_id: int) -> bool:
    url = f"https://www.roblox.com/games/{place_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return True
            elif response.status == 404:
                return False
            else:
                print(f"Unexpected status code {response.status} for place ID {place_id}")
                return False

@bot.tree.command(name="raid", description="Set the game ID")
@app_commands.describe(game_id="The game ID to set")
async def raid(interaction: discord.Interaction, game_id: int) -> None:
    user_id = interaction.user.id
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    member = guild.get_member(user_id)

    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except discord.NotFound:
            await interaction.response.send_message("Could not find the member in the server.", ephemeral=True)
            return

    if not any(role.id == ALLOWED_ROLE_ID for role in member.roles):
        await interaction.response.send_message("You do not have permission to use this bot.", ephemeral=True)
        return

    bypass_roles = [1278444615053082797, 1278442314699898982, 1278437864777977900]
    now = datetime.now()

    if not any(role.id in bypass_roles for role in member.roles):
        if user_id in bot.cooldowns:
            cooldown_expiry = bot.cooldowns[user_id]
            if now < cooldown_expiry:
                embed = discord.Embed(
                    title="serverside.emerald | #1 Raiding Tool",
                    description="**You're on a cooldown for 10 minutes!** 🚫",
                    color=65280
                )
                embed.set_author(name="serverside.emerald 2024.")
                embed.set_thumbnail(url="https://cdn.discordapp.com/icons/1278437475060154430/27c6ac62ff812f5faaa81ce013a77128.png?size=4096")

                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

    if not await is_valid_place_id(game_id):
        embed = discord.Embed(
            title="serverside.emerald | #1 Raiding Tool",
            description="**The provided Place ID is invalid. Please try again with a valid ID.** 🚫",
            color=65280
        )
        embed.set_author(name="serverside.emerald 2024.")
        embed.set_thumbnail(url="https://cdn.discordapp.com/icons/1278437475060154430/27c6ac62ff812f5faaa81ce013a77128.png?size=4096")

        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    bot.queue.append((interaction, game_id))

    position = len(bot.queue)
    embed = discord.Embed(
        title="serverside.emerald | #1 Raiding Tool",
        description=f"**You've been added to the queue in position #{position}.** Please wait until the current raid is complete. ⏳",
        color=15844367
    )
    embed.set_author(name="serverside.emerald 2024.")
    embed.set_thumbnail(url="https://cdn.discordapp.com/icons/1278437475060154430/27c6ac62ff812f5faaa81ce013a77128.png?size=4096")

    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()

    if position > 1:
        for i in range(1, position):
            embed.description = f"**You are in position #{i} in the queue.** Please wait until the current raid is complete. ⏳"
            await message.edit(embed=embed)
            await asyncio.sleep(1)

    if not bot.is_processing:
        await process_next_raid(message)

async def process_next_raid(message):
    if bot.is_processing or len(bot.queue) == 0:
        return

    bot.is_processing = True
    interaction, game_id = bot.queue.popleft()

    now = datetime.now()
    user_id = interaction.user.id

    bot.cooldowns[user_id] = now + timedelta(minutes=10)

    try:
        with open("game_id.txt", "w") as file:
            file.write(str(game_id))

        embed = discord.Embed(
            title="serverside.emerald | #1 Raiding Tool",
            description=f"**Game ID ({game_id}) is being raided!**\n**Thank you for purchasing serverside.emerald. 💸**",
            color=11559133
        )
        embed.set_author(name="serverside.emerald 2024.")
        embed.set_thumbnail(url="https://cdn.discordapp.com/icons/1278437475060154430/27c6ac62ff812f5faaa81ce013a77128.png?size=4096")

        await message.edit(embed=embed)

        print(f"Game ID set to {game_id}. It will be changed to 'stop' in 10 seconds.")

        await asyncio.sleep(10)

        with open("game_id.txt", "w") as file:
            file.write("stop")

        embed.description = "**Raiding Stopped! 🛑**\n**Thank you for purchasing serverside.emerald. 💸**"
        await message.edit(embed=embed)
        print("Game ID changed to 'stop'.")
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}")
        print(f"An error occurred: {str(e)}")
    finally:
        bot.is_processing = False
        if len(bot.queue) > 0:
            await process_next_raid(message)

@app.route('/', methods=['GET'])
def show_game_id():
    try:
        return send_file('game_id.txt')
    except Exception as e:
        return str(e), 500

async def run_flask_async():
    async with serve(app, host='0.0.0.0', port=5000):
        await asyncio.sleep(float('inf'))

Thread(target=lambda: asyncio.run(run_flask_async())).start()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

bot.run('MTI3ODQ0MTI5Mjg0MTYxOTYwOA.GBWy3A.jPL1YWgX1em6u-qyKygo1lyM9rTMcZcjeEjvN0')
