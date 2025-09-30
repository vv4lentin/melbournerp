import discord
from discord.ext import commands
import asyncio

class SecondaryCmds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='cpurge')
    @commands.has_permissions(administrator=True)
    async def cpurge(self, ctx, count: int):
        if count < 1:
            await ctx.send("Please specify a number greater than 0.")
            return
        if count > 500:
            await ctx.send("Cannot delete more than 500 messages at a time.")
            return

        try:
            await ctx.channel.purge(limit=count + 1)  # +1 to include the command message
            await ctx.send(f"Successfully deleted {count} message(s).", delete_after=5)
        except discord.errors.Forbidden:
            await ctx.send("I don't have permission to delete messages.")
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    @cpurge.error
    async def cpurge_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="Unauthorized",
                description="You need administrator permissions to use this command.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Please specify the number of messages to delete (e.g., `.cpurge 10`).")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Please provide a valid number of messages to delete.")

    @commands.command(name='cexecute')
    @commands.is_owner()
    async def cexecute(self, ctx, user_id: int, *, command: str):
        try:
            target_user = await self.bot.fetch_user(user_id)
        except discord.errors.NotFound:
            await ctx.send("Invalid user ID. User not found.")
            return
        except Exception as e:
            await ctx.send(f"Error fetching user: {str(e)}")
            return

        # Create a fake message with the target user as the author
        fake_message = await ctx.channel.send(f"{command}")
        fake_message.author = target_user  # Set the author to the target user
        fake_ctx = await self.bot.get_context(fake_message)

        try:
            # Invoke the command with the fake context, respecting the target user's permissions
            await self.bot.invoke(fake_ctx)
            if not fake_ctx.command_failed:  # Check if the command executed successfully
                await ctx.send(f"Executed command '{command}' as {target_user.display_name}.")
        except Exception as e:
            await ctx.send(f"Failed to execute command: {str(e)}")
        finally:
            await fake_message.delete()  # Clean up the fake message

    @cexecute.error
    async def cexecute_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            embed = discord.Embed(
                title="Unauthorized",
                description="This command is restricted to the bot owner.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Please provide a user ID and command (e.g., `.cexecute 123456789012345678 cpurge 10`).")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Please provide a valid user ID.")

async def setup(bot):
    await bot.add_cog(SecondaryCmds(bot))
