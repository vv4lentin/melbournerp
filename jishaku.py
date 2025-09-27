import discord
import asyncio
import subprocess
import textwrap
import io
import traceback
import datetime
import inspect
import os
import sys
import json
import shutil
from discord.ext import commands
from pathlib import Path
from discord.ui import Button, View
import logging

# Configure logging with fallback to console
try:
    log_file = Path("bot.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    if not os.access(log_file.parent, os.W_OK):
        raise PermissionError("No write permission for log directory")
    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format="%(asctime)s:%(levelname)s:%(name)s: %(message)s"
    )
except (PermissionError, OSError) as e:
    print(f"Logging to file failed: {e}. Falling back to console.")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s:%(levelname)s:%(name)s: %(message)s",
        handlers=[logging.StreamHandler()]
    )
logger = logging.getLogger("Jishaku")

class PaginatorView(View):
    def __init__(self, paginator, author):
        super().__init__(timeout=60)
        self.paginator = paginator
        self.author = author
        self.message = None
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.paginator.current_page == 0
        self.next_button.disabled = self.paginator.current_page >= len(self.paginator.pages) - 1

    async def on_timeout(self):
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
                logger.debug("Paginator view timed out")
            except discord.HTTPException as e:
                logger.warning(f"Failed to update paginator view on timeout: {e}")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("Only the command author can use these buttons.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.blurple, emoji="⬅️")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            self.paginator.prev_page()
            self.update_buttons()
            embed = self.paginator.get_embed()
            await interaction.response.edit_message(embed=embed, view=self)
            logger.debug(f"{interaction.user} navigated to previous page")
        except discord.HTTPException as e:
            logger.error(f"Failed to update paginator (prev): {e}")
            await interaction.response.send_message("Failed to update page.", ephemeral=True)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple, emoji="➡️")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            self.paginator.next_page()
            self.update_buttons()
            embed = self.paginator.get_embed()
            await interaction.response.edit_message(embed=embed, view=self)
            logger.debug(f"{interaction.user} navigated to next page")
        except discord.HTTPException as e:
            logger.error(f"Failed to update paginator (next): {e}")
            await interaction.response.send_message("Failed to update page.", ephemeral=True)

