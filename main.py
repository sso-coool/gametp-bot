import discord
from discord import app_commands
from flask import Flask, send_file
from threading import Thread
import asyncio
import aiohttp
from datetime import datetime, timedelta
from collections import deque
from waitress import serve

# Initialize Flask app
app = Flask(__name__)

class RaidBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)
        self.user_cooldowns = {}
        self.raid_queue = deque()
        self.is_raid_in_progress = False

    async def setup_hook(self):
        # Sync slash commands to the bot
        await self.tree.sync()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
bot = RaidBot(intents=intents)

# Define the role ID allowed to trigger raids
ALLOWED_ROLE_ID = 1280340589971247245

async def is_valid_game_id(game_id: int) -> bool:
    """Check if the provided game ID is valid on Roblox."""
    url = f"https://www.roblox.com/games/{game_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return True
            elif response.status == 404:
                return False
            else:
                print(f"Error: Received unexpected status code {response.status} for game ID {game_id}")
                return False

@bot.tree.command(name="raid", description="Initiate a raid on a game by setting its game ID.")
@app_commands.describe(game_id="The ID of the game to target for the raid.")
async def raid(interaction: discord.Interaction, game_id: int) -> None:
    """Handles the 'raid' command to set the game ID."""
    user_id = interaction.user.id
    guild = interaction.guild

    # Check if command is used in a server
    if guild is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    member = guild.get_member(user_id)
    if member is None:
        # Fetch member if not found in cache
        try:
            member = await guild.fetch_member(user_id)
        except discord.NotFound:
            await interaction.response.send_message("Could not find you in this server.", ephemeral=True)
            return

    # Check if user has the required role
    if not any(role.id == ALLOWED_ROLE_ID for role in member.roles):
        await interaction.response.send_message("You do not have permission to use this bot.", ephemeral=True)
        return

    # List of roles that bypass the cooldown
    bypass_roles = [1278444615053082797, 1278442314699898982, 1278437864777977900]
    now = datetime.now()

    # Apply cooldowns unless user has a bypass role
    if not any(role.id in bypass_roles for role in member.roles):
        if user_id in bot.user_cooldowns:
            cooldown_expiry = bot.user_cooldowns[user_id]
            if now < cooldown_expiry:
                embed = discord.Embed(
                    title="Raid Tool | Cooldown Active",
                    description="**You're on cooldown for 10 minutes!** 🚫",
                    color=65280
                )
                embed.set_author(name="RaidBot 2024.")
                embed.set_thumbnail(url="https://cdn.discordapp.com/icons/1278437475060154430/27c6ac62ff812f5faaa81ce013a77128.png?size=4096")

                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

    # Check if the provided game ID is valid
    if not await is_valid_game_id(game_id):
        embed = discord.Embed(
            title="Raid Tool | Invalid Game ID",
            description="**The provided game ID is invalid. Please try again with a valid ID.** 🚫",
            color=65280
        )
        embed.set_author(name="RaidBot 2024.")
        embed.set_thumbnail(url="https://cdn.discordapp.com/icons/1278437475060154430/27c6ac62ff812f5faaa81ce013a77128.png?size=4096")

        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Add the raid to the queue
    bot.raid_queue.append((interaction, game_id))

    # Inform the user of their queue position
    position = len(bot.raid_queue)
    embed = discord.Embed(
        title="Raid Tool | Queued",
        description=f"**You've been added to the queue at position #{position}.** Please wait for the current raid to complete. ⏳",
        color=15844367
    )
    embed.set_author(name="RaidBot 2024.")
    embed.set_thumbnail(url="https://cdn.discordapp.com/icons/1278437475060154430/27c6ac62ff812f5faaa81ce013a77128.png?size=4096")

    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()

    # Update position in the queue
    if position > 1:
        for i in range(1, position):
            embed.description = f"**You are in position #{i} in the queue.** Please wait for the current raid to finish. ⏳"
            await message.edit(embed=embed)
            await asyncio.sleep(1)

    # If no raid is in progress, start the next raid
    if not bot.is_raid_in_progress:
        await start_next_raid(message)

async def start_next_raid(message):
    """Process the next raid in the queue."""
    if bot.is_raid_in_progress or len(bot.raid_queue) == 0:
        return

    bot.is_raid_in_progress = True
    interaction, game_id = bot.raid_queue.popleft()

    # Set the cooldown for the user
    now = datetime.now()
    user_id = interaction.user.id
    bot.user_cooldowns[user_id] = now + timedelta(minutes=10)

    try:
        # Save the game ID to a file
        with open("game_id.txt", "w") as file:
            file.write(str(game_id))

        embed = discord.Embed(
            title="Raid Tool | Raid In Progress",
            description=f"**Game ID ({game_id}) is being raided!**\n**Thank you for using RaidBot. 💸**",
            color=11559133
        )
        embed.set_author(name="RaidBot 2024.")
        embed.set_thumbnail(url="https://cdn.discordapp.com/icons/1278437475060154430/27c6ac62ff812f5faaa81ce013a77128.png?size=4096")

        await message.edit(embed=embed)

        # Simulate the raid process for 10 seconds
        await asyncio.sleep(10)

        # Stop the raid
        with open("game_id.txt", "w") as file:
            file.write("stop")

        embed.description = "**Raid Stopped! 🛑**\n**Thank you for using RaidBot. 💸**"
        await message.edit(embed=embed)
    except Exception as e:
        # Handle any errors during the raid
        await interaction.followup.send(f"An error occurred: {str(e)}")
        print(f"Error: {str(e)}")
    finally:
        bot.is_raid_in_progress = False

        # Process the next raid if available
        if len(bot.raid_queue) > 0:
            await start_next_raid(message)

# Flask web server route to view current game ID
@app.route('/', methods=['GET'])
def show_game_id():
    try:
        return send_file('game_id.txt')
    except Exception as e:
        return f"Error: {str(e)}", 500

# Run Flask in a separate thread
async def run_flask_server():
    """Run Flask server asynchronously."""
    async with serve(app, host='0.0.0.0', port=5000):
        await asyncio.sleep(float('inf'))

Thread(target=lambda: asyncio.run(run_flask_server())).start()

# Event handler when bot is ready
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# Run the bot with the token
bot.run('YOUR_BOT_TOKEN')
