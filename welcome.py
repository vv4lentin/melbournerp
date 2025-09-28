import discord
from discord.ext import commands

class WelcomeGoodbye(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_guild_id = 1383386513533964349  # Target guild ID
        self.welcome_channel_id = 1384448616827064351  # Welcome channel ID
        self.goodbye_channel_id = 1383431917923336252  # Goodbye channel ID
        self.autorole_ids = [1384461995587276880, 1384462876319940608]  # Autorole IDs
        self.image_url = "https://cdn.discordapp.com/attachments/1383386514385272864/1421439122316464219/NEW_YORK.png?ex=68da5b57&is=68d909d7&hm=7b874e6eabe6b910561e9c5acbf415f414546f109bd350bac887f7d72dc90c93&"

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id != self.target_guild_id:
            return

        # Create welcome embed
        embed = discord.Embed(
            title="Welcome to Melbourne Roleplay!",
            description="Please verify to get access to all the channels.",
            color=discord.Color.green()
        )
        embed.set_image(url=self.image_url)
        embed.set_footer(text=f"Member ID: {member.id}")

        # Find the welcome channel
        channel = member.guild.get_channel(self.welcome_channel_id)
        
        if channel and isinstance(channel, discord.TextChannel):
            await channel.send(content=f"{member.mention}", embed=embed)

        # Assign autoroles
        for role_id in self.autorole_ids:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason="Autorole on join")
                except discord.Forbidden:
                    print(f"Missing permissions to assign role {role.name} to {member.name}")
                except discord.HTTPException as e:
                    print(f"Failed to assign role {role.name} to {member.name}: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.guild.id != self.target_guild_id:
            return

        # Create goodbye embed
        embed = discord.Embed(
            title="Oh.. someone left the server",
            description=f"Membercount: {member.guild.member_count}",
            color=discord.Color.red()
        )
        embed.set_image(url=self.image_url)
        embed.set_footer(text=f"Member ID: {member.id}")

        # Find the goodbye channel
        channel = member.guild.get_channel(self.goodbye_channel_id)
        
        if channel and isinstance(channel, discord.TextChannel):
            await channel.send(content=f"{member.mention}", embed=embed)

async def setup(bot):
    await bot.add_cog(WelcomeGoodbye(bot))
