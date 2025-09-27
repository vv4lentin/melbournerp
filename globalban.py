import discord
from discord.ext import commands
import logging

# Set up logging
logging.basicConfig(filename='globalban.log', level=logging.INFO, 
                    format='%(asctime)s:%(levelname)s:%(message)s')

class GlobalBan(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.allowed_role_ids = [1383401188447490099, 1421447689542832158]
        self.log_channel_id = 1421431875553067039

    async def get_user(self, ctx, user_input):
        try:
            # Try to convert input to user ID
            user_id = int(user_input)
            return await self.bot.fetch_user(user_id)
        except ValueError:
            # If not an ID, try to find by username
            return discord.utils.get(self.bot.users, name=user_input)
        except discord.NotFound:
            return None

    async def check_roles(self, ctx):
        return any(role.id in self.allowed_role_ids for role in ctx.author.roles)

    async def log_to_channel(self, message):
        log_channel = self.bot.get_channel(self.log_channel_id)
        if log_channel:
            await log_channel.send(message)

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def globalban(self, ctx, user_input: str, *, reason: str):
        if not await self.check_roles(ctx):
            embed = discord.Embed(
                title="UNAUTHORIZED",
                description=f"You are not allowed to execute this command (.globalban)",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            await self.log_to_channel(f"Unauthorized .globalban attempt by {ctx.author} ({ctx.author.id})")
            return

        user = await self.get_user(ctx, user_input)
        
        if not user:
            await ctx.send("User not found!")
            return

        banned_servers = []
        for guild in self.bot.guilds:
            try:
                await guild.ban(user, reason=f"Global Banned by {ctx.author}, reason: {reason}")
                banned_servers.append(guild.name)
            except discord.Forbidden:
                continue
            except discord.HTTPException:
                continue

        if not banned_servers:
            await ctx.send("Failed to ban user from any servers!")
            return

        # Create embed
        embed = discord.Embed(title="Global Ban - Successful", color=discord.Color.red())
        embed.add_field(name="User", value=user.name, inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Servers Banned", value="\n".join(banned_servers), inline=False)
        embed.set_footer(text="Melbourne Roleplay")
        
        await ctx.send(embed=embed)
        
        # Log to file and channel
        log_message = f"Global Banned by {ctx.author}, User: {user.name} ({user.id}), Reason: {reason}"
        logging.info(log_message)
        await self.log_to_channel(log_message)

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def unglobalban(self, ctx, user_input: str):
        if not await self.check_roles(ctx):
            embed = discord.Embed(
                title="UNAUTHORIZED",
                description=f"You are not allowed to execute this command (.unglobalban)",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            await self.log_to_channel(f"Unauthorized .unglobalban attempt by {ctx.author} ({ctx.author.id})")
            return

        user = await self.get_user(ctx, user_input)
        
        if not user:
            await ctx.send("User not found!")
            return

        unbanned_servers = []
        for guild in self.bot.guilds:
            try:
                await guild.unban(user, reason=f"Global Unbanned by {ctx.author}")
                unbanned_servers.append(guild.name)
            except discord.Forbidden:
                continue
            except discord.HTTPException:
                continue

        if not unbanned_servers:
            await ctx.send("Failed to unban user from any servers!")
            return

        # Create embed
        embed = discord.Embed(title="Global Unban - Successful", color=discord.Color.green())
        embed.add_field(name="User", value=user.name, inline=False)
        embed.add_field(name="Reason", value="Unbanned", inline=False)
        embed.add_field(name="Servers Unbanned", value="\n".join(unbanned_servers), inline=False)
        embed.set_footer(text="Melbourne Roleplay")
        
        await ctx.send(embed=embed)
        
        # Log to file and channel
        log_message = f"Global Unbanned by {ctx.author}, User: {user.name} ({user.id})"
        logging.info(log_message)
        await self.log_to_channel(log_message)

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="UNAUTHORIZED",
                description=f"You are not allowed to execute this command ({ctx.command.name})",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Missing required arguments! Usage: .globalban [user] [reason] or .unglobalban [user]")
        else:
            await ctx.send(f"An error occurred: {error}")

async def setup(bot):
    await bot.add_cog(GlobalBan(bot))
