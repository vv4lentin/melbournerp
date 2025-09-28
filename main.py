import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Select
import asyncio
import io
import re
import json
from keep_alive import keep_alive

# Bot setup with all intents
intents = discord.Intents.all()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='.', intents=intents)
bot.sleep_mode = True
ALLOWED_ROLE_ID = 1385160436046893168
SAY_ROLE_ID = 1385160436046893168
HELP_REQUEST_ROLE_ID = 1384466481831608381
IA_ROLE = 1420636084110495846  # New role ID for Internal Affairs commands
loaded_cogs = []

# Ticket system configuration
TICKET_PANEL_CHANNEL = 1402948558197362758
TRANSCRIPT_CHANNEL = 1403262039597776926
SUPPORT_ROLES = {
    'general': 1420671099242549318,
    'internals': 1420636084110495846,
    'management': 1383402156111167598,
    'senior': 1385160436046893168
}
TICKET_DATA = {}

# Role hierarchy
ROLE_HIERARCHY = [
    1402933851436879932, 1384460078928625755, 1384459593366769776, 1384459510571335681,
    1384459413401899028, 1420729658114052177, 1384438610303914015, 1384437924652781690,
    1384438407421497548, 1384438224021094482, 1420729110031765618, 1384437544825131171,
    1384437559068987505, 1384437426503684127, 1420635304607485972, 1384437286841876530,
    1383402914340671558, 1420415728137277440, 1383402824783626281, 1383402737340776468,
    1383402634462892032, 1383402460777021500, 1385160436046893168, 1383401961621159957,
    1383401856620957696, 1383401686827143201, 1383401586285346938, 1383401266998153216,
    1383386801682649088, 1383401122063978496, 1421437306912641129
]

# Warning and strike roles
WARNING_ROLES = {
    'Warning 1': 1409648184614977536,
    'Warning 2': 1409648178541891665
}
STRIKE_ROLES = {
    'Strike 1': 1409648127383699457,
    'Strike 2': 1409648126226206730
}
BLACKLIST_ROLE = 1409648100632559717
AT_ROLE = 1402933851436879932

# Application system configuration
ROLE_IDS = {
    'erlc_moderator': 1384461995587276880,
    'discord_moderator': 1384461995587276880,
    'internal_affairs': 1384461995587276880,
    'directorship': 1409644061463281714
}
REVIEW_CHANNEL_IDS = {
    'erlc_moderator': 1421437062963527690,
    'discord_moderator': 1421437062963527690,
    'internal_affairs': 1421437062963527690,
    'directorship': 1421437062963527690
}
APPLICATION_PANEL_CHANNEL_ID = 1421136732912353463
REVIEWER_ROLE_ID = 1385160436046893168

APPLICATION_QUESTIONS = {
    'erlc_moderator': [
        "What is your roblox username?",
        "What is your discord username?",
        "What is your discord ID?",
        "How old are you?",
        "Do you have any experience as ER:LC Moderator?",
        "Why do you want to become an ER:LC Moderator?",
        "Describe a situation where you handled a conflict between 2 players.",
        "What would you do if someone VDMed your staff car?",
        "What would you do if someone was saying something disrespectful to another player?",
        "What would you do if a player was breaking ToS?",
        "What would you do if someone RDMed someone else?",
        "Do you know our in-game rules?",
        "Do you understand that the IA team and the Senior High Ranking team can issue you infractions?",
        "Do you understand that you will have to go past a training if your application is accepted?",
        "Do you have any questions?"
    ],
    'discord_moderator': ["[APPLICATION UNAVAILIBLE]"],
    'internal_affairs': [
        "What is your roblox username?",
        "What is your discord username?",
        "What is your discord ID?",
        "How old are you?",
        "Do you have any past experience as Internals Affairs?",
        "Why do you want to join the Internal Affairs Team?",
        "How would you handle a case where a moderator is accused of mod-abuse?",
        "How would you handle a ticket?",
        "What would you do if you witness an on-duty moderator using 2 letters commands?",
        "What would you do if an off-duty moderator was using commands?",
        "Do you understand that you will have to go past a 2 weeks trial?"
    ],
    'directorship': ["[APPLICATION UNAVAILIBLE]"]
}
# DONE HERE

# Example button view for embeds.json
class ExampleButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Click Me", style=discord.ButtonStyle.green, custom_id="example_button")
    async def example_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Button clicked!", ephemeral=True)

# View mapping for embeds.json
VIEW_MAPPING = {
    'ExampleButtonView': ExampleButtonView
}

# Ticket view with dropdown
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="Select a support type...",
        options=[
            discord.SelectOption(label="General Support", value="general"),
            discord.SelectOption(label="Internal Affairs Support", value="internals"),
            discord.SelectOption(label="Management Support", value="management"),
            discord.SelectOption(label="Senior High Rank Support", value="senior")
        ],
        custom_id="ticket_select"
    )
    async def select_callback(self, interaction: discord.Interaction, select):
        if bot.sleep_mode:
            await interaction.response.send_message("The bot is in sleep mode. Ticket system is disabled.", ephemeral=True)
            return
            
        ticket_type = select.values[0]
        user = interaction.user
        guild = interaction.guild
        
        ticket_name = f"{ticket_type}-{user.name}"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(SUPPORT_ROLES[ticket_type]): discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        
        category = discord.utils.get(guild.categories, name="Tickets")
        if not category:
            category = await guild.create_category("Tickets")
            
        channel = await guild.create_text_channel(ticket_name, category=category, overwrites=overwrites)
        
        TICKET_DATA[channel.id] = {
            'type': ticket_type,
            'owner': user.id,
            'claimed': False
        }
        
        embed = discord.Embed(
            color=12134451,
            title=f"{ticket_type.capitalize()} Support",
            description="**Hello! Thank you for contacting Melbourne RP Support Team**\n**Please describe your issue.**\n**If you chose the wrong type of ticket, please close this ticket with the 'close' button** \n\nOpening a ticket to troll the support team will result in a week timeout."
        )
        embed.set_author(
            name="Melbourne Roleplay",
            icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1383386514385272864/1421439122316464219/NEW_YORK.png?ex=68d909d7&is=68d7b857&hm=223898c799d7739c9400543b11f5b28e267cab5a14564150ca12056350c0429c&")
        embed.set_footer(
            text="Melbourne Roleplay | Ticket System",
            icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
        )
        
        ticket_view = TicketControlView()
        await channel.send(
            content=f"{user.mention} <@&{SUPPORT_ROLES[ticket_type]}>",
            embed=embed,
            view=ticket_view
        )
        
        await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)

# Ticket control view
class TicketControlView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.green, custom_id="ticket_claim")
    async def claim_button(self, interaction: discord.Interaction, button: Button):
        ticket_data = TICKET_DATA.get(interaction.channel.id)
        if not ticket_data:
            await interaction.response.send_message("This is not a ticket channel!", ephemeral=True)
            return
            
        support_role = interaction.guild.get_role(SUPPORT_ROLES[ticket_data['type']])
        if support_role not in interaction.user.roles:
            await interaction.response.send_message("You don't have permission to claim this ticket!", ephemeral=True)
            return
            
        TICKET_DATA[interaction.channel.id]['claimed'] = True
        await interaction.response.send_message(f"Ticket claimed by {interaction.user.mention}", ephemeral=True)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, custom_id="ticket_close")
    async def close_button(self, interaction: discord.Interaction, button: Button):
        ticket_data = TICKET_DATA.get(interaction.channel.id)
        if not ticket_data:
            await interaction.response.send_message("This is not a ticket channel!", ephemeral=True)
            return
            
        await interaction.response.send_modal(CloseReasonModal())

