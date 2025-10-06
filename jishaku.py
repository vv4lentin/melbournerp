import discord
from discord.ext import commands
import subprocess
import textwrap
import asyncio
import time
import io
import contextlib
from datetime import datetime
import json
import os
import uuid
import logging
import platform
import statistics
import tracemalloc

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not installed. CPU/Memory stats in .jsk status will be limited.")

# Setup logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Jishaku(commands.Cog):
    def __init__(self, bot):
        logger.info("Initializing Jishaku cog")
        self.bot = bot
        self.start_time = datetime.utcnow()
        self.error_log_file = "errors.json"
        self.recent_pings = []  # Track recent pings for variance
        if not os.path.exists(self.error_log_file):
            with open(self.error_log_file, "w") as f:
                json.dump([], f)

    async def _log_error(self, command_name, error, args=None):
        error_id = str(uuid.uuid4())
        error_data = {
            "id": error_id,
            "timestamp": datetime.utcnow().isoformat(),
            "command": command_name,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "args": str(args) if args else "None"
        }
        try:
            with open(self.error_log_file, "r+") as f:
                errors = json.load(f)
                errors.append(error_data)
                f.seek(0)
                json.dump(errors, f, indent=2)
        except Exception as log_error:
            logger.error(f"Failed to log error: {log_error}")

    async def send_paginated(self, ctx, content, max_length=1900):
        try:
            if len(content) <= max_length:
                await ctx.send(f"```\n{content}\n```")
                return
            parts = [content[i:i + max_length] for i in range(0, len(content), max_length)]
            for i, part in enumerate(parts, 1):
                await ctx.send(f"```\nPart {i}/{len(parts)}:\n{part}\n```")
                await asyncio.sleep(0.5)
        except Exception as e:
            await self._log_error("send_paginated", e, content)
            await ctx.send(f"Error sending output: {type(e).__name__}: {str(e)}")

    async def measure_loop_lag(self):
        start = time.time()
        await asyncio.sleep(0)
        return round((time.time() - start) * 1000, 2)

    @commands.group(name="jsk", invoke_without_command=True)
    @commands.is_owner()
    async def jishaku(self, ctx):
        try:
            await ctx.send("Available: shell, exec, eval, git, ping, load, unload, shutdown, restart, refresh, refreshall, cogs, status")
        except Exception as e:
            await self._log_error("jsk", e)
            await ctx.send(f"Error: {type(e).__name__}: {str(e)}")

    @jishaku.command(name="shell", aliases=["sh"])
    @commands.is_owner()
    async def jsk_shell(self, ctx, *, command: str):
        try:
            start_time = time.time()
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
            except asyncio.TimeoutError:
                process.kill()
                await ctx.send("Command timed out after 30 seconds.")
                return
            exec_time = round(time.time() - start_time, 2)
            output = (stdout or b"").decode("utf-8", errors="ignore") + (stderr or b"").decode("utf-8", errors="ignore")
            return_code = process.returncode
            cwd = os.getcwd()
            result = (
                f"**Shell Execution**\n"
                f"Command: {command}\n"
                f"CWD: {cwd}\n"
                f"Return Code: {return_code}\n"
                f"Execution Time: {exec_time}s\n"
                f"Output:\n{output or 'No output.'}"
            )
            await self.send_paginated(ctx, result)
        except Exception as e:
            await self._log_error("shell", e, command)
            await ctx.send(f"Error: {type(e).__name__}: {str(e)}")

    @jishaku.command(name="exec")
    @commands.is_owner()
    async def jsk_exec(self, ctx, someoneid: int, *, command: str):
        try:
            start_time = time.time()
            user = await self.bot.fetch_user(someoneid)
            if not user:
                await ctx.send("User not found.")
                return

            target_guild = None
            for guild in self.bot.guilds:
                if guild.get_member(someoneid):
                    target_guild = guild
                    break
            if not target_guild:
                await ctx.send("User is not in any guild the bot can access.")
                return

            member = target_guild.get_member(someoneid)
            command_name = command.split()[0] if command else ""
            if not command_name:
                await ctx.send("No command provided.")
                return

            cmd = self.bot.get_command(command_name)
            if not cmd:
                await ctx.send(f"Command `{command_name}` not found.")
                return

            perms = member.guild_permissions if member else None
            prefix = (await self.bot.get_prefix(ctx.message))[0]
            fake_message = await ctx.channel.send(f"{prefix}{command}")
            fake_message.author = user
            fake_message.guild = target_guild
            fake_message.channel = ctx.channel

            new_ctx = await self.bot.get_context(fake_message)
            success = True
            try:
                await self.bot.invoke(new_ctx)
            except Exception as invoke_error:
                success = False
                await self._log_error(f"exec_invoke_{command_name}", invoke_error, command)

            await fake_message.delete()
            exec_time = round(time.time() - start_time, 2)
            status = "Success" if success else "Failed"
            result = (
                f"**Command Execution**\n"
                f"Command: {command}\n"
                f"User: {user} (ID: {someoneid})\n"
                f"Guild: {target_guild.name}\n"
                f"Permissions: {perms.administrator if perms else 'N/A'}\n"
                f"Status: {status}\n"
                f"Execution Time: {exec_time}s"
            )
            await ctx.send(result)
        except Exception as e:
            await self._log_error("exec", e, f"{someoneid} {command}")
            await self.send_paginated(ctx, f"Error: {type(e).__name__}: {str(e)}")

    @jishaku.command(name="eval")
    @commands.is_owner()
    async def jsk_eval(self, ctx, *, expression: str):
        try:
            env = {
                'bot': self.bot,
                'ctx': ctx,
                'channel': ctx.channel,
                'author': ctx.author,
                'guild': ctx.guild,
                'message': ctx.message
            }
            env.update(globals())
            result = eval(expression, env)
            if asyncio.iscoroutine(result):
                result = await result
            await self.send_paginated(ctx, f"**Eval Result**\nExpression: {expression}\nResult: {str(result) or 'No output.'}")
        except Exception as e:
            await self._log_error("eval", e, expression)
            await self.send_paginated(ctx, f"Error: {type(e).__name__}: {str(e)}")

    @jishaku.command(name="git")
    @commands.is_owner()
    async def jsk_git(self, ctx, *, git_command: str):
        try:
            start_time = time.time()
            process = await asyncio.create_subprocess_shell(
                f"git {git_command}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
            except asyncio.TimeoutError:
                process.kill()
                await ctx.send("Git command timed out after 30 seconds.")
                return
            exec_time = round(time.time() - start_time, 2)
            output = (stdout or b"").decode("utf-8", errors="ignore") + (stderr or b"").decode("utf-8", errors="ignore")
            return_code = process.returncode
            cwd = os.getcwd()
            result = (
                f"**Git Execution**\n"
                f"Command: git {git_command}\n"
                f"CWD: {cwd}\n"
                f"Return Code: {return_code}\n"
                f"Execution Time: {exec_time}s\n"
                f"Output:\n{output or 'No output.'}"
            )
            await self.send_paginated(ctx, result)
        except Exception as e:
            await self._log_error("git", e, git_command)
            await ctx.send(f"Error: {type(e).__name__}: {str(e)}")

    @jishaku.command(name="ping")
    @commands.is_owner()
    async def jsk_ping(self, ctx):
        try:
            start_time = time.time()
            message = await ctx.send("Pinging...")
            ws_latency = round(self.bot.latency * 1000, 2)
            api_latency = round((time.time() - start_time) * 1000, 2)
            loop_lag = await self.measure_loop_lag()
            self.recent_pings.append(ws_latency)
            if len(self.recent_pings) > 10:
                self.recent_pings.pop(0)
            ping_variance = round(statistics.stdev(self.recent_pings), 2) if len(self.recent_pings) > 1 else "N/A"
            await message.edit(content=(
                f"**Ping Results**\n"
                f"Websocket: {ws_latency}ms\n"
                f"API: {api_latency}ms\n"
                f"Event Loop Lag: {loop_lag}ms\n"
                f"Ping Variance: {ping_variance}ms"
            ))
        except Exception as e:
            await self._log_error("ping", e)
            await ctx.send(f"Error: {type(e).__name__}: {str(e)}")

    @jishaku.command(name="load")
    @commands.is_owner()
    async def jsk_load(self, ctx, cog: str):
        try:
            await self.bot.load_extension(cog)
            path = self.bot.extensions.get(cog, "Unknown")
            await ctx.send(f"Cog `{cog}` loaded successfully.\nPath: {path}\nTotal cogs: {len(self.bot.cogs)}")
        except Exception as e:
            await self._log_error("load", e, cog)
            await ctx.send(f"Failed to load `{cog}`: {type(e).__name__}: {str(e)}")

    @jishaku.command(name="unload")
    @commands.is_owner()
    async def jsk_unload(self, ctx, cog: str):
        try:
            await self.bot.unload_extension(cog)
            await ctx.send(f"Cog `{cog}` unloaded successfully.\nTotal cogs: {len(self.bot.cogs)}")
        except Exception as e:
            await self._log_error("unload", e, cog)
            await ctx.send(f"Failed to unload `{cog}`: {type(e).__name__}: {str(e)}")

    @jishaku.command(name="shutdown")
    @commands.is_owner()
    async def jsk_shutdown(self, ctx):
        try:
            await ctx.send("Shutting down...")
            await self.bot.close()
        except Exception as e:
            await self._log_error("shutdown", e)
            await ctx.send(f"Error: {type(e).__name__}: {str(e)}")

    @jishaku.command(name="restart")
    @commands.is_owner()
    async def jsk_restart(self, ctx):
        try:
            await ctx.send("Restarting...")
            await self.bot.close()
            import os
            os._exit(0)
        except Exception as e:
            await self._log_error("restart", e)
            await ctx.send(f"Error: {type(e).__name__}: {str(e)}")

    @jishaku.command(name="refresh")
    @commands.is_owner()
    async def jsk_refresh(self, ctx, cog: str):
        try:
            await self.bot.reload_extension(cog)
            path = self.bot.extensions.get(cog, "Unknown")
            await ctx.send(f"Cog `{cog}` refreshed successfully.\nPath: {path}\nTotal cogs: {len(self.bot.cogs)}")
        except Exception as e:
            await self._log_error("refresh", e, cog)
            await ctx.send(f"Failed to refresh `{cog}`: {type(e).__name__}: {str(e)}")

    @jishaku.command(name="refreshall")
    @commands.is_owner()
    async def jsk_refreshall(self, ctx):
        try:
            start_time = time.time()
            results = []
            success_count = 0
            for cog in list(self.bot.extensions.keys()):
                try:
                    await self.bot.reload_extension(cog)
                    results.append(f"✓ `{cog}` reloaded")
                    success_count += 1
                except Exception as e:
                    results.append(f"✗ `{cog}` failed: {type(e).__name__}: {str(e)}")
                    await self._log_error(f"refreshall_{cog}", e, cog)
            exec_time = round(time.time() - start_time, 2)
            summary = f"\nSummary: {success_count}/{len(self.bot.extensions)} cogs refreshed successfully.\nTotal Time: {exec_time}s"
            await self.send_paginated(ctx, "\n".join(results) + summary)
        except Exception as e:
            await self._log_error("refreshall", e)
            await ctx.send(f"Error: {type(e).__name__}: {str(e)}")

    @jishaku.command(name="cogs")
    @commands.is_owner()
    async def jsk_cogs(self, ctx, verbose: str = None): # type: ignore
        try:
            cog_details = []
            for name, cog in self.bot.cogs.items():
                cmd_count = len(cog.get_commands())
                status = "✓ Loaded" if name in self.bot.extensions else "✗ Unloaded"
                path = self.bot.extensions.get(name, "Unknown")
                detail = f"{name} | Commands: {cmd_count} | Status: {status}"
                if verbose == "verbose":
                    detail += f" | Path: {path}"
                cog_details.append(detail)
            details = "Loaded Cogs Details:\n" + "\n".join(cog_details)
            await self.send_paginated(ctx, details or "No cogs loaded.")
        except Exception as e:
            await self._log_error("cogs", e, verbose)
            await ctx.send(f"Error: {type(e).__name__}: {str(e)}")

    @jishaku.command(name="status")
    @commands.is_owner()
    async def jsk_status(self, ctx, verbose: str = None): # pyright: ignore[reportArgumentType]
        try:
            uptime = datetime.utcnow() - self.start_time
            days, seconds = divmod(uptime.total_seconds(), 86400)
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
            uptime_seconds = round(uptime.total_seconds(), 2)

            ws_latency = round(self.bot.latency * 1000, 2)
            loop_lag = await self.measure_loop_lag()
            ping_variance = (
                round(statistics.stdev(self.recent_pings), 2)
                if len(self.recent_pings) > 1
                else "N/A"
            )

            owner_id = getattr(self.bot, "owner_id", None)
            owner = await self.bot.fetch_user(owner_id) if owner_id else None
            owner_str = f"{owner.name} ({owner_id})" if owner else "Unknown"

            cached_messages = (
                len(self.bot.cached_messages)
                if hasattr(self.bot, "cached_messages")
                else "N/A"
            )
            voice_connections = len(self.bot.voice_clients)
            private_channels = len(
                [ch for ch in getattr(self.bot, "private_channels", []) if isinstance(ch, discord.DMChannel)]
            )

            shard_count = getattr(self.bot, "shard_count", None)
            shard_ids = getattr(self.bot, "shard_ids", None)
            shard_info = f"Shards: {shard_count}/{shard_ids}" if shard_count else "Shards: N/A"

            # Process Stats
            if PSUTIL_AVAILABLE:
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                cpu_percent = process.cpu_percent(interval=0.1)
                process_info = f"Memory: {memory_mb:.2f} MB | CPU: {cpu_percent:.2f}%"
            else:
                process_info = "Process stats: Unavailable (psutil not installed)"

            # TraceMalloc Info
            if tracemalloc.is_tracing():
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_info = f"Current: {current / 1024 / 1024:.2f} MB | Peak: {peak / 1024 / 1024:.2f} MB"
            else:
                tracemalloc_info = "N/A"

            # System Info
            system_info = (
                f"Python: {platform.python_version()}\n"
                f"OS: {platform.system()} {platform.release()} ({platform.version()})"
            )

            status = getattr(self.bot, "status", "Unknown")
            activity = getattr(getattr(self.bot, "activity", None), "name", "None")

            guild_perms = ""
            if ctx.guild and ctx.guild.me:
                bot_member = ctx.guild.me
                admin = bot_member.guild_permissions.administrator
                guild_perms = f"Bot Perms in Guild: Administrator = {admin}"

            # Construct the main status output
            status_table = (
                f"**Bot Status Overview**\n"
                f"{'='*30}\n"
                f"**System**\n"
                f"{system_info}\n"
                f"TraceMalloc: {tracemalloc_info}\n"
                f"{process_info}\n"
                f"{'='*30}\n"
                f"**Bot**\n"
                f"Uptime: {uptime_str} ({uptime_seconds}s)\n"
                f"Owner: {owner_str}\n"
                f"Status: {status}\n"
                f"Activity: {activity}\n"
                f"Guilds: {len(self.bot.guilds)}\n"
                f"Users (Cached): {len(self.bot.users)}\n"
                f"Cached Messages: {cached_messages}\n"
                f"Commands: {len(set(self.bot.commands))}\n"
                f"Cogs: {len(self.bot.cogs)} | Extensions: {len(self.bot.extensions)}\n"
                f"{'='*30}\n"
                f"**Network**\n"
                f"Websocket: {ws_latency}ms\n"
                f"Ping Variance: {ping_variance}ms\n"
                f"Event Loop Lag: {loop_lag}ms\n"
                f"{shard_info}\n"
                f"{guild_perms}\n"
                f"discord.py: {discord.__version__}"
            )

            # Verbose extension list
            if verbose == "verbose":
                extensions = getattr(self.bot, "extensions", {})
                extension_list = "\n".join([f"- {ext}" for ext in extensions]) or "None"
                status_table += f"\n\n**Loaded Extensions:**\n{extension_list}"

            await self.send_paginated(ctx, status_table)

        except Exception as e:
            await self._log_error("status", e, verbose)
            await ctx.send(f"Error: {type(e).__name__}: {str(e)}")

async def setup(bot):
    logger.info("Setting up Jishaku cog")
    try:
        await bot.add_cog(Jishaku(bot))
        logger.info("Jishaku cog loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load Jishaku cog: {type(e).__name__}: {str(e)}")

        raise
