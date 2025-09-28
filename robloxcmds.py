import discord
from discord.ext import commands, tasks
import requests
import json
import random
import asyncio
from datetime import datetime, timedelta
import pytz

class RobloxCMDS(commands.Cog):
    """A cog for executing commands in an ER:LC private server via API, handling hints, messages, and vehicle scans."""

    def __init__(self, bot):
        self.bot = bot
        # ER:LC API configuration
        self.api_url = "https://api.policeroleplay.community/v1/server/command"
        self.command_logs_url = "https://api.policeroleplay.community/v1/server/commandlogs"
        self.vehicles_api_url = "https://api.policeroleplay.community/v1/server/vehicles"
        self.api_key = "KgJHIfYWkZrddourWXvA-KKbhSbtwmiuDuXeGvhwySmLDgmhuuAatwRpYIJhi"
        self.headers = {
            "server-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "*/*"
        }
        # Hints configuration
        self.hints_list = [
            "Please use our liveries and our uniform for the best roleplay!",
            "Join our communications server now! Code: 3-H-P-5-s-t-g-9-m-9 (no dashes)",
            "If you need help or if you saw someone breaks server rules, please call !mod"
        ]
        self.hints_running = False
        self.hints_channel = None
        # Messages configuration
        self.messages_list = [
            "Want to become a staff member or to join a Whitelisted department? Join our communications server now! Code: 3-H-P-5-s-t-g-9-m-9 (no dashes)",
            "Welcome to Melbourne Roleplay! Join our communications server now! Code: 3-H-P-5-s-t-g-9-m-9 (no dashes)"
        ]
        self.messages_running = False
        self.messages_channel = None
        # Vehicle scan configuration
        self.vscan_running = False
        self.vscan_channel = None
        self.target_textures = ["undercover", "ghost", "WL", "SWAT"]
        self.vehicle_alert_channel_id = 1421801258188279881
        # Role ID for permission checks
        self.required_role_id = 1385160436046893168
        # Log channel ID
        self.log_channel_id = 1384468121842090035

    async def has_required_role(self, ctx, command_name):
        """Check if the user has the required role."""
        role = discord.utils.get(ctx.author.roles, id=self.required_role_id)
        if not role:
            embed = discord.Embed(
                title="UNAUTHORIZED",
                description=f"You are not allowed to run this command `{command_name}`.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            # Log unauthorized attempt
            log_channel = self.bot.get_channel(self.log_channel_id)
            if log_channel:
                log_embed = discord.Embed(
                    title="Unauthorized Command Attempt",
                    description=f"User {ctx.author.mention} tried to run `{command_name}` without permission.",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                await log_channel.send(embed=log_embed)
            return False
        return True

    async def log_command(self, command_name, user, details=None):
        """Log command usage or hint/message/vehicle scan to the specified channel."""
        log_channel = self.bot.get_channel(self.log_channel_id)
        if not log_channel:
            return

        embed = discord.Embed(
            title=f"Command Used: {command_name}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=user.mention, inline=True)
        if details:
            embed.add_field(name="Details", value=details, inline=False)
        await log_channel.send(embed=embed)

    async def execute_ingame_command(self, command):
        """Execute an in-game command via the ER:LC API."""
        payload = {"command": command}
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                data=json.dumps(payload),
                timeout=10
            )
            return response.status_code in (200, 201)
        except requests.exceptions.RequestException:
            return False

    @commands.command(name="execute")
    async def execute_command(self, ctx, *, command: str):
        if not await self.has_required_role(ctx, "execute"):
            return

        await self.log_command("execute", ctx.author, f"Command: `{command}`")

        try:
            success = await self.execute_ingame_command(command)
            if success:
                await ctx.send(f"Command `{command}` sent successfully!")
            else:
                await ctx.send(f"Failed to execute command `{command}`. Check API status or command validity.")
        except requests.exceptions.RequestException as e:
            await ctx.send(f"Error contacting the ER:LC API: {str(e)}")

    @commands.command(name="startscan")
    async def start_scan(self, ctx):
        if not await self.has_required_role(ctx, "startscan"):
            return

        if self.vscan_running:
            await ctx.send("Vehicle scan is already running!")
            return

        await self.log_command("startscan", ctx.author)
        self.vscan_running = True
        self.vscan_channel = ctx.channel
        await ctx.send("Starting vehicle scan.. Please wait…")
        await asyncio.sleep(3)

        embed = discord.Embed(
            title="Scan Started",
            description="Vehicle scan has been started successfully, use `.stopscan` to stop it.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        self.scan_vehicles.start()

    @commands.command(name="stopscan")
    async def stop_scan(self, ctx):
        if not await self.has_required_role(ctx, "stopscan"):
            return

        if not self.vscan_running:
            await ctx.send("No scans are currently running!")
            return

        await self.log_command("stopscan", ctx.author)
        await ctx.send("Stopping vehicle scan.. Please wait…")
        await asyncio.sleep(3)

        self.vscan_running = False
        self.scan_vehicles.stop()
        self.vscan_channel = None

        embed = discord.Embed(
            title="Scan Stopped",
            description="Vehicle scan has been successfully stopped, use `.startscan` to start it.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    @commands.command(name="starthints")
    async def start_hints(self, ctx):
        if not await self.has_required_role(ctx, "starthints"):
            return

        if self.hints_running:
            await ctx.send("Hints are already running!")
            return

        await self.log_command("starthints", ctx.author)
        self.hints_running = True
        self.hints_channel = ctx.channel
        await ctx.send("Starting hints... please wait a few seconds... ETA: 3 seconds")
        await asyncio.sleep(3)

        embed = discord.Embed(
            title="Hints Started!",
            description="The hints system has been successfully started and hints will be sent every 90 seconds.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        self.send_hints.start()

    @commands.command(name="stophints")
    async def stop_hints(self, ctx):
        if not await self.has_required_role(ctx, "stophints"):
            return

        if not self.hints_running:
            await ctx.send("Hints are not running!")
            return

        await self.log_command("stophints", ctx.author)
        await ctx.send("Stopping hints... please wait a few seconds... ETA: 3 seconds")
        await asyncio.sleep(3)

        self.hints_running = False
        self.send_hints.stop()
        self.hints_channel = None

        embed = discord.Embed(
            title="Hints Stopped!",
            description="Hints system has been successfully stopped.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    @commands.command(name="startmessages")
    async def start_messages(self, ctx):
        if not await self.has_required_role(ctx, "startmessages"):
            return

        if self.messages_running:
            await ctx.send("Messages are already running!")
            return

        await self.log_command("startmessages", ctx.author)
        self.messages_running = True
        self.messages_channel = ctx.channel
        await ctx.send("Starting messages... please wait a few seconds... ETA: 3 seconds")
        await asyncio.sleep(3)

        embed = discord.Embed(
            title="Messages Started!",
            description="The messages system has been successfully started and messages will be sent every 180 seconds.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        self.send_messages.start()

    @commands.command(name="stopmessages")
    async def stop_messages(self, ctx):
        if not await self.has_required_role(ctx, "stopmessages"):
            return

        if not self.messages_running:
            await ctx.send("Messages are not running!")
            return

        await self.log_command("stopmessages", ctx.author)
        await ctx.send("Stopping messages... please wait a few seconds... ETA: 3 seconds")
        await asyncio.sleep(3)

        self.messages_running = False
        self.send_messages.stop()
        self.messages_channel = None

        embed = discord.Embed(
            title="Messages Stopped!",
            description="Messages system has been successfully stopped.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    @tasks.loop(seconds=90)
    async def send_hints(self):
        """Send random hints in-game."""
        if self.hints_running and self.hints_channel:
            random_hint = random.choice(self.hints_list)
            hint_command = f":h {random_hint}"
            try:
                success = await self.execute_ingame_command(hint_command)
                log_channel = self.bot.get_channel(self.log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="Hint Sent",
                        description=f"Sent hint to ER:LC server: `{hint_command}`",
                        color=discord.Color.blue(),
                        timestamp=datetime.utcnow()
                    )
                    await log_channel.send(embed=embed)
                if not success:
                    if log_channel:
                        error_embed = discord.Embed(
                            title="Hint Failed",
                            description=f"Failed to send hint `{hint_command}` to ER:LC server.",
                            color=discord.Color.red(),
                            timestamp=datetime.utcnow()
                        )
                        await log_channel.send(embed=error_embed)
            except requests.exceptions.RequestException as e:
                log_channel = self.bot.get_channel(self.log_channel_id)
                if log_channel:
                    error_embed = discord.Embed(
                        title="Hint Failed",
                        description=f"Error sending hint `{hint_command}` to ER:LC API: {str(e)}",
                        color=discord.Color.red(),
                        timestamp=datetime.utcnow()
                    )
                    await log_channel.send(embed=error_embed)

    @tasks.loop(seconds=180)
    async def send_messages(self):
        """Send random messages in-game."""
        if self.messages_running and self.messages_channel:
            random_message = random.choice(self.messages_list)
            message_command = f":m {random_message}"
            try:
                success = await self.execute_ingame_command(message_command)
                log_channel = self.bot.get_channel(self.log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="Message Sent",
                        description=f"Sent message to ER:LC server: `{message_command}`",
                        color=discord.Color.blue(),
                        timestamp=datetime.utcnow()
                    )
                    await log_channel.send(embed=embed)
                if not success:
                    if log_channel:
                        error_embed = discord.Embed(
                            title="Message Failed",
                            description=f"Failed to send message `{message_command}` to ER:LC server.",
                            color=discord.Color.red(),
                            timestamp=datetime.utcnow()
                        )
                        await log_channel.send(embed=error_embed)
            except requests.exceptions.RequestException as e:
                log_channel = self.bot.get_channel(self.log_channel_id)
                if log_channel:
                    error_embed = discord.Embed(
                        title="Message Failed",
                        description=f"Error sending message `{message_command}` to ER:LC API: {str(e)}",
                        color=discord.Color.red(),
                        timestamp=datetime.utcnow()
                    )
                    await log_channel.send(embed=error_embed)

    @tasks.loop(seconds=60)
    async def scan_vehicles(self):
        """Scan vehicles for specific liveries."""
        if self.vscan_running and self.vscan_channel:
            try:
                response = requests.get(
                    self.vehicles_api_url,
                    headers=self.headers,
                    timeout=10
                )
                log_channel = self.bot.get_channel(self.log_channel_id)
                alert_channel = self.bot.get_channel(self.vehicle_alert_channel_id)

                if not alert_channel and log_channel:
                    log_embed = discord.Embed(
                        title="Vehicle Scan Error",
                        description="Cannot access alert channel. Check bot permissions.",
                        color=discord.Color.red(),
                        timestamp=datetime.utcnow()
                    )
                    await log_channel.send(embed=log_embed)

                if response.status_code == 200:
                    try:
                        data = response.json()
                        if isinstance(data, dict):
                            data = data.get("vehicles") or data.get("data") or data.get("result") or data
                            if not isinstance(data, list):
                                data = []

                        textures_found = []
                        for idx, vehicle in enumerate(data):
                            texture = vehicle.get("Texture") or vehicle.get("texture") or vehicle.get("livery")
                            cleaned_texture = str(texture).strip().lower() if texture else "None"
                            textures_found.append(f"Vehicle {idx}: {texture} (Cleaned: {cleaned_texture})")
                        if log_channel:
                            log_embed = discord.Embed(
                                title="Vehicle Scan Textures",
                                description=f"Found textures:\n{', '.join(textures_found) if textures_found else 'None'}",
                                color=discord.Color.blue(),
                                timestamp=datetime.utcnow()
                            )
                            await log_channel.send(embed=log_embed)

                        matching_vehicles = []
                        for vehicle in data:
                            texture = vehicle.get("Texture") or vehicle.get("texture") or vehicle.get("livery")
                            if texture:
                                texture_clean = str(texture).strip().lower()
                                if any(target.lower() == texture_clean for target in self.target_textures):
                                    car_type = vehicle.get("Name", "Unknown")
                                    username = vehicle.get("Owner", "Unknown")
                                    matching_vehicles.append({
                                        "username": username,
                                        "car_type": car_type,
                                        "texture": texture
                                    })

                        if matching_vehicles and alert_channel:
                            try:
                                await alert_channel.purge(check=lambda m: not m.pinned)
                                description = "\n".join(
                                    f"Username: {v['username']} | Car Type: {v['car_type']} | Livery: {v['texture']}"
                                    for v in matching_vehicles
                                )
                                embed = discord.Embed(
                                    title="No-Livery Cars",
                                    description=description,
                                    color=discord.Color.red(),
                                    timestamp=datetime.utcnow()
                                )
                                await alert_channel.send(embed=embed)
                            except discord.errors.Forbidden:
                                if log_channel:
                                    log_embed = discord.Embed(
                                        title="Vehicle Scan Error",
                                        description="Failed to purge or send to alert channel. Missing 'Manage Messages' or 'Send Messages' permissions.",
                                        color=discord.Color.red(),
                                        timestamp=datetime.utcnow()
                                    )
                                    await log_channel.send(embed=log_embed)
                        elif not matching_vehicles and log_channel:
                            log_embed = discord.Embed(
                                title="Vehicle Scan",
                                description="No vehicles with target textures (SWAT, Undercover, Ghost, WL) found.",
                                color=discord.Color.blue(),
                                timestamp=datetime.utcnow()
                            )
                            await log_channel.send(embed=log_embed)

                        if matching_vehicles and log_channel:
                            log_description = "\n".join(
                                f"Username: {v['username']} | Car Type: {v['car_type']} | Livery: {v['texture']}"
                                for v in matching_vehicles
                            )
                            log_embed = discord.Embed(
                                title="Vehicle Scan Alert",
                                description=f"Detected {len(matching_vehicles)} vehicles with target textures:\n{log_description}",
                                color=discord.Color.blue(),
                                timestamp=datetime.utcnow()
                            )
                            await log_channel.send(embed=log_embed)

                    except json.JSONDecodeError:
                        error_embed = discord.Embed(
                            title="Vehicle Scan Failed",
                            description="Failed to parse vehicle data from ER:LC API.",
                            color=discord.Color.red(),
                            timestamp=datetime.utcnow()
                        )
                        await self.vscan_channel.send(embed=error_embed)
                        if log_channel:
                            await log_channel.send(embed=error_embed)
                else:
                    error_embed = discord.Embed(
                        title="Vehicle Scan Failed",
                        description=f"Failed to fetch vehicle data from ER:LC server.\nError: {response.status_code} - {response.text}",
                        color=discord.Color.red(),
                        timestamp=datetime.utcnow()
                    )
                    await self.vscan_channel.send(embed=error_embed)
                    if log_channel:
                        await log_channel.send(embed=error_embed)
            except requests.exceptions.RequestException as e:
                error_embed = discord.Embed(
                    title="Vehicle Scan Failed",
                    description=f"Error contacting ER:LC vehicles API: {str(e)}",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                await self.vscan_channel.send(embed=error_embed)
                if log_channel:
                    await log_channel.send(embed=error_embed)

    @send_hints.before_loop
    async def before_send_hints(self):
        await self.bot.wait_until_ready()

    @send_messages.before_loop
    async def before_send_messages(self):
        await self.bot.wait_until_ready()

    @scan_vehicles.before_loop
    async def before_scan_vehicles(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{self.__class__.__name__} cog is loaded.")

async def setup(bot):
    await bot.add_cog(RobloxCMDS(bot))
