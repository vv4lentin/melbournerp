import discord
from discord.ext import commands

class Callsigns(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Role ID to prefix mapping (cleaned, with O → F, CO → CF, and updated A role ID)
        self.role_prefixes = {
            1402933851436879932: "TM",
            1384460078928625755: "JM",
            1384459593366769776: "M",
            1384459510571335681: "SM",
            1384459413401899028: "HM",
            1420729658114052177: "HoM",
            1384438610303914015: "JA",
            1384437924652781690: "A",
            1384438407421497548: "SA",
            1384438224021094482: "HA",
            1420729110031765618: "HoA",
            1384437544825131171: "TSS",
            1384437559068987505: "JSS",
            1384437426503684127: "SS",
            1420635304607485972: "SSS",
            1384437286841876530: "HSS",
            1383402914340671558: "TMT",
            1420415728137277440: "TJMT",
            1383402824783626281: "JMT",
            1383402737340776468: "MGT",
            1383402634462892032: "SMT",
            1383402460777021500: "CM",
            1383401961621159957: "TAD",
            1383401856620957696: "AD",
            1383401686827143201: "DD",
            1383401586285346938: "D",
            1383401266998153216: "AF",
            1383386801682649088: "CF",
            1383401122063978496: "F"
        }
        # Role groups in specified order
        self.role_groups = [
            ("FounderShip", ["AF", "CF", "F"]),
            ("DirectorShip", ["TAD", "AD", "DD", "D"]),
            ("Management Team", ["TMT", "TJMT", "JMT", "MGT", "SMT", "CM"]),
            ("Staff Supervision Team", ["TSS", "JSS", "SS", "SSS", "HSS"]),
            ("Administration Team", ["JA", "A", "SA", "HA", "HoA"]),
            ("Moderation Team", ["TM", "JM", "M", "SM", "HM", "HoM"])
        ]

    # Helper function to generate callsign based on role
    def generate_callsign(self, role_id, index):
        # Get prefix from role ID, default to "X" if not found
        prefix = self.role_prefixes.get(role_id, "X")
        return f"{prefix}-{index}"

    @commands.command(name="update_callsigns")
    async def update_callsigns(self, ctx):
        # Check if user has the required role
        required_role_id = 1385160436046893168
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
        target_channel = guild.get_channel(1421432657891557426)
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
        ping_role = guild.get_role(1384465784042029198)
        ping_message = f"<@&{1384465784042029198}> The callsigns has been updated! Your callsign might have changed." if ping_role else "On-Duty Role not found"
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