# Close reason modal
class CloseReasonModal(discord.ui.Modal, title="Close Ticket"):
    reason = discord.ui.TextInput(
        label="Reason for closing",
        style=discord.TextStyle.paragraph,
        placeholder="Enter the reason for closing this ticket...",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        ticket_data = TICKET_DATA.get(interaction.channel.id)
        if not ticket_data:
            await interaction.response.send_message("This is not a ticket channel!", ephemeral=True)
            return
            
        embed = discord.Embed(
            color=12134451,
            title="Ticket | Close Request",
            description=f"{interaction.user.mention} requested to close this ticket.\n\n**Reason**: {self.reason.value}"
        )
        embed.set_author(
            name="Melbourne Roleplay",
            icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1383386514385272864/1421439122316464219/NEW_YORK.png?ex=68d909d7&is=68d7b857&hm=223898c799d7739c9400543b11f5b28e267cab5a14564150ca12056350c0429c&")
        embed.set_footer(
            text="Melbourne Roleplay | Ticket System",
            icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
        )
        
        await interaction.response.send_message(
            content=f"<@!{ticket_data['owner']}>",
            embed=embed,
            view=ConfirmCloseView()
        )

# Confirm close view
class ConfirmCloseView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.red, custom_id="confirm_close")
    async def confirm_close(self, interaction: discord.Interaction, button: Button):
        ticket_data = TICKET_DATA.get(interaction.channel.id)
        if not ticket_data:
            await interaction.response.send_message("This is not a ticket channel!", ephemeral=True)
            return
            
        transcript = []
        async for message in interaction.channel.history(limit=1000):
            transcript.append(f"[{message.created_at}] {message.author}: {message.content}")
        
        transcript_text = "\n".join(reversed(transcript))
        transcript_channel = bot.get_channel(TRANSCRIPT_CHANNEL)
        
        await transcript_channel.send(
            f"Transcript for {interaction.channel.name}",
            file=discord.File(
                fp=io.StringIO(transcript_text),
                filename=f"transcript-{interaction.channel.name}.txt"
            )
        )
        
        del TICKET_DATA[interaction.channel.id]
        await interaction.channel.delete()

# Application review view
class ApplicationReviewView(View):
    def __init__(self, applicant: discord.User, application_type: str):
        super().__init__(timeout=None)
        self.applicant = applicant
        self.application_type = application_type
        self.add_item(Button(label="Accept", style=discord.ButtonStyle.green, custom_id=f"accept_{applicant.id}_{application_type}"))
        self.add_item(Button(label="Deny", style=discord.ButtonStyle.red, custom_id=f"deny_{applicant.id}_{application_type}"))
        self.children[0].callback = self.accept_button
        self.children[1].callback = self.deny_button

    async def accept_button(self, interaction: discord.Interaction):
        if REVIEWER_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("You do not have permission to review applications.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        message = interaction.message
        embed = message.embeds[0]
        embed.color = discord.Color.green()
        embed.add_field(name="Status", value=f"Accepted by {interaction.user.mention}", inline=False)
        await message.edit(embed=embed, view=None)

        try:
            await self.applicant.send(
                embed=discord.Embed(
                    title=f"{self.application_type.replace('_', ' ').title()} Application Accepted",
                    description="Congratulations! Your application has been accepted. Please open a ticket if you did not get roled.",
                    color=discord.Color.green()
                ).set_footer(text="Melbourne Roleplay")
            )
        except discord.Forbidden:
            await interaction.followup.send(f"Could not DM {self.applicant.mention}. Please notify them manually.", ephemeral=True)

        await interaction.followup.send(f"Application for {self.applicant.mention} accepted!", ephemeral=True)

    async def deny_button(self, interaction: discord.Interaction):
        if REVIEWER_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("You do not have permission to review applications.", ephemeral=True)
            return

        await interaction.response.send_modal(DenyReasonModal(self.applicant, self.application_type))

# Deny reason modal
class DenyReasonModal(discord.ui.Modal, title="Deny Application Reason"):
    def __init__(self, applicant: discord.User, application_type: str):
        super().__init__()
        self.applicant = applicant
        self.application_type = application_type
        self.reason = discord.ui.TextInput(
            label="Reason",
            placeholder="Enter the reason for denying the application",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        message = interaction.message
        embed = message.embeds[0]
        embed.color = discord.Color.red()
        embed.add_field(name="Status", value=f"Denied by {interaction.user.mention}\n**Reason**: {self.reason.value}", inline=False)
        await message.edit(embed=embed, view=None)

        try:
            await self.applicant.send(
                embed=discord.Embed(
                    title=f"{self.application_type.replace('_', ' ').title()} Application Denied",
                    description=f"Your application has been denied.\n**Reason**: {self.reason.value}",
                    color=discord.Color.red()
                ).set_footer(text="Melbourne Roleplay")
            )
        except discord.Forbidden:
            await interaction.followup.send(f"Could not DM {self.applicant.mention}. Please notify them manually.", ephemeral=True)

        await interaction.followup.send(f"Application for {self.applicant.mention} denied!", ephemeral=True)

# Application dropdown
class ApplicationSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="ER:LC Moderator", value="erlc_moderator", description="Apply for in-game moderator role"),
            discord.SelectOption(label="Discord Moderator", value="discord_moderator", description="Apply for Discord server moderator role"),
            discord.SelectOption(label="Internal Affairs Team", value="internal_affairs", description="Apply for IA team role"),
            discord.SelectOption(label="DirectorShip", value="directorship", description="Apply for Assistant Director role")
        ]
        super().__init__(placeholder="Select an application type...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_app = self.values[0]
        required_role_id = ROLE_IDS.get(selected_app)
        user = interaction.user

        if bot.sleep_mode:
            await interaction.response.send_message(
                "The bot is in sleep mode. Applications are currently disabled.",
                ephemeral=True
            )
            return

        if APPLICATION_QUESTIONS[selected_app][0] == "[APPLICATION UNAVAILIBLE]":
            await interaction.response.send_message(
                f"The {selected_app.replace('_', ' ').title()} application is currently unavailable.",
                ephemeral=True
            )
            return

        if required_role_id not in [role.id for role in user.roles]:
            await interaction.response.send_message(
                f"You need the required role to apply for {selected_app.replace('_', ' ').title()}!",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Application started! Check your DMs to proceed.",
            ephemeral=True
        )

        try:
            await user.send(f"You've started the application for **{selected_app.replace('_', ' ').title()}**. Please answer the following questions one at a time.")

            answers = []
            for question in APPLICATION_QUESTIONS[selected_app]:
                await user.send(question)
                try:
                    response = await bot.wait_for(
                        'message',
                        check=lambda m: m.author == user and m.channel == user.dm_channel,
                        timeout=300
                    )
                    answers.append((question, response.content))
                except asyncio.TimeoutError:
                    await user.send("You took too long to respond. Application cancelled.")
                    return

            embed = discord.Embed(
                title=f"{selected_app.replace('_', ' ').title()} Application",
                color=0xa8e2ff,
                description=f"Application from {user.mention} ({user.id})"
            )
            for i, (question, answer) in enumerate(answers, 1):
                embed.add_field(name=f"Question {i}: {question}", value=answer, inline=False)
            embed.set_author(
                name="Melbourne Roleplay",
                icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
            )
            embed.set_footer(text="Melbourne Roleplay | Application Submission")

            review_channel = bot.get_channel(REVIEW_CHANNEL_IDS[selected_app])
            if review_channel:
                view = ApplicationReviewView(user, selected_app)
                await review_channel.send(embed=embed, view=view)
                await user.send("Your application has been submitted successfully! You'll hear back soon.")
            else:
                await user.send("Error: Review channel not found. Please contact an admin.")

        except discord.Forbidden:
            await interaction.followup.send("I can't send you DMs. Please enable DMs from server members.", ephemeral=True)

# Application view
class ApplicationView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ApplicationSelect())

# Promote modal
class PromoteModal(discord.ui.Modal, title="Promotion Reason"):
    def __init__(self, member: discord.Member, next_rank: discord.Role, bot):
        super().__init__()
        self.member = member
        self.next_rank = next_rank
        self.bot = bot
        self.reason = discord.ui.TextInput(
            label="Reason",
            placeholder="Enter the reason for promotion",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        current_rank = None
        for role_id in ROLE_HIERARCHY:
            role = interaction.guild.get_role(role_id)
            if role in self.member.roles:
                current_rank = role
                break
        
        if current_rank and self.next_rank:
            await self.member.remove_roles(current_rank)
            await self.member.add_roles(self.next_rank)
            
            promotion_channel = self.bot.get_channel(1421440876089053194)
            embed = discord.Embed(
                title="Staff | Promotion",
                description=(
                    f"Congratulations! The senior high ranking team of **Melbourne Roleplay** "
                    f"has decided to promote you!\n\n"
                    f"**New Rank**: {self.next_rank.mention}\n"
                    f"**Reason**: {self.reason.value}"
                ),
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Issued by {interaction.user}")
            await promotion_channel.send(content=f"{self.member.mention}", embed=embed)
            
            await interaction.followup.send(f"Successfully promoted {self.member.mention} to {self.next_rank.name}!", ephemeral=True)
        else:
            await interaction.followup.send("Error: Could not determine current or next rank.", ephemeral=True)

# Warning modal
class WarningModal(discord.ui.Modal, title="Warning Reason"):
    def __init__(self, member: discord.Member, bot):
        super().__init__()
        self.member = member
        self.bot = bot
        self.reason = discord.ui.TextInput(
            label="Reason",
            placeholder="Enter the reason for the warning",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        warn_role = interaction.guild.get_role(WARNING_ROLES['Warning 1'])
        if warn_role in self.member.roles:
            warn_role = interaction.guild.get_role(WARNING_ROLES['Warning 2'])
            warn_level = "2/2"
        else:
            warn_role = interaction.guild.get_role(WARNING_ROLES['Warning 1'])
            warn_level = "1/2"
        
        await self.member.add_roles(warn_role)
        
        warning_channel = self.bot.get_channel(1421441062907412480)
        embed = discord.Embed(
            title=f"Staff Infraction • Warning ({warn_level})",
            description=f"{self.member.mention} has been warned.\n\n**Reason**: {self.reason.value}",
            color=discord.Color.red()
        )
        embed.set_footer(text=f"Issued by {interaction.user}")
        await warning_channel.send(content=f"{self.member.mention}", embed=embed)
        
        await interaction.followup.send(f"Successfully issued warning {warn_level} to {self.member.mention}!", ephemeral=True)

# Strike modal
class StrikeModal(discord.ui.Modal, title="Strike Reason"):
    def __init__(self, member: discord.Member, bot):
        super().__init__()
        self.member = member
        self.bot = bot
        self.reason = discord.ui.TextInput(
            label="Reason",
            placeholder="Enter the reason for the strike",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        strike_role = interaction.guild.get_role(STRIKE_ROLES['Strike 1'])
        if strike_role in self.member.roles:
            strike_role = interaction.guild.get_role(STRIKE_ROLES['Strike 2'])
            strike_level = "2/2"
        else:
            strike_role = interaction.guild.get_role(STRIKE_ROLES['Strike 1'])
            strike_level = "1/2"
        
        await self.member.add_roles(strike_role)
        
        strike_channel = self.bot.get_channel(1421441062907412480)
        embed = discord.Embed(
            title=f"Staff Infraction • Strike ({strike_level})",
            description=f"{self.member.mention} has been striked.\n\n**Reason**: {self.reason.value}",
            color=discord.Color.red()
        )
        embed.set_footer(text=f"Issued by {interaction.user}")
        await strike_channel.send(content=f"{self.member.mention}", embed=embed)
        
        await interaction.followup.send(f"Successfully issued strike {strike_level} to {self.member.mention}!", ephemeral=True)

# Termination modal
class TerminationModal(discord.ui.Modal, title="Termination Reason"):
    def __init__(self, member: discord.Member, bot):
        super().__init__()
        self.member = member
        self.bot = bot
        self.reason = discord.ui.TextInput(
            label="Reason",
            placeholder="Enter the reason for termination",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        roles_to_remove = [interaction.guild.get_role(role_id) for role_id in ROLE_HIERARCHY if interaction.guild.get_role(role_id) in self.member.roles]
        if roles_to_remove:
            await self.member.remove_roles(*roles_to_remove)
        
        termination_channel = self.bot.get_channel(1421441062907412480)
        embed = discord.Embed(
            title="Staff Termination",
            description=f"{self.member.mention} has been terminated!\n\n**Reason**: {self.reason.value}",
            color=discord.Color.greyple()
        )
        embed.set_footer(text=f"Issued by {interaction.user}")
        await termination_channel.send(content=f"{self.member.mention}", embed=embed)
        
        await interaction.followup.send(f"Successfully terminated {self.member.mention}!", ephemeral=True)

# Blacklist modal
class BlacklistModal(discord.ui.Modal, title="Blacklist Reason"):
    def __init__(self, member: discord.Member, bot):
        super().__init__()
        self.member = member
        self.bot = bot
        self.reason = discord.ui.TextInput(
            label="Reason",
            placeholder="Enter the reason for blacklisting",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        roles_to_remove = [interaction.guild.get_role(role_id) for role_id in ROLE_HIERARCHY if interaction.guild.get_role(role_id) in self.member.roles]
        if roles_to_remove:
            await self.member.remove_roles(*roles_to_remove)
        
        blacklist_role = interaction.guild.get_role(BLACKLIST_ROLE)
        await self.member.add_roles(blacklist_role)
        
        blacklist_channel = self.bot.get_channel(1421441062907412480)
        embed = discord.Embed(
            title="Staff Blacklist",
            description=f"{self.member.mention} has been blacklisted from staff!\n\n**Reason**: {self.reason.value}",
            color=discord.Color(0x000000)
        )
        embed.set_footer(text=f"Issued by {interaction.user}")
        await blacklist_channel.send(content=f"{self.member.mention}", embed=embed)
        
        await interaction.followup.send(f"Successfully blacklisted {self.member.mention}!", ephemeral=True)

# Re-Training modal
class ReTrainingModal(discord.ui.Modal, title="Re-Training Reason"):
    def __init__(self, member: discord.Member, bot):
        super().__init__()
        self.member = member
        self.bot = bot
        self.reason = discord.ui.TextInput(
            label="Reason",
            placeholder="Enter the reason for Re-Training",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        roles_to_remove = [interaction.guild.get_role(role_id) for role_id in ROLE_HIERARCHY if interaction.guild.get_role(role_id) in self.member.roles]
        if roles_to_remove:
            await self.member.remove_roles(*roles_to_remove)
        
        at_role = interaction.guild.get_role(AT_ROLE)
        await self.member.add_roles(at_role)
        
        retraining_channel = self.bot.get_channel(1410606498559557682)
        embed = discord.Embed(
            title="Staff | Re-Training",
            description=f"{self.member.mention} has been issued a re-training.\n\n**Reason**: {self.reason.value}",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Issued by {interaction.user}")
        await retraining_channel.send(content=f"{self.member.mention}", embed=embed)
        
        await interaction.followup.send(f"Successfully issued re-training for {self.member.mention}!", ephemeral=True)

# Staff panel view
class StaffPanelView(View):
    def __init__(self, member: discord.Member, next_rank: discord.Role, bot):
        super().__init__(timeout=None)
        self.member = member
        self.next_rank = next_rank
        self.bot = bot
        
        if next_rank:
            self.add_item(Button(label="Promote", style=discord.ButtonStyle.green, custom_id=f"promote_{member.id}"))
            self.children[-1].callback = self.promote_button
        self.add_item(Button(label="Warning", style=discord.ButtonStyle.red, custom_id=f"warn_{member.id}"))
        self.add_item(Button(label="Strike", style=discord.ButtonStyle.red, custom_id=f"strike_{member.id}"))
        self.add_item(Button(label="Termination", style=discord.ButtonStyle.grey, custom_id=f"terminate_{member.id}"))
        self.add_item(Button(label="Blacklist", style=discord.ButtonStyle.grey, custom_id=f"blacklist_{member.id}"))
        self.add_item(Button(label="Re-Training", style=discord.ButtonStyle.green, custom_id=f"retraining_{member.id}"))
        self.children[-5].callback = self.warning_button
        self.children[-4].callback = self.strike_button
        self.children[-3].callback = self.termination_button
        self.children[-2].callback = self.blacklist_button
        self.children[-1].callback = self.retraining_button

    async def promote_button(self, interaction: discord.Interaction):
        user_highest_role = max((role for role in interaction.user.roles if role.id in ROLE_HIERARCHY), 
                               key=lambda r: ROLE_HIERARCHY.index(r.id), default=None)
        member_highest_role = max((role for role in self.member.roles if role.id in ROLE_HIERARCHY), 
                                 key=lambda r: ROLE_HIERARCHY.index(r.id), default=None)
        
        if not user_highest_role or not member_highest_role:
            await interaction.response.send_message("Error: User or member does not have a rank in the hierarchy.", ephemeral=True)
            return
        
        if ROLE_HIERARCHY.index(user_highest_role.id) <= ROLE_HIERARCHY.index(member_highest_role.id):
            await interaction.response.send_message("You do not have permission to promote this member.", ephemeral=True)
            return
        
        await interaction.response.send_modal(PromoteModal(self.member, self.next_rank, self.bot))

    async def warning_button(self, interaction: discord.Interaction):
        user_highest_role = max((role for role in interaction.user.roles if role.id in ROLE_HIERARCHY), 
                               key=lambda r: ROLE_HIERARCHY.index(r.id), default=None)
        member_highest_role = max((role for role in self.member.roles if role.id in ROLE_HIERARCHY), 
                                 key=lambda r: ROLE_HIERARCHY.index(r.id), default=None)
        
        if not user_highest_role or not member_highest_role:
            await interaction.response.send_message("Error: User or member does not have a rank in the hierarchy.", ephemeral=True)
            return
        
        if ROLE_HIERARCHY.index(user_highest_role.id) <= ROLE_HIERARCHY.index(member_highest_role.id):
            await interaction.response.send_message("You do not have permission to warn this member.", ephemeral=True)
            return
        
        await interaction.response.send_modal(WarningModal(self.member, self.bot))

    async def strike_button(self, interaction: discord.Interaction):
        user_highest_role = max((role for role in interaction.user.roles if role.id in ROLE_HIERARCHY), 
                               key=lambda r: ROLE_HIERARCHY.index(r.id), default=None)
        member_highest_role = max((role for role in self.member.roles if role.id in ROLE_HIERARCHY), 
                                 key=lambda r: ROLE_HIERARCHY.index(r.id), default=None)
        
        if not user_highest_role or not member_highest_role:
            await interaction.response.send_message("Error: User or member does not have a rank in the hierarchy.", ephemeral=True)
            return
        
        if ROLE_HIERARCHY.index(user_highest_role.id) <= ROLE_HIERARCHY.index(member_highest_role.id):
            await interaction.response.send_message("You do not have permission to strike this member.", ephemeral=True)
            return
        
        await interaction.response.send_modal(StrikeModal(self.member, self.bot))

    async def termination_button(self, interaction: discord.Interaction):
        user_highest_role = max((role for role in interaction.user.roles if role.id in ROLE_HIERARCHY), 
                               key=lambda r: ROLE_HIERARCHY.index(r.id), default=None)
        member_highest_role = max((role for role in self.member.roles if role.id in ROLE_HIERARCHY), 
                                 key=lambda r: ROLE_HIERARCHY.index(r.id), default=None)
        
        if not user_highest_role or not member_highest_role:
            await interaction.response.send_message("Error: User or member does not have a rank in the hierarchy.", ephemeral=True)
            return
        
        if ROLE_HIERARCHY.index(user_highest_role.id) <= ROLE_HIERARCHY.index(member_highest_role.id):
            await interaction.response.send_message("You do not have permission to terminate this member.", ephemeral=True)
            return
        
        await interaction.response.send_modal(TerminationModal(self.member, self.bot))

    async def blacklist_button(self, interaction: discord.Interaction):
        user_highest_role = max((role for role in interaction.user.roles if role.id in ROLE_HIERARCHY), 
                               key=lambda r: ROLE_HIERARCHY.index(r.id), default=None)
        member_highest_role = max((role for role in self.member.roles if role.id in ROLE_HIERARCHY), 
                                 key=lambda r: ROLE_HIERARCHY.index(r.id), default=None)
        
        if not user_highest_role or not member_highest_role:
            await interaction.response.send_message("Error: User or member does not have a rank in the hierarchy.", ephemeral=True)
            return
        
        if ROLE_HIERARCHY.index(user_highest_role.id) <= ROLE_HIERARCHY.index(member_highest_role.id):
            await interaction.response.send_message("You do not have permission to blacklist this member.", ephemeral=True)
            return
        
        await interaction.response.send_modal(BlacklistModal(self.member, self.bot))

    async def retraining_button(self, interaction: discord.Interaction):
        user_highest_role = max((role for role in interaction.user.roles if role.id in ROLE_HIERARCHY), 
                               key=lambda r: ROLE_HIERARCHY.index(r.id), default=None)
        member_highest_role = max((role for role in self.member.roles if role.id in ROLE_HIERARCHY), 
                                 key=lambda r: ROLE_HIERARCHY.index(r.id), default=None)
        
        if not user_highest_role or not member_highest_role:
            await interaction.response.send_message("Error: User or member does not have a rank in the hierarchy.", ephemeral=True)
            return
        
        if ROLE_HIERARCHY.index(user_highest_role.id) <= ROLE_HIERARCHY.index(member_highest_role.id):
            await interaction.response.send_message("You do not have permission to issue a re-training for this member.", ephemeral=True)
            return
        
        await interaction.response.send_modal(ReTrainingModal(self.member, self.bot))

# Role request view
class RoleRequestView(View):
    def __init__(self, requester: discord.User, role: str, action: str):
        super().__init__(timeout=None)
        self.requester = requester
        self.role = role
        self.action = action
        self.add_item(Button(label="Accept", style=discord.ButtonStyle.green, custom_id=f"role_accept_{requester.id}_{role}_{action}"))
        self.add_item(Button(label="Deny", style=discord.ButtonStyle.red, custom_id=f"role_deny_{requester.id}_{role}_{action}"))
        self.children[0].callback = self.accept_button
        self.children[1].callback = self.deny_button

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only allow vavax989 to use the buttons
        vavax_id = 1038522974988411000
        if interaction.user.id != vavax_id:
            await interaction.response.send_message("Only vavax989 can use these buttons!", ephemeral=True)
            return False
        return True

    async def accept_button(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        message = interaction.message
        embed = message.embeds[0]
        embed.color = discord.Color.green()
        embed.add_field(name="Status", value=f"Accepted by {interaction.user.mention}", inline=False)
        await message.edit(embed=embed, view=None)

        try:
            await self.requester.send(
                embed=discord.Embed(
                    title="Role Request Accepted",
                    description=f"Your request for the role '{self.role}' ({self.action}) has been accepted.",
                    color=discord.Color.green()
                ).set_author(
                    name="Melbourne Roleplay",
                    icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
                ).set_footer(
                    text="Melbourne Roleplay",
                    icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
                )
            )
        except discord.Forbidden:
            await interaction.followup.send(f"Could not DM {self.requester.mention}. Please notify them manually.", ephemeral=True)

        await interaction.followup.send(f"Role request for {self.requester.mention} accepted!", ephemeral=True)

    async def deny_button(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        message = interaction.message
        embed = message.embeds[0]
        embed.color = discord.Color.red()
        embed.add_field(name="Status", value=f"Denied by {interaction.user.mention}", inline=False)
        await message.edit(embed=embed, view=None)

        try:
            await self.requester.send(
                embed=discord.Embed(
                    title="Role Request Denied",
                    description=f"Your request for the role '{self.role}' ({self.action}) has been denied.",
                    color=discord.Color.red()
                ).set_author(
                    name="Melbourne Roleplay",
                    icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
                ).set_footer(
                    text="Melbourne Roleplay",
                    icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
                )
            )
        except discord.Forbidden:
            await interaction.followup.send(f"Could not DM {self.requester.mention}. Please notify them manually.", ephemeral=True)

        await interaction.followup.send(f"Role request for {self.requester.mention} denied!", ephemeral=True)

# Cog loader
async def load_extensions():
    global loaded_cogs
    print("Cogs Loader:")
    cogs = [
        "jishaku",
        "globalban",
        "sessions",
        "robloxcmds",
        "welcome",
        "callsigns",
        "jsoncheck"
    ]
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"   Cogs.{cog.split('.')[-1]}")
            loaded_cogs.append(cog.split(".")[-1])
        except Exception as e:
            print(f"Failed to load Cogs.{cog.split('.')[-1]}: {e}")

# Check for allowed role
def has_allowed_role():
    async def predicate(ctx):
        if bot.sleep_mode and ctx.command.name != 'start':
            return False
        role = discord.utils.get(ctx.author.roles, id=ALLOWED_ROLE_ID)
        return role is not None
    return commands.check(predicate)

# Check for say command role
def has_say_role():
    async def predicate(ctx):
        if bot.sleep_mode:
            return False
        role = discord.utils.get(ctx.author.roles, id=SAY_ROLE_ID)
        return role is not None
    return commands.check(predicate)

# Check for help request role
def has_help_request_role():
    async def predicate(ctx):
        if bot.sleep_mode:
            return False
        role = discord.utils.get(ctx.author.roles, id=HELP_REQUEST_ROLE_ID)
        return role is not None
    return commands.check(predicate)

# Check for ticket command permissions
def has_support_role():
    async def predicate(ctx):
        if bot.sleep_mode:
            return False
        return any(role.id in SUPPORT_ROLES.values() for role in ctx.author.roles)
    return commands.check(predicate)

# Check for IA role
def has_ia_role():
    async def predicate(ctx):
        if bot.sleep_mode:
            return False
        role = discord.utils.get(ctx.author.roles, id=IA_ROLE)
        return role is not None
    return commands.check(predicate)

# Unauthorized embed
def unauthorized_embed():
    embed = discord.Embed(
        title="UNAUTHORIZED",
        description="You are not allowed to execute this command.",
        color=discord.Color.red()
    )
    return embed

def parse_time(time_str):
    # Parse time like '1h', '30m', etc.
    match = re.match(r'^(\d+)([hm])$', time_str)
    if not match:
        raise ValueError("Invalid time format. Use '1h', '30m', etc.")
    value, unit = int(match.group(1)), match.group(2)
    if unit == 'h':
        return value * 3600  # Convert hours to seconds
    elif unit == 'm':
        return value * 60 
        
# Mass update command
@bot.command()
@has_allowed_role()
async def massupdate(ctx):
    if bot.sleep_mode:
        await ctx.send(embed=discord.Embed(
            title="ERROR",
            description="Bot is in sleep mode.",
            color=discord.Color.red()
        ))
        return

    try:
        with open('embeds.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        await ctx.send(embed=discord.Embed(
            title="ERROR",
            description="embeds.json file not found.",
            color=discord.Color.red()
        ))
        return
    except json.JSONDecodeError:
        await ctx.send(embed=discord.Embed(
            title="ERROR",
            description="Invalid JSON format in embeds.json.",
            color=discord.Color.red()
        ))
        return

    updated_channels = []
    errors = []

    for channel_id, config in data.get('channels', {}).items():
        channel = bot.get_channel(int(channel_id))
        if not channel:
            errors.append(f"Channel {channel_id} not found.")
            continue

        # Create embed
        embed_data = config.get('embed', {})
        embed = discord.Embed(
            title=embed_data.get('title'),
            description=embed_data.get('description'),
            color=embed_data.get('color', 0x00ff00)
        )

        # Set author if present
        if 'author' in embed_data:
            embed.set_author(
                name=embed_data['author'].get('name'),
                url=embed_data['author'].get('url'),
                icon_url=embed_data['author'].get('icon_url')
            )

        # Set footer if present
        if 'footer' in embed_data:
            embed.set_footer(
                text=embed_data['footer'].get('text'),
                icon_url=embed_data['footer'].get('icon_url')
            )

        # Set image if present
        if 'image' in embed_data:
            embed.set_image(url=embed_data['image'].get('url'))

        # Set thumbnail if present
        if 'thumbnail' in embed_data:
            embed.set_thumbnail(url=embed_data['thumbnail'].get('url'))

        # Add fields if present
        for field in embed_data.get('fields', []):
            embed.add_field(
                name=field.get('name', 'Field'),
                value=field.get('value', 'Value'),
                inline=field.get('inline', False)
            )

        # Get view if specified
        view = None
        view_name = config.get('view')
        if view_name and view_name in VIEW_MAPPING:
            view = VIEW_MAPPING[view_name]()

        # Purge channel and send new embed
        try:
            async for message in channel.history(limit=100):
                if not message.pinned:
                    await message.delete()
            await channel.send(embed=embed, view=view)
            updated_channels.append(channel.mention)
        except discord.Forbidden:
            errors.append(f"Missing permissions in {channel.mention}")
        except Exception as e:
            errors.append(f"Error in {channel.mention}: {str(e)}")

    # Send response
    embed = discord.Embed(
        title="Mass Update Complete",
        color=discord.Color.green()
    )
    if updated_channels:
        embed.add_field(
            name="Updated Channels",
            value="\n".join(updated_channels),
            inline=False
        )
    if errors:
        embed.add_field(
            name="Errors",
            value="\n".join(errors),
            inline=False
        )
    await ctx.send(embed=embed)

@bot.command(name="training", description="Announce a training session")
@has_allowed_role()
async def training(ctx: commands.Context, co_host: discord.Member = None):
    if bot.sleep_mode:
        await ctx.send(embed=unauthorized_embed())
        return
    
    # Role ID to ping
    role_id = 1402933851436879932
    
    # Create announcement embed
    embed = discord.Embed(
        title="Training • Announcement",
        color=discord.Color.from_str("#B92833")  # Pink color
    )
    embed.add_field(name="Host", value=ctx.author.mention, inline=True)
    embed.add_field(name="Co-Host", value=co_host.mention if co_host else "None", inline=True)
    embed.add_field(name="Join Code", value="SFRole", inline=True)
    embed.add_field(name="Location", value="Sheriff • Briefing Room", inline=True)
    embed.set_footer(
        text="Melbourne Roleplay",
        icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
    )
    embed.set_author(
        text="Melbourne Roleplay",
        icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
    )
    embed.set_image(url="https://cdn.discordapp.com/attachments/1383386514385272864/1421439122316464219/NEW_YORK.png?ex=68d909d7&is=68d7b857&hm=223898c799d7739c9400543b11f5b28e267cab5a14564150ca12056350c0429c&")
    
    # Send embed to the command's channel and ping role
    try:
        message = await ctx.channel.send(content=f"<@&{role_id}>", embed=embed)
        await message.add_reaction("✅")
        await ctx.send(embed=discord.Embed(
            title="Training Announcement Sent",
            description=f"Announcement sent in {ctx.channel.mention}!",
            color=discord.Color.green()
        ))
    except discord.Forbidden:
        await ctx.send(embed=discord.Embed(
            title="ERROR",
            description="Bot lacks permissions to send messages or add reactions in this channel.",
            color=discord.Color.red()
        ))
    except Exception as e:
        await ctx.send(embed=discord.Embed(
            title="ERROR",
            description=f"Failed to send announcement: {str(e)}",
            color=discord.Color.red()
        ))
               
# Role request slash command
@bot.tree.command(name="role_request", description="Submit a role request to vavax989")
@app_commands.describe(
    role="The role you are requesting",
    action="Whether to add or remove the role",
    reason="Reason for the role request"
)
@app_commands.choices(action=[
    app_commands.Choice(name="Add", value="Add"),
    app_commands.Choice(name="Remove", value="Remove")
])
async def role_request(interaction: discord.Interaction, role: str, action: str, reason: str):
    if bot.sleep_mode:
        embed = unauthorized_embed()
        embed.description = "Bot is in sleep mode."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Check if the user has the allowed role
    if ALLOWED_ROLE_ID not in [r.id for r in interaction.user.roles]:
        await interaction.response.send_message(embed=unauthorized_embed(), ephemeral=True)
        return

    # IDs
    vavax_id = 1038522974988411000  # vavax989 user ID
    channel_id = 1421443061845852220  # Role request channel ID

    # Get the vavax989 user and the channel
    try:
        vavax_user = await bot.fetch_user(vavax_id)
        channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
    except discord.NotFound:
        await interaction.response.send_message("Error: Could not find vavax989 or the role request channel.", ephemeral=True)
        return

    # DM Embed
    dm_embed = discord.Embed(
        title="New Role Request!",
        description="Please check the role request channel.",
        color=11020918
    )
    dm_embed.set_author(
        name="Melbourne Roleplay",
        icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=51"
    )
    dm_embed.set_footer(
        name="Melbourne Roleplay",
        icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=51"
    )

    # Send DM to vavax989
    try:
        await vavax_user.send(embed=dm_embed)
    except discord.Forbidden:
        await interaction.response.send_message("Failed to DM vavax989. They may have DMs disabled.", ephemeral=True)
        return

    # Channel Embed
    channel_embed = discord.Embed(
        title="Role Request",
        color=11020918
    )
    channel_embed.add_field(name="User", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
    channel_embed.add_field(name="Role", value=role, inline=False)
    channel_embed.add_field(name="Reason", value=reason, inline=False)
    channel_embed.add_field(name="Type", value=action, inline=False)
    channel_embed.set_author(
        name="Melbourne Roleplay",
        icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
    )
    channel_embed.set_footer(
        name="Melbourne Roleplay",
        icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=51"
    )

    # Send the embed with buttons to the channel
    await channel.send(content=f"<@{vavax_id}> {interaction.user.mention}", embed=channel_embed, view=RoleRequestView(interaction.user, role, action))

    # Respond to the user
    await interaction.response.send_message("Your role request has been submitted!", ephemeral=True)

# Bot ready event
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.change_presence(
        status=discord.Status.idle,
        activity=discord.Activity(type=discord.ActivityType.watching, name="Waiting for SHR to initialize..")
    )
    await load_extensions()
    print('Cogs loaded successfully')
    
    # Send application panel
    channel = bot.get_channel(APPLICATION_PANEL_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            color=12134451,
            title="Applications",
            description=(
                "**Informations** \n\n"
                "- ER:LC Moderator : \nIf your application is accepted, you will have to moderate the in-game server. \n\n"
                "- Discord Moderator : \nIf your application is accepted, you will have to moderate all the channels and members in our discord server. \n\n"
                "- Internals Affairs Team : \nIf your application is accepted, you will have to review ER:LC and Discord moderators, IA cases, and you will have to issues infractions to moderators breaking rules. \n\n"
                "- DirectorShip Application\nIf your application is accepted, you will become Assistant Director, it means, that you will have to manage the servers and ever staff teams. **Restricted to Management Team *WHEN* spots are free.** \n\n"
                "**Requirements**\n\n"
                "You must be at least 13 years old. \n"
                "You must use common-sense during your application. \n"
                "You must use SPaG at all times. \n"
                "You must be active."
            )
        )
        embed.set_author(
            name="Melbourne Roleplay",
            icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1383386514385272864/1421439122316464219/NEW_YORK.png?ex=68d909d7&is=68d7b857&hm=223898c799d7739c9400543b11f5b28e267cab5a14564150ca12056350c0429c&")
        embed.set_footer(
            text="Melbourne Roleplay | Application System",
            icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
        )
        
        view = ApplicationView()
        await channel.send(embed=embed, view=view)
        print("Application panel sent!")
    
    # Send ticket panel
    ticket_channel = bot.get_channel(TICKET_PANEL_CHANNEL)
    if ticket_channel:
        await ticket_channel.purge(limit=100)
        embed = discord.Embed(
            color=12134451,
            title="Support",
            description=(
                "**Informations** \n\n"
                "- General Support : \n-> Questions\n-> Issues\n\n"
                "- Internals Affairs Support : \n-> Report ER:LC Moderators & Directive Team\n-> Report Discord Moderators\n-> Appeal an infraction/moderation\n\n"
                "- Management Support : \n-> High Ranking Issues\n-> Redeem giveaways, prizes.. \n-> Partnerships\n\n"
                "- Senior High Rank Support : \n-> Important Issues\n-> Departments Requests\n-> Blacklists Requests\n-> Report an Internals Affairs Member\n\n"
                "Opening a ticket to troll the support team will result in a week timeout."
            )
        )
        embed.set_author(
            name="Melbourne Roleplay",
            icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1383386514385272864/1421439122316464219/NEW_YORK.png?ex=68d909d7&is=68d7b857&hm=223898c799d7739c9400543b11f5b28e267cab5a14564150ca12056350c0429c&")
        embed.set_footer(
            text="Melbourne Roleplay | Ticket System",
            icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
        )
        
        await ticket_channel.send(embed=embed, view=TicketView())
        print("Ticket panel sent!")
    
    await bot.tree.sync()
    print("Slash commands synced")

# Stop command
@bot.command()
@has_allowed_role()
async def stop(ctx):
    bot.sleep_mode = True
    embed = discord.Embed(
        title="[BOT] Sleep Mode",
        description=f"The bot has been put in sleep mode by {ctx.author.mention}\n\n**Disabled cogs:**\n" + "\n".join(loaded_cogs),
        color=discord.Color.blue()
    )
    embed.set_footer(text="Melbourne Roleplay")
    await bot.change_presence(
        status=discord.Status.idle,
        activity=discord.Activity(type=discord.ActivityType.watching, name="Waiting for SHR to initialize..")
    )
    for cog in loaded_cogs:
        if cog != 'jishaku':
            await bot.unload_extension(f'cogs.{cog}')
    loaded_cogs.clear()
    loaded_cogs.append('jishaku')
    await ctx.send(embed=embed)

# Start command
@bot.command()
@has_allowed_role()
async def start(ctx):
    bot.sleep_mode = False
    embed = discord.Embed(
        title="[BOT] Started",
        description=f"The bot has been started by {ctx.author.mention}\n\n**Enabled cogs:**\n" + "\n".join(loaded_cogs),
        color=discord.Color.green()
    )
    embed.set_footer(text="Melbourne Roleplay")
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Activity(type=discord.ActivityType.watching, name="Melbourne Roleplay")
    )
    await load_extensions()
    await ctx.send(embed=embed)

# Purge command
@bot.command()
@has_allowed_role()
async def purge(ctx, channel_id: int):
    channel = bot.get_channel(channel_id)
    if not channel:
        await ctx.send("Invalid channel ID")
        return
    async for message in channel.history(limit=None):
        if not message.pinned:
            await message.delete()
    await ctx.send(f"Cleared non-pinned messages in {channel.mention}")

# Servers command
@bot.command()
@has_allowed_role()
async def servers(ctx):
    embed = discord.Embed(
        title="[BOT] Servers",
        description="\n".join([f"{guild.name} - {guild.id}" for guild in bot.guilds]),
        color=discord.Color.blue()
    )
    embed.set_footer(text="Melbourne Roleplay")
    await ctx.send(embed=embed)

# Nick command
@bot.command()
@has_allowed_role()
async def nick(ctx, member: discord.Member, *, new_nick):
    try:
        await member.edit(nick=new_nick)
        await ctx.send(f"Changed nickname for {member.mention} to {new_nick}")
    except discord.Forbidden:
        await ctx.send("I don't have permission to change that user's nickname")

# Say command
@bot.command()
@has_say_role()
async def say(ctx, *, message):
    await ctx.message.delete()
    await ctx.send(message)

# Requesthelp command
@bot.command()
@has_help_request_role()
async def requesthelp(ctx, *, reason: str):
    if not reason:
        await ctx.send(embed=discord.Embed(
            title="ERROR",
            description="Please provide a reason for the help request.",
            color=discord.Color.red()
        ))
        return
    
    help_channel = bot.get_channel(1421443989139361802)
    role = discord.utils.get(ctx.guild.roles, id=HELP_REQUEST_ROLE_ID)
    
    embed = discord.Embed(
        title="Staff Help Request",
        description=f"{ctx.author.mention} has requested in-game assistance with *moderating* the server. Please clock in!",
        color=discord.Color.blue()
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text="Melbourne Roleplay")
    
    await help_channel.send(content=f"{role.mention}", embed=embed)
    await ctx.send(embed=discord.Embed(
        title="Help Request Sent",
        description="Your request for assistance has been sent to the staff team.",
        color=discord.Color.green()
    ))

# Ticket commands
@bot.command()
@has_support_role()
async def closerequest(ctx, *, reason="No reason provided"):
    ticket_data = TICKET_DATA.get(ctx.channel.id)
    if not ticket_data:
        await ctx.send(embed=discord.Embed(
            title="ERROR",
            description="This is not a ticket channel!",
            color=discord.Color.red()
        ))
        return
        
    embed = discord.Embed(
        color=12134451,
        title="Ticket | Close Request",
        description=f"{ctx.author.mention} requested to close this ticket.\n\n**Reason**: {reason}"
    )
    embed.set_author(
        name="Melbourne Roleplay",
        icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
    )
    embed.set_image(url="https://cdn.discordapp.com/attachments/1383386514385272864/1421439122316464219/NEW_YORK.png?ex=68d909d7&is=68d7b857&hm=223898c799d7739c9400543b11f5b28e267cab5a14564150ca12056350c0429c&")
    embed.set_footer(
        text="Melbourne Roleplay | Ticket System",
        icon_url="https://cdn.discordapp.com/icons/1383386513533964349/202921f0cb5e1382522e41b5948f19c5.png?size=512"
    )
    
    await ctx.send(
        content=f"<@!{ticket_data['owner']}>",
        embed=embed,
        view=ConfirmCloseView()
    )

@bot.command()
@has_support_role()
async def add(ctx, member: discord.Member):
    ticket_data = TICKET_DATA.get(ctx.channel.id)
    if not ticket_data:
        await ctx.send(embed=discord.Embed(
            title="ERROR",
            description="This is not a ticket channel!",
            color=discord.Color.red()
        ))
        return
        
    await ctx.channel.set_permissions(member, view_channel=True, send_messages=True)
    await ctx.send(f"{member.mention} has been added to the ticket.")

@bot.command()
@has_support_role()
async def remove(ctx, member: discord.Member):
    ticket_data = TICKET_DATA.get(ctx.channel.id)
    if not ticket_data:
        await ctx.send(embed=discord.Embed(
            title="ERROR",
            description="This is not a ticket channel!",
            color=discord.Color.red()
        ))
        return
        
    await ctx.channel.set_permissions(member, view_channel=False, send_messages=False)
    await ctx.send(f"{member.mention} has been removed from the ticket.")

# Staffpanel slash command
@bot.tree.command(name="staffpanel", description="Display a staff member's panel")
@app_commands.describe(member="The staff member to display the panel for")
async def staffpanel(interaction: discord.Interaction, member: discord.Member):
    if bot.sleep_mode:
        embed = unauthorized_embed()
        embed.description = "Bot is in sleep mode."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    authorized = any(role.id == ALLOWED_ROLE_ID for role in interaction.user.roles)
    if not authorized:
        await interaction.response.send_message(embed=unauthorized_embed(), ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    current_rank = None
    current_rank_index = -1
    for i, role_id in enumerate(ROLE_HIERARCHY):
        role = interaction.guild.get_role(role_id)
        if role in member.roles:
            current_rank = role
            current_rank_index = i
            break
    
    previous_rank = interaction.guild.get_role(ROLE_HIERARCHY[current_rank_index - 1]) if current_rank_index > 0 else None
    next_rank = None if current_rank_index == len(ROLE_HIERARCHY) - 1 else interaction.guild.get_role(ROLE_HIERARCHY[current_rank_index + 1])
    
    warnings = [name for name, role_id in WARNING_ROLES.items() if interaction.guild.get_role(role_id) in member.roles]
    strikes = [name for name, role_id in STRIKE_ROLES.items() if interaction.guild.get_role(role_id) in member.roles]
    
    embed = discord.Embed(
        title=f"Welcome to {member.mention}'s Panel",
        color=discord.Color.blue()
    )
    embed.add_field(name="Current Rank", value=current_rank.mention if current_rank else "None", inline=False)
    embed.add_field(name="Previous Rank", value=previous_rank.mention if previous_rank else "None", inline=False)
    embed.add_field(name="Next Rank", value=next_rank.mention if next_rank else "None", inline=False)
    embed.add_field(name="Active Warnings", value=", ".join(warnings) if warnings else "None", inline=False)
    embed.add_field(name="Active Strikes", value=", ".join(strikes) if strikes else "None", inline=False)
    
    view = StaffPanelView(member, next_rank, bot)
    
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

# Internal Affairs commands
@bot.tree.command(name="ia_case", description="Create an Internal Affairs case embed and thread")
@app_commands.describe(
    number="Case number",
    reporter="User reporting the case (mention)",
    reported="User being reported (mention)",
    reason="Reason for the case"
)
async def ia_case(interaction: discord.Interaction, number: int, reporter: discord.User, reported: discord.User, reason: str):
    if bot.sleep_mode:
        embed = unauthorized_embed()
        embed.description = "Bot is in sleep mode."
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if IA_ROLE not in [role.id for role in interaction.user.roles]:
        await interaction.response.send_message(embed=unauthorized_embed(), ephemeral=True)
        return

    # Define the target channel
    channel = bot.get_channel(1421444258380124160)
    if not channel:
        await interaction.response.send_message("Channel not found!", ephemeral=True)
        return

    # Create the case embed
    case_embed = discord.Embed(
        title=f"Internal Affairs Case | #{number}",
        color=discord.Color.green()
    )
    case_embed.add_field(name="Reporter", value=reporter.mention, inline=False)
    case_embed.add_field(name="Reported", value=reported.mention, inline=False)
    case_embed.add_field(name="Reason", value=reason, inline=False)
    case_embed.set_footer(text="Melbourne Roleplay")

    # Send the case embed and create a thread
    case_message = await channel.send(embed=case_embed)
    thread = await case_message.create_thread(
        name=f"Internal Affairs Case | #{number}",
        auto_archive_duration=10080  # 7 days
    )

    # Create the punishment poll embed
    poll_embed = discord.Embed(
        title="Punishment Poll",
        description=(
            "1️⃣ Verbal Warning\n"
            "2️⃣ Warning\n"
            "3️⃣ Strike\n"
            "4️⃣ Suspension\n"
            "5️⃣ Demotion\n"
            "6️⃣ Re-Training\n"
            "7️⃣ Blacklist"
        ),
        color=discord.Color.blue()
    )
    poll_embed.set_footer(text="Melbourne Roleplay")

    # Send the poll embed in the thread and add reactions
    poll_message = await thread.send(embed=poll_embed)
    reactions = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣']
    for emoji in reactions:
        await poll_message.add_reaction(emoji)

    await interaction.response.send_message(f"Case #{number} created in {channel.mention} with thread {thread.mention}", ephemeral=True)

@bot.command(name="caseclose", description="Close and lock the case thread and update embed color to red")
@has_ia_role()
async def case_close(ctx: commands.Context):
    if bot.sleep_mode:
        await ctx.send(embed=unauthorized_embed())
        return

    # Ensure the command is run in a thread
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.send(embed=discord.Embed(
            title="ERROR",
            description="This command can only be run in a thread!",
            color=discord.Color.red()
        ), delete_after=5)
        return

    thread = ctx.channel
    # Fetch the parent message (the embed) from the thread's parent channel
    try:
        parent_message = await thread.parent.fetch_message(thread.id)
    except discord.NotFound:
        await ctx.send(embed=discord.Embed(
            title="ERROR",
            description="Parent message not found!",
            color=discord.Color.red()
        ), delete_after=5)
        return

    # Check if the message has an embed
    if not parent_message.embeds:
        await ctx.send(embed=discord.Embed(
            title="ERROR",
            description="No embed found in the parent message!",
            color=discord.Color.red()
        ), delete_after=5)
        return

    # Get the embed and modify its color
    embed = parent_message.embeds[0]
    embed.color = discord.Color.red()

    # Update the original message with the new embed
    await parent_message.edit(embed=embed)

    # Close and lock the thread
    await thread.edit(archived=True, locked=True)

    await ctx.send("Case closed and thread locked.", delete_after=5)

@bot.command(name="endpoll", description="End the punishment poll and announce the result")
@has_ia_role()
async def end_poll(ctx: commands.Context):
    if bot.sleep_mode:
        await ctx.send(embed=unauthorized_embed())
        return

    # Ensure the command is run in a thread
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.send(embed=discord.Embed(
            title="ERROR",
            description="This command can only be run in a thread!",
            color=discord.Color.red()
        ), delete_after=5)
        return

    # Ensure the command is a reply to a message
    if not ctx.message.reference:
        await ctx.send(embed=discord.Embed(
            title="ERROR",
            description="Please reply to the poll message to use this command!",
            color=discord.Color.red()
        ), delete_after=5)
        return

    # Fetch the replied-to message
    try:
        poll_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
    except discord.NotFound:
        await ctx.send(embed=discord.Embed(
            title="ERROR",
            description="Poll message not found!",
            color=discord.Color.red()
        ), delete_after=5)
        return

    # Check if the message has an embed
    if not poll_message.embeds:
        await ctx.send(embed=discord.Embed(
            title="ERROR",
            description="Replied message is not a poll embed!",
            color=discord.Color.red()
        ), delete_after=5)
        return

    # Define punishment mapping
    punishment_map = {
        '1️⃣': 'Verbal Warning',
        '2️⃣': 'Warning',
        '3️⃣': 'Strike',
        '4️⃣': 'Suspension',
        '5️⃣': 'Demotion',
        '6️⃣': 'Re-Training',
        '7️⃣': 'Blacklist'
    }

    # Count reactions
    max_reactions = 0
    winning_punishment = None
    for reaction in poll_message.reactions:
        if reaction.emoji in punishment_map:
            count = reaction.count - 1  # Subtract 1 to exclude bot's own reaction
            if count > max_reactions:
                max_reactions = count
                winning_punishment = punishment_map[reaction.emoji]
            elif count == max_reactions and count > 0:
                winning_punishment = None  # Tie detected

    # Announce result
    if winning_punishment:
        await ctx.send(embed=discord.Embed(
            title="Poll Result",
            description=f"The punishment with the most votes is: **{winning_punishment}** with {max_reactions} vote(s).",
            color=discord.Color.blue()
        ))
    elif max_reactions == 0:
        await ctx.send(embed=discord.Embed(
            title="Poll Result",
            description="No votes were cast in the poll.",
            color=discord.Color.blue()
        ))
    else:
        await ctx.send(embed=discord.Embed(
            title="Poll Result",
            description="There was a tie in the poll. Please resolve the tie or vote again.",
            color=discord.Color.blue()
        ))

# Error handler for missing permissions
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send(embed=unauthorized_embed())
    elif isinstance(error, commands.MissingRequiredArgument):
        if ctx.command.name == 'requesthelp':
            await ctx.send(embed=discord.Embed(
                title="ERROR",
                description="Please provide a reason for the help request.",
                color=discord.Color.red()
            ))

keep_alive()
bot.run("MTQyMTQzNzIxNjg2MDgwMzIxNQ.Ge3UX6.1VP-U6-q8ntS5SN0BPW81xx2ttBNkbgP1amQgI")
