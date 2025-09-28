import discord
from discord.ext import commands
from discord import ButtonStyle, Embed
from discord.ui import Button, View

class VoteView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)  # Persistent view
        self.cog = cog

    @discord.ui.button(label="Vote", style=ButtonStyle.green)
    async def vote_button(self, interaction: discord.Interaction, button: Button):
        user = interaction.user
        if user.id in self.cog.voters:
            await interaction.response.send_message("You have already voted!", ephemeral=True)
            return
        self.cog.voters.add(user.id)
        await interaction.response.send_message("Your vote has been recorded!", ephemeral=True)
        # Update the embed with the current vote count
        embed = interaction.message.embeds[0]
        embed.set_field_at(0, name="Join Code", value=f"MeL\n**Votes: {len(self.cog.voters)}/5**", inline=False)
        await interaction.message.edit(embed=embed)

    @discord.ui.button(label="Voters", style=ButtonStyle.grey)
    async def voters_button(self, interaction: discord.Interaction, button: Button):
        if not self.cog.voters:
            await interaction.response.send_message("No votes yet!", ephemeral=True)
            return
        voter_names = [self.cog.bot.get_user(user_id).mention for user_id in self.cog.voters if self.cog.bot.get_user(user_id)]
        voters_list = "\n".join(voter_names) if voter_names else "No valid voters found."
        await interaction.response.send_message(f"**Voters:**\n{voters_list}", ephemeral=True)

    @discord.ui.button(label="Cancel Vote", style=ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        user = interaction.user
        if user.id not in self.cog.voters:
            await interaction.response.send_message("You haven't voted yet!", ephemeral=True)
            return
        self.cog.voters.remove(user.id)
        await interaction.response.send_message("Your vote has been canceled!", ephemeral=True)
        # Update the embed with the current vote count
        embed = interaction.message.embeds[0]
        embed.set_field_at(0, name="Join Code", value=f"MeL\n**Votes: {len(self.cog.voters)}/5**", inline=False)
        await interaction.message.edit(embed=embed)

class Sessions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.required_role_id = 1420730840929009714
        self.target_channel_id = 1421088776993767456
        self.voters = set()  # Store voter IDs

    # Unauthorized embed
    def unauthorized_embed(self, command_name):
        embed = Embed(title="UNAUTHORIZED", description=f"You are not allowed to execute this command ({command_name}).", color=discord.Color.red())
        return embed

    # Check for required role
    def has_required_role():
        async def predicate(ctx):
            role = ctx.guild.get_role(ctx.cog.required_role_id)
            if role in ctx.author.roles:
                return True
            await ctx.send(embed=ctx.cog.unauthorized_embed(ctx.command.name))
            return False
        return commands.check(predicate)

    @commands.command()
    @has_required_role()
    async def vote(self, ctx):
        channel = self.bot.get_channel(self.target_channel_id)
        if not channel:
            await ctx.send("Target channel not found.")
            return

        embed = discord.Embed(
            color=14384577,
            title="Server Start Up (SSU) | Community Vote",
            description="Vote for SSU with the button below, 5 votes are required to SSU."
        )
        embed.set_author(
            name="Miami Beach Roleplay",
            icon_url="https://cdn.discordapp.com/icons/1409637452125175850/778a19b6966c1a9ae0d1cef3655b7c97.png?size=512"
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1409991757025771681/1410924642343976980/NEW_YORK_2.png?ex=68b2c978&is=68b177f8&hm=667deaf834ed429f60d7a1a4454088e474e9ab83bb0c299d7549456adadc36ee&")
        embed.set_footer(
            text="Miami Beach Roleplay | Sessions Management System",
            icon_url="https://cdn.discordapp.com/icons/1409637452125175850/778a19b6966c1a9ae0d1cef3655b7c97.png?size=512"
        )
        embed.add_field(
            name="Join Code",
            value=f"SFRole\n**Votes: {len(self.voters)}/10**",
            inline=False
        )
        embed.add_field(
            name="Server Owner",
            value="fartsaremelly2002",
            inline=False
        )

        # Create view with buttons
        view = VoteView(self)

        # Send embed with everyone ping
        await channel.send("@everyone", embed=embed, view=view)
        await ctx.send("Vote embed sent successfully.")

    @commands.command()
    @has_required_role()
    async def ssu(self, ctx):
        channel = self.bot.get_channel(self.target_channel_id)
        if not channel:
            await ctx.send("Target channel not found.")
            return

        embed = discord.Embed(
            color=14384577,
            title="Server Start Up (SSU)",
            description="The in-game server has started up! Everyone who voted for SSU are required to join. Please follow all our rules during this session, if you require assistance, call !mod."
        )
        embed.set_author(
            name="Miami Beach Roleplay",
            icon_url="https://cdn.discordapp.com/icons/1409637452125175850/778a19b6966c1a9ae0d1cef3655b7c97.png?size=512"
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1409991757025771681/1410924642343976980/NEW_YORK_2.png?ex=68b2c978&is=68b177f8&hm=667deaf834ed429f60d7a1a4454088e474e9ab83bb0c299d7549456adadc36ee&")
        embed.set_footer(
            text="Miami Beach Roleplay | Sessions Management System",
            icon_url="https://cdn.discordapp.com/icons/1409637452125175850/778a19b6966c1a9ae0d1cef3655b7c97.png?size=512"
        )
        embed.add_field(
            name="Join Code",
            value="SFRole",
            inline=False
        )
        embed.add_field(
            name="Server Owner",
            value="fartsaremelly2002",
            inline=False
        )

        # Send embed with everyone ping
        await channel.send("@everyone", embed=embed)
        await ctx.send("SSU embed sent successfully.")
        self.voters.clear()  # Reset voters after SSU

    @commands.command()
    @has_required_role()
    async def ssd(self, ctx):
        channel = self.bot.get_channel(self.target_channel_id)
        if not channel:
            await ctx.send("Target channel not found.")
            return

        embed = discord.Embed(
            color=14384577,
            title="Server Shutdown (SSD)",
            description="The in-game server has shut down. Please leave the server. The MB:RP Staff Team hope to see y'all soon in the next session!"
        )
        embed.set_author(
            name="Miami Beach Roleplay",
            icon_url="https://cdn.discordapp.com/icons/1409637452125175850/778a19b6966c1a9ae0d1cef3655b7c97.png?size=512"
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1409991757025771681/1410924642343976980/NEW_YORK_2.png?ex=68b2c978&is=68b177f8&hm=667deaf834ed429f60d7a1a4454088e474e9ab83bb0c299d7549456adadc36ee&")
        embed.set_footer(
            text="Miami Beach Roleplay | Sessions Management System",
            icon_url="https://cdn.discordapp.com/icons/1409637452125175850/778a19b6966c1a9ae0d1cef3655b7c97.png?size=512"
        )
        embed.add_field(
            name="Join Code",
            value="SFRole",
            inline=False
        )
        embed.add_field(
            name="Server Owner",
            value="fartsaremelly2002",
            inline=False
        )

        # Send embed
        await channel.send(embed=embed)
        await ctx.send("SSD embed sent successfully.")
        self.voters.clear()  # Reset voters after SSD

async def setup(bot):
    await bot.add_cog(Sessions(bot))
