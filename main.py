import discord
from discord import app_commands
from flask import Flask, send_file
from threading import Thread
import asyncio
import aiohttp
from datetime import datetime, timedelta
from collections import deque
from waitress import serve  # Import the waitress library

# Initialize Flask app
app = Flask(__name__)

# Subclass discord.Client to properly attach the command tree
class MyBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)
        self.cooldowns = {}
        self.queue = deque()  # Initialize a queue using deque
        self.is_processing = False  # To check if a command is currently being processed

    async def setup_hook(self):
        await self.tree.sync()

# Initialize the bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True  # Required for role checking
bot = MyBot(intents=intents)

# Role ID that is allowed to use the bot
ALLOWED_ROLE_ID = 1278446317328142478  # Replace this with the actual role ID

# Define a function to check if a place ID is valid using the Roblox website
async def is_valid_place_id(place_id: int) -> bool:
    url = f"https://www.roblox.com/games/{place_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                # If the page is accessible, consider it valid
                return True
            elif response.status == 404:
                # If a 404 error page is returned, consider it invalid
                return False
            else:
                # For other status codes, you might want to log or handle differently
                print(f"Unexpected status code {response.status} for place ID {place_id}")
                return False

# Define the slash command
@bot.tree.command(name="raid", description="Set the game ID")
@app_commands.describe(game_id="The game ID to set")
async def raid(interaction: discord.Interaction, game_id: int) -> None:
    """Sets the game ID and queues users if a command is already being processed."""

    user_id = interaction.user.id
    guild = interaction.guild  # Get the guild (server) from the interaction
    if guild is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    member = guild.get_member(user_id)  # Get the member object for the user

    if member is None:  # If member is not found, try to fetch it
        try:
            member = await guild.fetch_member(user_id)
        except discord.NotFound:
            await interaction.response.send_message("Could not find the member in the server.", ephemeral=True)
            return

    # Check if the user has the allowed role
    if not any(role.id == ALLOWED_ROLE_ID for role in member.roles):
        await interaction.response.send_message("You do not have permission to use this bot.", ephemeral=True)
        return

    # Role IDs that bypass cooldown
    bypass_roles = [1278444615053082797, 1278442314699898982, 1278437864777977900]  # Add the second role ID here
    now = datetime.now()

    # Check if the user has one of the bypass roles
    if any(role.id in bypass_roles for role in member.roles):
        # No cooldown for users with bypass roles
        pass
    else:
        # Check if the user is on cooldown
        if user_id in bot.cooldowns:
            cooldown_expiry = bot.cooldowns[user_id]
            if now < cooldown_expiry:
                # User is still on cooldown
                embed = discord.Embed(
                    title="Frigid | #1 Raiding Tool",
                    description="**You're on a cooldown for 10 minutes!** 🚫",
                    color=14508128
                )
                embed.set_author(name="Frigid 2024.")
                embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1278436853900640342/1278447609685606483/Screenshot_2024-08-28_at_21.14.16.png")

                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

    # Validate the game ID using the Roblox website
    if not await is_valid_place_id(game_id):
        # If the place ID is invalid, send an embed message
        embed = discord.Embed(
            title="Frigid | #1 Raiding Tool",
            description="**The provided Place ID is invalid. Please try again with a valid ID.** 🚫",
            color=14508128
        )
        embed.set_author(name="Frigid 2024.")
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1278436853900640342/1278447609685606483/Screenshot_2024-08-28_at_21.14.16.png")

        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Add the user to the queue
    bot.queue.append((interaction, game_id))

    # Send an initial embed message indicating the user's position in the queue
    position = len(bot.queue)
    embed = discord.Embed(
        title="Frigid | #1 Raiding Tool",
        description=f"**You've been added to the queue in position #{position}.** Please wait until the current raid is complete. ⏳",
        color=15844367
    )
    embed.set_author(name="Frigid 2024.")
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1278436853900640342/1278447609685606483/Screenshot_2024-08-28_at_21.14.16.png")

    # Use the interaction's followup to ensure the message object is correctly retrieved
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()

    # Update the message with the user's position if there are more in the queue
    if position > 1:
        for i in range(1, position):
            embed.description = f"**You are in position #{i} in the queue.** Please wait until the current raid is complete. ⏳"
            await message.edit(embed=embed)
            await asyncio.sleep(1)

    # If not processing, start the queue
    if not bot.is_processing:
        await process_next_raid(message)

async def process_next_raid(message):
    """Processes the next raid in the queue."""
    if bot.is_processing or len(bot.queue) == 0:
        return  # Exit if already processing or queue is empty

    bot.is_processing = True  # Set processing flag
    interaction, game_id = bot.queue.popleft()  # Get the next user in the queue

    now = datetime.now()
    user_id = interaction.user.id

    # Set cooldown for 10 minutes
    bot.cooldowns[user_id] = now + timedelta(minutes=10)

    try:
        # Write the game ID to the file
        with open("game_id.txt", "w") as file:
            file.write(str(game_id))

        # Edit the message to indicate the raid has started
        embed = discord.Embed(
            title="Frigid | #1 Raiding Tool",
            description=f"**Game ID ({game_id}) is being raided!**\n**Thank you for purchasing Frigid. 💸**",
            color=11559133
        )
        embed.set_author(name="Frigid 2024.")
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1278436853900640342/1278447609685606483/Screenshot_2024-08-28_at_21.14.16.png")

        await message.edit(embed=embed)

        print(f"Game ID set to {game_id}. It will be changed to 'stop' in 10 seconds.")

        # Wait for 10 seconds
        await asyncio.sleep(10)

        # Change the content to "stop"
        with open("game_id.txt", "w") as file:
            file.write("stop")

        # Edit the message to indicate that raiding has stopped
        embed.description = "**Raiding Stopped! 🛑**\n**Thank you for purchasing Frigid. 💸**"
        await message.edit(embed=embed)
        print("Game ID changed to 'stop'.")
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}")
        print(f"An error occurred: {str(e)}")
    finally:
        bot.is_processing = False  # Reset processing flag
        # Process the next raid after the current one is done
        if len(bot.queue) > 0:
            await process_next_raid(message)

@app.route('/', methods=['GET'])
def show_game_id():
    """Displays the content of game_id.txt."""
    try:
        return send_file('game_id.txt')
    except Exception as e:
        return str(e), 500

# Function to run Flask app asynchronously using waitress
async def run_flask_async():
    """Runs the Flask app asynchronously."""
    async with serve(app, host='0.0.0.0', port=5000):  # Use 'waitress' for async execution
        await asyncio.sleep(float('inf'))  # Keep the server running indefinitely

# Start the Flask server asynchronously in a separate thread
Thread(target=lambda: asyncio.run(run_flask_async())).start()

@bot.event
async def on_ready():
    """Event handler for when the bot is ready."""
    print(f"Logged in as {bot.user}")

# Run the bot with your token
bot.run('MTI3ODQ0MTI5Mjg0MTYxOTYwOA.GBWy3A.jPL1YWgX1em6u-qyKygo1lyM9rTMcZcjeEjvN0')