class Paginator:
    def __init__(self, entries, title, per_page=10):
        self.entries = entries or ["No entries."]
        self.title = title[:256]  # Ensure title fits Discord's limit
        self.per_page = per_page
        self.pages = [self.entries[i:i + per_page] for i in range(0, len(self.entries), per_page)]
        self.current_page = 0

    def get_page(self):
        content = "\n".join(self.pages[self.current_page]) if self.pages else "No entries."
        return content[:4000]  # Ensure within Discord's description limit

    def get_embed(self):
        embed = discord.Embed(
            title=self.title,
            description=f"```py\n{self.get_page()}\n```",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")
        return embed

    def next_page(self):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1

class Jishaku(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.datetime.utcnow()
        self.owner_ids = set()
        self.config = self._load_config()
        self.error_channel_id = self.config.get("error_channel_id")
        self._owners_fetched = False
        self._load_owners()
        logger.info("Jishaku cog initialized")

    def _load_config(self):
        config_path = Path("config.json")
        default_config = {
            "owner_ids": [],
            "error_channel_id": None,
            "max_log_lines": 100,
            "backup_dir": "backups"
        }
        try:
            if not config_path.exists():
                with config_path.open("w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=2)
                logger.info("Created default config.json")
                return default_config
            with config_path.open("r", encoding="utf-8") as f:
                config = json.load(f)
                return {**default_config, **config}
        except (json.JSONDecodeError, OSError, PermissionError) as e:
            logger.error(f"Failed to load config.json: {e}. Using defaults.")
            return default_config

    def _save_config(self):
        config_path = Path("config.json")
        try:
            with config_path.open("w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            logger.debug("Saved config.json")
        except (OSError, PermissionError) as e:
            logger.error(f"Failed to save config.json: {e}")

    def _load_owners(self):
        try:
            owner_ids = self.config.get("owner_ids", [])
            self.owner_ids = {int(oid) for oid in owner_ids if isinstance(oid, (int, str)) and str(oid).isdigit()}
            logger.info(f"Loaded owner IDs from config: {self.owner_ids}")
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid owner_ids in config: {e}. Using empty set.")
            self.owner_ids = set()

    async def _fetch_owners(self):
        try:
            await self.bot.wait_until_ready()
            app_info = await self.bot.application_info()
            if app_info.team:
                self.owner_ids = {member.id for member in app_info.team.members}
            else:
                self.owner_ids = {app_info.owner.id}
            self.config["owner_ids"] = list(self.owner_ids)
            self._save_config()
            logger.info(f"Fetched owner IDs: {self.owner_ids}")
        except discord.HTTPException as e:
            logger.error(f"Failed to fetch owners: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        if not self._owners_fetched and not self.owner_ids:
            self._owners_fetched = True
            await self._fetch_owners()
            logger.info("Owner fetching completed in on_ready")

    async def cog_load(self):
        logger.info("Jishaku cog async initialization completed")

    async def cog_check(self, ctx):
        if not self.owner_ids:
            logger.warning("No owner IDs defined")
            await ctx.send("No bot owners configured.")
            return False
        if ctx.author.id not in self.owner_ids:
            logger.warning(f"{ctx.author} is not an owner")
            await ctx.send("This command is restricted to bot owners.")
            return False
        return True

    async def _send_paginated(self, ctx, entries, title, per_page=10):
        try:
            if not entries:
                await ctx.send(f"No {title.lower()} found.")
                return
            paginator = Paginator(entries, title, per_page)
            view = PaginatorView(paginator, ctx.author)
            view.message = await ctx.send(embed=paginator.get_embed(), view=view)
            logger.info(f"{ctx.author} received paginated output for {title}")
        except discord.Forbidden as e:
            logger.error(f"Failed to send paginated embed: {e}")
            await ctx.send("Failed to send embed. Ensure the bot has permissions to send messages and embed links.")
        except discord.HTTPException as e:
            logger.error(f"Failed to send paginated embed: {e}")
            await ctx.send(f"Failed to send embed: {str(e)}")

    async def _send_file(self, ctx, content, filename, max_length=2000):
        content = content[:1000000]  # Prevent massive files
        if len(content) <= max_length:
            try:
                await ctx.send(f"```{filename.split('.')[-1]}\n{content}\n```")
                logger.info(f"{ctx.author} received inline output: {filename}")
            except discord.Forbidden as e:
                logger.error(f"Failed to send inline message: {e}")
                await ctx.send("Failed to send message. Ensure the bot has permissions to send messages.")
            return
        file_path = Path(f"temp_{filename}")
        try:
            with file_path.open("w", encoding="utf-8") as f:
                f.write(content)
            if file_path.stat().st_size > 25 * 1024 * 1024:
                await ctx.send(f"Output too large to upload (>25MB). Saved to `{filename}`.")
            else:
                await ctx.send(file=discord.File(file_path, filename))
                logger.info(f"{ctx.author} received file output: {filename}")
        except (OSError, discord.Forbidden, discord.HTTPException) as e:
            logger.error(f"Failed to send file {filename}: {e}")
            await ctx.send(f"Failed to send file: {str(e)}")
        finally:
            try:
                file_path.unlink(missing_ok=True)
            except OSError as e:
                logger.warning(f"Failed to delete temp file {file_path}: {e}")

    async def _report_error(self, ctx, error, command):
        if not self.error_channel_id:
            logger.debug("No error channel configured for error reporting")
            return
        channel = self.bot.get_channel(self.error_channel_id)
        if not channel:
            logger.warning(f"Error channel {self.error_channel_id} not found")
            return
        error_msg = f"Error in `{command}` by {ctx.author} ({ctx.author.id}):\n```py\n{str(error)[:1500]}\n```"
        try:
            await channel.send(error_msg)
            logger.info(f"Reported error in {command} to error channel")
        except discord.HTTPException as e:
            logger.error(f"Failed to send error report: {e}")

    @commands.group(name="jishaku", aliases=["jsk"], invoke_without_command=True)
    async def jishaku(self, ctx):
        logger.info(f"{ctx.author} invoked jsk command")
        prefix = ctx.prefix
        commands_list = [
            f"{prefix}jsk reload <cog>",
            f"{prefix}jsk reloadall",
            f"{prefix}jsk load <cog>",
            f"{prefix}jsk unload <cog>",
            f"{prefix}jsk restart",
            f"{prefix}jsk shutdown",
            f"{prefix}jsk owners",
            f"{prefix}jsk invite",
            f"{prefix}jsk backup",
            f"{prefix}jsk status",
            f"{prefix}jsk latency",
            f"{prefix}jsk extensions",
            f"{prefix}jsk shell <command>",
            f"{prefix}jsk execute <code>"
        ]
        await self._send_paginated(ctx, commands_list, "Jishaku Commands")
        logger.info(f"{ctx.author} received jsk command list")

    @jishaku.command(name="reload")
    async def jsk_reload(self, ctx, *, cog: str):
        if not cog:
            await ctx.send("Please specify a cog to reload.")
            return
        if cog not in self.bot.extensions:
            await ctx.send(f"Cog `{cog}` is not loaded.")
            return
        try:
            await self.bot.reload_extension(cog)
            await ctx.send(f"🔄 `{cog}`")
            logger.info(f"{ctx.author} reloaded cog: {cog}")
        except commands.ExtensionError as e:
            await ctx.send(f"Failed to reload `{cog}`:\n```py\n{str(e)[:1000]}\n```")
            await self._report_error(ctx, str(e), "jsk reload")
            logger.error(f"Failed to reload cog {cog}: {e}")

    @jishaku.command(name="reloadall")
    async def jsk_reloadall(self, ctx):
        async with ctx.typing():
            results = []
            for cog in list(self.bot.extensions.keys()):
                if cog == "cogs.jishaku":
                    results.append(f"↪️ `{cog}`")
                    continue
                try:
                    await self.bot.reload_extension(cog)
                    results.append(f"🔄 `{cog}`")
                except commands.ExtensionError as e:
                    results.append(f"Failed `{cog}`: {str(e)[:100]}")
                    await self._report_error(ctx, str(e), "jsk reloadall")
            await self._send_paginated(ctx, results, "Reload All Cogs")
            logger.info(f"{ctx.author} reloaded all cogs")

    @jishaku.command(name="load")
    async def jsk_load(self, ctx, *, cog: str):
        if not cog:
            await ctx.send("Please specify a cog to load.")
            return
        try:
            await self.bot.load_extension(cog)
            await ctx.send(f"▶️ `{cog}`")
            logger.info(f"{ctx.author} loaded cog: {cog}")
        except commands.ExtensionError as e:
            await ctx.send(f"Failed to load `{cog}`:\n```py\n{str(e)[:1000]}\n```")
            await self._report_error(ctx, str(e), "jsk load")
            logger.error(f"Failed to load cog {cog}: {e}")

    @jishaku.command(name="unload")
    async def jsk_unload(self, ctx, *, cog: str):
        if not cog:
            await ctx.send("Please specify a cog to unload.")
            return
        if cog == "cogs.jishaku":
            await ctx.send("Cannot unload Jishaku!")
            return
        if cog not in self.bot.extensions:
            await ctx.send(f"Cog `{cog}` is not loaded.")
            return
        try:
            await self.bot.unload_extension(cog)
            await ctx.send(f"⏸️ `{cog}`")
            logger.info(f"{ctx.author} unloaded cog: {cog}")
        except commands.ExtensionError as e:
            await ctx.send(f"Failed to unload `{cog}`:\n```py\n{str(e)[:1000]}\n```")
            await self._report_error(ctx, str(e), "jsk unload")
            logger.error(f"Failed to unload cog {cog}: {e}")

    @jishaku.command(name="restart")
    async def jsk_restart(self, ctx):
        try:
            await ctx.send("🔄...")
            logger.info(f"{ctx.author} initiated restart")
            with open("restart.json", "w", encoding="utf-8") as f:
                json.dump({"channel_id": ctx.channel.id}, f)
            python = sys.executable
            os.execl(python, python, *sys.argv)
        except Exception as e:
            logger.error(f"Restart failed: {e}")
            await ctx.send(f"Failed to restart: {str(e)[:1000]}")
            await self.bot.close()

    @jishaku.command(name="shutdown", aliases=["stop"])
    async def jsk_shutdown(self, ctx):
        try:
            await ctx.send("⏹️...")
            logger.info(f"{ctx.author} initiated shutdown")
            await self.bot.close()
        except discord.Forbidden as e:
            logger.error(f"Failed to send shutdown message: {e}")
            await self.bot.close()

    @jishaku.command(name="owners")
    async def jsk_owners(self, ctx, action: str = "list", user: discord.User = None):
        try:
            if action.lower() == "list":
                if not self.owner_ids:
                    await ctx.send("No owners configured.")
                    return
                owners = [f"<@{oid}> ({oid})" for oid in sorted(self.owner_ids)]
                await self._send_paginated(ctx, owners, "Bot Owners")
            elif action.lower() == "add":
                if not user:
                    await ctx.send("Specify a user to add (e.g., `jsk owners add @user`).")
                    return
                if user.id in self.owner_ids:
                    await ctx.send(f"{user.mention} is already an owner.")
                    return
                self.owner_ids.add(user.id)
                self.config["owner_ids"] = list(self.owner_ids)
                self._save_config()
                await ctx.send(f"Added {user.mention} as an owner.")
            elif action.lower() == "remove":
                if not user:
                    await ctx.send("Specify a user to remove (e.g., `jsk owners remove @user`).")
                    return
                if user.id not in self.owner_ids:
                    await ctx.send(f"{user.mention} is not an owner.")
                    return
                if len(self.owner_ids) <= 1:
                    await ctx.send("Cannot remove the last owner.")
                    return
                self.owner_ids.remove(user.id)
                self.config["owner_ids"] = list(self.owner_ids)
                self._save_config()
                await ctx.send(f"Removed {user.mention} as an owner.")
            else:
                await ctx.send("Invalid action. Use `list`, `add <user>`, or `remove <user>`.")
            logger.info(f"{ctx.author} ran owners action: {action} for user: {user.id if user else None}")
        except discord.Forbidden as e:
            logger.error(f"Failed to send owners message: {e}")
            await ctx.send("Failed to process owners command.")

    @jishaku.command(name="invite")
    async def jsk_invite(self, ctx):
        try:
            permissions = discord.Permissions(administrator=True)
            invite_url = discord.utils.oauth_url(
                self.bot.user.id,
                permissions=permissions,
                scopes=("bot", "applications.commands")
            )
            embed = discord.Embed(
                title="🛜",
                description=f"[Click to invite the bot]({invite_url})",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            logger.info(f"{ctx.author} generated invite link")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to generate invite:\n```py\n{str(e)[:1000]}\n```")
            await self._report_error(ctx, str(e), "jsk invite")
            logger.error(f"Failed to generate invite link: {e}")

    @jishaku.command(name="backup")
    async def jsk_backup(self, ctx, directories: str = "cogs"):
        async with ctx.typing():
            dir_list = directories.split() or ["cogs"]
            backup_dir = Path(self.config.get("backup_dir", "backups"))
            try:
                backup_dir.mkdir(exist_ok=True)
            except OSError as e:
                await ctx.send(f"Failed to create backup directory: {e}")
                return
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}.zip"
            temp_dir = Path(f"temp_backup_{timestamp}")
            try:
                temp_dir.mkdir(exist_ok=True)
                for directory in dir_list:
                    dir_path = Path(directory)
                    if not dir_path.exists() or not dir_path.is_dir():
                        await ctx.send(f"Directory `{directory}` does not exist.")
                        return
                    shutil.copytree(dir_path, temp_dir / directory, dirs_exist_ok=True)
                shutil.make_archive(backup_dir / f"backup_{timestamp}", "zip", temp_dir)
                backup_path = backup_dir / backup_name
                if backup_path.stat().st_size > 25 * 1024 * 1024:
                    await ctx.send(f"Backup created at `{backup_path}` (too large to upload).")
                else:
                    await ctx.send(f"🗂️ `{backup_name}`", file=discord.File(backup_path))
                    logger.info(f"{ctx.author} created backup of {', '.join(dir_list)}: {backup_name}")
            except (shutil.Error, OSError, discord.Forbidden) as e:
                await ctx.send(f"Failed to create backup:\n```py\n{str(e)[:1000]}\n```")
                await self._report_error(ctx, str(e), "jsk backup")
                logger.error(f"Failed to create backup of {', '.join(dir_list)}: {e}")
            finally:
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except OSError as e:
                    logger.warning(f"Failed to clean up temp backup directory: {e}")

    @jishaku.command(name="status", aliases=["stats", "stat"])
    async def jsk_status(self, ctx):
        try:
            uptime = datetime.datetime.utcnow() - self.start_time
            uptime_str = str(uptime).split(".")[0]
            embed = discord.Embed(title="Bot Status", color=discord.Color.blue())
            embed.add_field(name="Guilds", value=len(self.bot.guilds), inline=True)
            embed.add_field(name="Users", value=len(self.bot.users), inline=True)
            embed.add_field(name="Latency", value=f"{self.bot.latency * 1000:.2f} ms", inline=True)
            embed.add_field(name="Commands", value=len(self.bot.commands), inline=True)
            embed.add_field(name="Uptime", value=uptime_str, inline=True)
            await ctx.send(embed=embed)
            logger.info(f"{ctx.author} ran status")
        except discord.Forbidden as e:
            logger.error(f"Failed to send status embed: {e}")
            await ctx.send("Failed to send status. Ensure bot has embed permissions.")

    @jishaku.command(name="latency")
    async def jsk_latency(self, ctx):
        try:
            latency = self.bot.latency * 1000
            embed = discord.Embed(
                title="Bot Latency",
                description=f"{latency:.2f} ms",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            logger.info(f"{ctx.author} checked latency")
        except discord.Forbidden as e:
            logger.error(f"Failed to send latency embed: {e}")
            await ctx.send("Failed to send latency. Ensure bot has embed permissions.")

    @jishaku.command(name="extensions")
    async def jsk_extensions(self, ctx):
        cog_path = Path("cogs")
        if not cog_path.exists() or not cog_path.is_dir():
            await ctx.send("No `cogs` directory found.")
            return
        cogs = []
        for file in cog_path.glob("*.py"):
            if file.name == "__init__.py":
                continue
            cog_name = f"cogs.{file.stem}"
            status = " (loaded)" if cog_name in self.bot.extensions else ""
            cogs.append(f"- `{cog_name}`{status}")
        await self._send_paginated(ctx, sorted(cogs), "Available Cogs")
        logger.info(f"{ctx.author} listed extensions")

    @jishaku.command(name="shell", aliases=["sh"])
    async def jsk_shell(self, ctx, *, command: str):
        async with ctx.typing():
            try:
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                try:
                    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
                except asyncio.TimeoutError:
                    process.kill()
                    await ctx.send("Shell command timed out after 60 seconds.")
                    await self._report_error(ctx, "Shell command timeout", "jsk shell")
                    return
                output = (stdout + stderr).decode("utf-8", errors="replace")
                await self._send_file(ctx, output, "shell_output.txt")
                logger.info(f"{ctx.author} executed shell command: {command}")
            except (subprocess.SubprocessError, OSError) as e:
                await ctx.send(f"Error executing shell command:\n```py\n{str(e)[:1000]}\n```")
                await self._report_error(ctx, str(e), "jsk shell")
                logger.error(f"Shell command failed: {e}")

    @jishaku.command(name="execute", aliases=["exec"])
    async def jsk_execute(self, ctx, *, code: str):
        async with ctx.typing():
            try:
                code = code.strip()
                if code.startswith("```") and code.endswith("```"):
                    code = code[3:-3].strip()
                    if code.startswith("py\n"):
                        code = code[3:].strip()
                env = {
                    "bot": self.bot,
                    "ctx": ctx,
                    "discord": discord,
                    "commands": commands,
                    "__name__": "__main__"
                }
                env.update(globals())
                output = io.StringIO()
                sys.stdout = output
                try:
                    exec(code, env)
                finally:
                    sys.stdout = sys.__stdout__
                result = output.getvalue()
                if result:
                    await self._send_file(ctx, result, "exec_output.txt")
                else:
                    await ctx.send("Code executed successfully, no output.")
                logger.info(f"{ctx.author} executed Python code")
            except Exception as e:
                error_trace = "".join(traceback.format_exception(type(e), e, e.__traceback__))
                await self._send_file(ctx, error_trace, "exec_error.txt")
                await self._report_error(ctx, str(e), "jsk execute")
                logger.error(f"Failed to execute code: {e}")

async def setup(bot):
    try:
        required_intents = ["guilds", "members", "messages"]
        missing_intents = [intent for intent in required_intents if not getattr(bot.intents, intent)]
        if missing_intents:
            logger.error(f"Missing required intents: {', '.join(missing_intents)}")
            print(f"Error: Missing intents: {', '.join(missing_intents)}. Enable them in Discord Developer Portal and bot code.")
            return
        cog = Jishaku(bot)
        await bot.add_cog(cog)
        logger.info("Jishaku cog loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load Jishaku cog: {e}\n{traceback.format_exc()}")
        print(f"Failed to load Jishaku: {e}")
