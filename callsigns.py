import discord
from discord.ext import commands

class Callsigns(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Role ID to prefix mapping (cleaned, with O → F, CO → CF, and updated A role ID)
        self.role_prefixes = {
            1409647282168660038: "AT",
            1409646969646874757: "TM",
            1409646965637251192: "JM",
            1409646961551740939: "M",
            1409646958351487029: "SM",
            1409646950155944058: "HM",
            1409646326152429568: "TA",
            1409646322742595625: "JA",
            1409646319232090223: "A",
            1409646316044156958: "SA",
            1409646285442646056: "HA",
            1409644038784811090: "JMT",
            1409643902734041211: "SMT",
            1409643792176517221: "CM",
            1409641396964556862: "DD",
            1409641367721742416: "AD",
            1409641315993649342: "D",
            1409639458684538978: "DF",
            1409639307068837978: "F"
        }
        # Role groups in specified order
        self.role_groups = [
            ("FounderShip", ["DF", "F"]),
            ("DirectorShip", ["DD", "AD", "D"]),
            ("Management Team", ["JMT", "SMT", "CM"]),
            ("Administration Team", ["TA", "JA", "A", "SA", "HA"]),
            ("Moderation Team", ["TM", "JM", "M", "SM", "HM"]),
            ("Awaiting Training", ["AT"])
        ]

    # Helper function to generate callsign based on role
    def generate_callsign(self, role_id, index):
        # Get prefix from role ID, default to "X" if not found
        prefix = self.role_prefixes.get(role_id, "X")
        return f"{prefix}-{index}"

    @commands.command(name="update_callsigns")
    async def update_callsigns(self, ctx):
        # Check if user has the required role
        required_role_id = 1410822274109542440
        if not any(role.id == required_role_id for role in ctx.author.roles):
            embed = discord.Embed(
                title="UNAUTHORIZED",
                description="You are not allowed to execute this command.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        guild = ctx.guild
        if not guild:
            await ctx.send("This command must be used in a server.")
            return

        # Get the target channel
        target_channel = guild.get_channel(1410300455858475089)
        if not target_channel:
            await ctx.send("Target channel not found.")
            return

        # Purge the target channel (up to 100 messages)
        try:
            await target_channel.purge(limit=100)
        except discord.Forbidden:
            await ctx.send("I lack permission to purge messages in the target channel.")
            return

        # Dictionary to store callsigns by member
        callsigns = {}
        role_counts = {}  # Track number of members per role for indexing

        # Iterate through all members in the guild
        for member in guild.members:
            # Get roles that match the role_prefixes keys
            eligible_roles = [role for role in member.roles if role.id in self.role_prefixes]
            if not eligible_roles:
                continue  # Skip members with no mapped roles

            # Sort roles by position (highest role first)
            highest_role = max(eligible_roles, key=lambda r: r.position)

            # Initialize or increment role count
            role_id = highest_role.id
            role_counts[role_id] = role_counts.get(role_id, 0) + 1

            # Generate callsign
            callsign = self.generate_callsign(highest_role.id, role_counts[role_id])
            callsigns[member] = callsign

        # Ping the role
        ping_role = guild.get_role(1409647524607955149)
        ping_message = f"<@&{1409647524607955149}> The callsigns has been updated! Your callsign might have changed." if ping_role else "On-Duty Role not found"
        await target_channel.send(ping_message)

        # Create an embed for each role group in specified order
        for group_name, prefixes in self.role_groups:
            # Filter members whose callsigns match the group's prefixes
            group_members = {
                member: cs for member, cs in callsigns.items()
                if any(cs.startswith(prefix + '-') for prefix in prefixes)
            }

            # Skip empty groups
            if not group_members:
                continue

            # Create embed for this group
            embed = discord.Embed(
                title=group_name,
                description="\n".join(
                    f"{member.mention} - {callsign}"
                    for member, callsign in sorted(group_members.items(), key=lambda x: x[1])  # Sort by callsign
                ),
                color=discord.Color.pink()
            )

            # Send embed to target channel
            await target_channel.send(embed=embed)

    # Error handling for the command
    @update_callsigns.error
    async def update_callsigns_error(self, ctx, error):
        await ctx.send("An error occurred while processing the command.")
        raise error

async def setup(bot):
    await bot.add_cog(Callsigns(bot))
