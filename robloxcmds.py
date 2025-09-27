import discord
from discord.ext import commands, tasks
import requests
import json
import random
import asyncio
from datetime import datetime, timedelta
import pytz

class RobloxCMDS(commands.Cog):
    """A cog for executing commands in an ER:LC private server via API, handling hints, messages, vehicle scans, and banned command detection."""

    def __init__(self, bot):
        self.bot = bot
        # ER:LC API configuration
        self.api_url = "https://api.policeroleplay.community/v1/server/command"
        self.command_logs_url = "https://api.policeroleplay.community/v1/server/commandlogs"
        self.vehicles_api_url = "https://api.policeroleplay.community/v1/server/vehicles"
        self.api_key = "NO_API"
        self.headers = {
            "server-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "*/*"
        }
        # Banned commands and trusted players
        self.banned_commands = [":down", ":time", ":weather"]
        self.banned_keywords = ["time", "weather", "down"]
        self.trusted_players = ["fartsaremelly2002", "Vavax989"]  # Add trusted usernames here
        self.banned_command_channel_id = 1412105304216305807
        self.bcscan_running = False
        self.reported_commands = {}  # Track reported commands with timestamps
        self.report_cooldown = timedelta(minutes=5)  # Cooldown period for duplicate alerts
        # Hints configuration
        self.hints_list = [
            "Please use our liveries and our uniform for the best roleplay!",
            "Join our communications server now! Code: t-R-f-a-H-k-Q-D-q-S (no dashes)",
            "If you need help or if you saw someone breaks server rules, please call !mod"
        ]
        self.hints_running = False
        self.hints_channel = None
        # Messages configuration
        self.messages_list = [
            "Want to become a staff member or to join a Whitelisted department? Join our communications server now! Code: c-J-F-J-8-2-q-U-q-w (no dashes)",
            "Welcome to Miami Beach Roleplay! Join our communications server now! Code: t-R-f-a-H-k-Q-D-q-S (no dashes)"
        ]
        self.messages_running = False
        self.messages_channel = None
        # Vehicle scan configuration
        self.vscan_running = False
        self.vscan_channel = None
        self.target_textures = ["undercover", "ghost", "WL", "SWAT"]
        self.vehicle_alert_channel_id = 1410300631926964365
        # Role ID for permission checks
        self.required_role_id = 1409641647859568660
        # Log channel ID
        self.log_channel_id = 1412105551789297927
        # Off-duty commands detector configuration
        self.off_duty_alert_channel_id = 1412105238428651721
        self.off_duty_required_role_id = 1410049625905172660  # Replace with the actual role ID required to be "on-duty" for using commands
        self.off_duty_bypass_role_id = 1410822274109542440  # Replace with the actual role ID that allows bypassing the off-duty check
        self.user_mapping = {  # Map Roblox usernames to Discord user IDs (integers)
            "Vavax989": 1038522974988411000,
            "Lel_664": 1040198042000838687,
            "Nick_Playzz": 1296868173550845963,
            "mun_chers": 1241030555219398670,
            "PrigerGlobalalt": 1241760982217523425,
            "Jonathan0157_021": 1196503006175313932,
            "PLEX_0209": 1291749227185045575,
            "Mohammedmm152q4": 1325108035001258086,
            "Supercrystal_01": 1250762012464644186,
            "coquiian": 1174398346237059093
              # Replace with actual mappings
            # Add more: "roblox_username": discord_user_id,
        }
        self.reported_off_duty = {}  # Track reported off-duty commands with timestamps

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

        if self.bcscan_running or self.vscan_running:
            await ctx.send("One or both scans are already running!")
            return

        await self.log_command("startscan", ctx.author)
        self.bcscan_running = True
        self.vscan_running = True
        self.vscan_channel = ctx.channel
        await ctx.send("Starting vehicle, banned and off-duty commands scan.. Please wait…")
        await asyncio.sleep(3)

        embed = discord.Embed(
            title="Scan Started",
            description="Functionalities as vehicle scan, banned and off-duty commands detector has been started successfully, use `.stopscan` to stop it.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        self.check_banned_commands.start()
        self.scan_vehicles.start()

    @commands.command(name="stopscan")
    async def stop_scan(self, ctx):
        if not await self.has_required_role(ctx, "stopscan"):
            return

        if not self.bcscan_running and not self.vscan_running:
            await ctx.send("No scans are currently running!")
            return

        await self.log_command("stopscan", ctx.author)
        await ctx.send("Stopping vehicle, banned and off-duty commands scan.. Please wait…")
        await asyncio.sleep(3)

        self.bcscan_running = False
        self.vscan_running = False
        self.check_banned_commands.stop()
        self.scan_vehicles.stop()
        self.vscan_channel = None
        self.reported_commands.clear()  # Clear reported commands on stop
        self.reported_off_duty.clear()  # Clear reported off-duty on stop

        embed = discord.Embed(
            title="Scan Stopped",
            description="Functionalities as vehicle scan, banned and off-duty commands detector has been successfully stopped, use `.startscan` to start it.",
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

    @tasks.loop(seconds=30)
    async def check_banned_commands(self):
        """Check for banned commands and off-duty command usage, log raw JSON."""
        if not self.bcscan_running:
            return

        try:
            response = requests.get(
                self.command_logs_url,
                headers=self.headers,
                timeout=10
            )
            log_channel = self.bot.get_channel(self.log_channel_id)
            banned_channel = self.bot.get_channel(self.banned_command_channel_id)
            off_duty_channel = self.bot.get_channel(self.off_duty_alert_channel_id)

            if not banned_channel or not log_channel or not off_duty_channel:
                if log_channel:
                    error_embed = discord.Embed(
                        title="Command Check Error",
                        description="Cannot access required channels. Check bot permissions.",
                        color=discord.Color.red(),
                        timestamp=datetime.utcnow()
                    )
                    await log_channel.send(embed=error_embed)
                return

            guild = log_channel.guild  # Get the guild from the log channel

            if response.status_code == 200:
                try:
                    data = response.json()
                    # Debug: Log the structure of the response
                    debug_description = f"Response type: {type(data).__name__}\n"
                    if isinstance(data, dict):
                        debug_description += f"Keys: {list(data.keys())}\n"
                        if "commands" in data:
                            debug_description += f"commands type: {type(data['commands']).__name__}\n"
                        if "data" in data:
                            debug_description += f"data type: {type(data['data']).__name__}\n"
                        if "result" in data:
                            debug_description += f"result type: {type(data['result']).__name__}\n"
                    elif isinstance(data, list):
                        debug_description += f"List length: {len(data)}\n"
                        if data:
                            debug_description += f"First item keys: {list(data[0].keys()) if isinstance(data[0], dict) else 'Not a dict'}\n"
                    debug_embed = discord.Embed(
                        title="API Response Debug",
                        description=debug_description,
                        color=discord.Color.blue(),
                        timestamp=datetime.utcnow()
                    )
                    await log_channel.send(embed=debug_embed)

                    # Normalize data to a list
                    if not isinstance(data, list):
                        data = data.get("commands") or data.get("data") or data.get("result") or []
                        if not isinstance(data, list):
                            data = []

                    # Log raw JSON response
                    raw_json = json.dumps(data, indent=2)
                    chunks = [raw_json[i:i+1900] for i in range(0, len(raw_json), 1900)]
                    for i, chunk in enumerate(chunks, 1):
                        log_embed = discord.Embed(
                            title=f"Command Logs Raw JSON (Part {i})",
                            description=f"```json\n{chunk}\n```",
                            color=discord.Color.blue(),
                            timestamp=datetime.utcnow()
                        )
                        await log_channel.send(embed=log_embed)

                    # Log all commands
                    if data:
                        log_description = "\n".join(
                            f"Username: {log.get('Player', 'Unknown').split(':')[0]} | Command: {log.get('Command', 'None')} | Timestamp: {log.get('Timestamp', 'None')}"
                            for log in data
                        )
                        log_embed = discord.Embed(
                            title="Command Logs",
                            description=log_description or "No commands found.",
                            color=discord.Color.blue(),
                            timestamp=datetime.utcnow()
                        )
                        await log_channel.send(embed=log_embed)
                    else:
                        log_embed = discord.Embed(
                            title="Command Logs",
                            description="No commands found in the API response.",
                            color=discord.Color.blue(),
                            timestamp=datetime.utcnow()
                        )
                        await log_channel.send(embed=log_embed)

                    # Check for banned commands or keywords and off-duty usage
                    current_time = datetime.utcnow()
                    for log in data:
                        command = log.get("Command", "").strip().lower()
                        player = log.get("Player", "Unknown")
                        # Extract username from "username:id" format
                        username = player.split(":")[0] if ":" in player else player
                        timestamp = log.get("Timestamp", current_time)

                        # Parse timestamp
                        if isinstance(timestamp, (int, float)):
                            # Assume Unix timestamp in seconds
                            command_time = datetime.fromtimestamp(timestamp, tz=pytz.UTC)
                            timestamp_str = command_time.isoformat()
                        elif isinstance(timestamp, str):
                            try:
                                command_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                                timestamp_str = timestamp
                            except ValueError:
                                command_time = current_time
                                timestamp_str = current_time.isoformat()
                                error_embed = discord.Embed(
                                    title="Timestamp Parse Error",
                                    description=f"Invalid timestamp format for command by {username}: {timestamp}. Using current time.",
                                    color=discord.Color.yellow(),
                                    timestamp=current_time
                                )
                                await log_channel.send(embed=error_embed)
                        else:
                            command_time = current_time
                            timestamp_str = current_time.isoformat()
                            error_embed = discord.Embed(
                                title="Timestamp Type Error",
                                description=f"Unexpected timestamp type for command by {username}: {type(timestamp)}. Using current time.",
                                color=discord.Color.yellow(),
                                timestamp=current_time
                            )
                            await log_channel.send(embed=error_embed)

                        # Skip if user is trusted
                        if username in self.trusted_players:
                            log_embed = discord.Embed(
                                title="Trusted Player Command",
                                description=f"Skipping checks for trusted user {username} with command `{command}`.",
                                color=discord.Color.green(),
                                timestamp=command_time
                            )
                            await log_channel.send(embed=log_embed)
                            continue

                        # Create a unique identifier for the command instance
                        command_id = f"{username}:{command}:{timestamp_str}"

                        # Banned command check
                        # Check if command was recently reported
                        if command_id in self.reported_commands:
                            last_reported = self.reported_commands[command_id]
                            if current_time - last_reported < self.report_cooldown:
                                log_embed = discord.Embed(
                                    title="Duplicate Banned Command Skipped",
                                    description=f"Command `{command}` by {username} skipped due to recent report within {self.report_cooldown.seconds // 60} minutes.",
                                    color=discord.Color.yellow(),
                                    timestamp=command_time
                                )
                                await log_channel.send(embed=log_embed)
                            else:
                                continue  # Still process if cooldown passed, but since it's duplicate, perhaps continue

                        # Check for exact banned commands or keywords
                        is_banned = (
                            any(banned_cmd.lower() == command for banned_cmd in self.banned_commands) or
                            any(keyword.lower() in command for keyword in self.banned_keywords)
                        )

                        # Debug: Log command check result
                        log_embed = discord.Embed(
                            title="Banned Command Check",
                            description=f"Command: `{command}` | Username: {username} | Is Banned: {is_banned}",
                            color=discord.Color.blue(),
                            timestamp=command_time
                        )
                        await log_channel.send(embed=log_embed)

                        if is_banned:
                            self.reported_commands[command_id] = current_time  # Store timestamp of report
                            embed = discord.Embed(
                                title="Banned Command Alert",
                                description=f"**{username}** has used a banned command in the private server!",
                                color=discord.Color.red(),
                                timestamp=command_time
                            )
                            embed.add_field(name="Command", value=f"`{command}`", inline=True)
                            embed.add_field(name="When", value=f"<t:{int(command_time.timestamp())}:F>", inline=True)
                            embed.set_footer(text="AS:RP")

                            # Create buttons
                            view = discord.ui.View()

                            async def acknowledge_callback(interaction):
                                embed.title = f"Banned Command Alert (Acknowledged by {interaction.user.name})"
                                await interaction.message.edit(embed=embed)
                                await interaction.response.send_message("Acknowledged.", ephemeral=True)

                            acknowledge_button = discord.ui.Button(label="Acknowledgement", style=discord.ButtonStyle.green)
                            acknowledge_button.callback = acknowledge_callback
                            view.add_item(acknowledge_button)

                            async def revoke_callback(interaction):
                                await self.execute_ingame_command(f":unmod {username}")
                                await self.execute_ingame_command(f":unadmin {username}")
                                await self.execute_ingame_command(f":pm {username} You have been unmodded/unadminned due to a banned command.")
                                await interaction.response.send_message(
                                    f"Permissions revoked for {username}. PM sent: check logs dumass",
                                    ephemeral=True
                                )

                            revoke_button = discord.ui.Button(label="Revoke Perms", style=discord.ButtonStyle.red)
                            revoke_button.callback = revoke_callback
                            view.add_item(revoke_button)

                            # Send alert with buttons
                            try:
                                await banned_channel.send(content="@everyone", embed=embed, view=view)
                                log_embed = discord.Embed(
                                    title="Banned Command Alert Sent",
                                    description=f"Alert sent for {username} using `{command}`.",
                                    color=discord.Color.green(),
                                    timestamp=command_time
                                )
                                await log_channel.send(embed=log_embed)
                            except discord.errors.Forbidden:
                                error_embed = discord.Embed(
                                    title="Failed to Send Banned Alert",
                                    description="Bot lacks permission to send messages in the banned command channel.",
                                    color=discord.Color.red(),
                                    timestamp=current_time
                                )
                                await log_channel.send(embed=error_embed)

                            # Send in-game PM
                            pm_success = await self.execute_ingame_command(
                                f":pm {username} You have used a banned command, the SHR team has been notified"
                            )
                            if not pm_success and log_channel:
                                error_embed = discord.Embed(
                                    title="Banned Command PM Failed",
                                    description=f"Failed to send PM to {username} about banned command usage.",
                                    color=discord.Color.red(),
                                    timestamp=current_time
                                )
                                await log_channel.send(embed=error_embed)

                        # Off-duty command check (independent of banned check)
                        # Skip if no mapping for username
                        if username not in self.user_mapping:
                            log_embed = discord.Embed(
                                title="Off-Duty Check Skipped",
                                description=f"No Discord ID mapping found for username {username}.",
                                color=discord.Color.yellow(),
                                timestamp=command_time
                            )
                            await log_channel.send(embed=log_embed)
                            continue

                        discord_id = self.user_mapping[username]
                        member = guild.get_member(discord_id)
                        if not member:
                            log_embed = discord.Embed(
                                title="Off-Duty Check Failed",
                                description=f"Could not find Discord member for ID {discord_id} (username {username}).",
                                color=discord.Color.yellow(),
                                timestamp=command_time
                            )
                            await log_channel.send(embed=log_embed)
                            continue

                        # Check if has bypass role
                        has_bypass = discord.utils.get(member.roles, id=self.off_duty_bypass_role_id) is not None
                        if has_bypass:
                            log_embed = discord.Embed(
                                title="Off-Duty Check Bypassed",
                                description=f"User {username} ({member.mention}) has bypass role, skipping off-duty check.",
                                color=discord.Color.green(),
                                timestamp=command_time
                            )
                            await log_channel.send(embed=log_embed)
                            continue

                        # Check if has required on-duty role
                        has_required = discord.utils.get(member.roles, id=self.off_duty_required_role_id) is not None
                        is_off_duty = not has_required

                        # Debug: Log off-duty check result
                        log_embed = discord.Embed(
                            title="Off-Duty Command Check",
                            description=f"Command: `{command}` | Username: {username} | Is Off-Duty: {is_off_duty}",
                            color=discord.Color.blue(),
                            timestamp=command_time
                        )
                        await log_channel.send(embed=log_embed)

                        if is_off_duty:
                            # Check if recently reported
                            if command_id in self.reported_off_duty:
                                last_reported = self.reported_off_duty[command_id]
                                if current_time - last_reported < self.report_cooldown:
                                    log_embed = discord.Embed(
                                        title="Duplicate Off-Duty Command Skipped",
                                        description=f"Command `{command}` by {username} skipped due to recent report within {self.report_cooldown.seconds // 60} minutes.",
                                        color=discord.Color.yellow(),
                                        timestamp=command_time
                                    )
                                    await log_channel.send(embed=log_embed)
                                    continue

                            self.reported_off_duty[command_id] = current_time  # Store timestamp of report
                            embed = discord.Embed(
                                title="Off-Duty Command Alert",
                                description=f"**{username}** ({member.mention}) has used a command while off-duty in the private server!",
                                color=discord.Color.red(),
                                timestamp=command_time
                            )
                            embed.add_field(name="Command", value=f"`{command}`", inline=True)
                            embed.add_field(name="When", value=f"<t:{int(command_time.timestamp())}:F>", inline=True)
                            embed.set_footer(text="AS:RP")

                            # Create buttons (similar to banned)
                            view = discord.ui.View()

                            async def acknowledge_callback(interaction):
                                embed.title = f"Off-Duty Command Alert (Acknowledged by {interaction.user.name})"
                                await interaction.message.edit(embed=embed)
                                await interaction.response.send_message("Acknowledged.", ephemeral=True)

                            acknowledge_button = discord.ui.Button(label="Acknowledgement", style=discord.ButtonStyle.green)
                            acknowledge_button.callback = acknowledge_callback
                            view.add_item(acknowledge_button)

                            async def revoke_callback(interaction):
                                await self.execute_ingame_command(f":unmod {username}")
                                await self.execute_ingame_command(f":unadmin {username}")
                                pm_success = await self.execute_ingame_command(f":pm {username} You have been unmodded/unadminned due to off-duty command usage.")
                                await interaction.response.send_message(
                                    f"Permissions revoked for {username}. PM sent: {pm_success}",
                                    ephemeral=True
                                )

                            revoke_button = discord.ui.Button(label="Revoke Perms", style=discord.ButtonStyle.red)
                            revoke_button.callback = revoke_callback
                            view.add_item(revoke_button)

                            # Send alert with buttons
                            try:
                                await off_duty_channel.send(content="No Ping", embed=embed, view=view)
                                log_embed = discord.Embed(
                                    title="Off-Duty Command Alert Sent",
                                    description=f"Alert sent for {username} using `{command}` while off-duty.",
                                    color=discord.Color.green(),
                                    timestamp=command_time
                                )
                                await log_channel.send(embed=log_embed)
                            except discord.errors.Forbidden:
                                error_embed = discord.Embed(
                                    title="Failed to Send Off-Duty Alert",
                                    description="Bot lacks permission to send messages in the off-duty alert channel.",
                                    color=discord.Color.red(),
                                    timestamp=current_time
                                )
                                await log_channel.send(embed=error_embed)

                            # Send in-game PM
                            pm_success = await self.execute_ingame_command(
                                f":pm {username} You have used a command while off-duty, the SHR team has been notified"
                            )
                            if not pm_success and log_channel:
                                error_embed = discord.Embed(
                                    title="Off-Duty Command PM Failed",
                                    description=f"Failed to send PM to {username} about off-duty command usage.",
                                    color=discord.Color.red(),
                                    timestamp=current_time
                                )
                                await log_channel.send(embed=error_embed)

                except json.JSONDecodeError:
                    error_embed = discord.Embed(
                        title="Command Check Failed",
                        description="Failed to parse command logs from ER:LC API.",
                        color=discord.Color.red(),
                        timestamp=datetime.utcnow()
                    )
                    await log_channel.send(embed=error_embed)
            else:
                error_embed = discord.Embed(
                    title="Command Check Failed",
                    description=f"Failed to fetch command logs. Error: {response.status_code} - {response.text}",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                await log_channel.send(embed=error_embed)

        except requests.exceptions.RequestException as e:
            error_embed = discord.Embed(
                title="Command Check Failed",
                description=f"Error contacting ER:LC command logs API: {str(e)}",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            await log_channel.send(embed=error_embed)

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

    @check_banned_commands.before_loop
    async def before_check_banned_commands(self):
        await self.bot.wait_until_ready()

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
