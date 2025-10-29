import io
import logging
import traceback

import nextcord
from nextcord.ext import commands

import utility

green_square_emoji = '\U0001F7E9'
red_square_emoji = '\U0001F7E5'
refresh_emoji = '\U0001F504'


class Signup(commands.Cog):
    def __init__(self, bot: commands.Bot, helper: utility.Helper):
        self.bot = bot
        self.bot.add_view(SignupView(helper))  # so it knows to listen for buttons on pre-existing signup forms
        self.helper = helper

    @commands.command()
    async def ShowSignUps(self, ctx: commands.Context):
        """Sends a DM listing the STs, players, and kibitz members of the game."""
        await utility.start_processing(ctx)
        st_role = self.helper.STRole
        st_names = [st.display_name for st in st_role.members]
        player_role = self.helper.PlayerRole
        player_names = [player.display_name for player in player_role.members]
        #kibitz_role = self.helper.KibitzRole
        #kibitz_names = [kibitzer.display_name for kibitzer in kibitz_role.members]

        output_string = f"Players\n" \
                        f"Storyteller:\n"
        output_string += "\n".join(st_names)

        output_string += "\nPlayers:\n"
        output_string += "\n".join(player_names)

        #output_string += "\nKibitz members:\n"
        #output_string += "\n".join(kibitz_names)

        dm_success = await utility.dm_user(ctx.author, output_string)
        if not dm_success:
            await ctx.send(content=output_string, reference=ctx.message)
        await utility.finish_processing(ctx)

    @commands.command()
    async def StartSignups(self, ctx: commands.Context):
        """Posts a message listing the signed up players in the appropriate game channel, with buttons that players can use to sign up or leave the game.
        If players are added or removed in other ways, may need to be updated explicitly with the appropriate button to
         reflect those changes."""
        if ctx.channel == self.helper.GameChannel:
            await utility.start_processing(ctx)
            # Post Signup Page
            st_names = [st.display_name for st in self.helper.STRole.members] if len(self.helper.STRole.members) != 0 else ["unknown"]
            player_list = self.helper.PlayerRole.members
            embed = nextcord.Embed(title="Livetext Game Sign Up",
                                    description="Ran by " + ", ".join(st_names) +
                                                f"\nPress {green_square_emoji} to sign up for the game"
                                                f"\nPress {red_square_emoji} to remove yourself from the game"
                                                f"\nPress {refresh_emoji} if the list needs updating "
                                                "(if a command is used to assign roles)",
                                    color=0xff0000)
            for i, player in enumerate(player_list):
                name = player.display_name
                embed.add_field(name=str(i + 1) + ". " + str(name),
                                value=f"{player_list[i].mention} has signed up",
                                inline=False)
            await self.helper.GameChannel.send(embed=embed, view=SignupView(self.helper))
            await utility.finish_processing(ctx)
        else:
            utility.deny_command(ctx, "This command is exclusive to livetext and hence only usable in that channel.")         
            

class SignupView(nextcord.ui.View):
    def __init__(self, helper: utility.Helper):
        super().__init__(timeout=3600)  # 1hr, stops old signups being used
        self.helper = helper

    async def on_error(self, error: Exception, item: nextcord.ui.Item, interaction: nextcord.Interaction) -> None:
        traceback_buffer = io.StringIO()
        traceback.print_exception(type(error), error, error.__traceback__, file=traceback_buffer)
        traceback_text = traceback_buffer.getvalue()
        logging.exception(f"Ignoring exception in SignupView:\n{traceback_text}")

    @nextcord.ui.button(label="Sign Up", custom_id="Sign_Up_Command", style=nextcord.ButtonStyle.green)
    async def signup_callback(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.send_message(content=f"{button.label} has been selected!",
                                                ephemeral=True)
        game_role = self.helper.PlayerRole
        st_role = self.helper.STRole
        #kibitz_role = self.helper.KibitzRole

        # Sign up command
        if game_role in interaction.user.roles:
            await utility.dm_user(interaction.user, 
                                  "You are already signed up, click the refresh button if this is not visible.")
        elif st_role in interaction.user.roles:
            await utility.dm_user(interaction.user,
                                  "You are the Storyteller for this game and so cannot sign up for it")
        elif interaction.user.bot:
            pass
        else:
            await interaction.user.add_roles(game_role)
            #await interaction.user.remove_roles(kibitz_role)
            await self.update_signup_sheet(interaction.message)
            for st in st_role.members:
                await utility.dm_user(st,
                                      f"{interaction.user.display_name} ({interaction.user.name}) "
                                      f"has signed up for livetext")
            await self.helper.log(
                f"{interaction.user.display_name} ({interaction.user.name}) has signed up for livetext")

    @nextcord.ui.button(label="Leave Game", custom_id="Leave_Game_Command", style=nextcord.ButtonStyle.red)
    async def leave_callback(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.send_message(content=f"{button.label} has been selected!",
                                                ephemeral=True)
        game_role = self.helper.PlayerRole
        st_role = self.helper.STRole

        if game_role not in interaction.user.roles:
            await utility.dm_user(interaction.user, "You haven't signed up")
        elif interaction.user.bot:
            pass
        else:
            await interaction.user.remove_roles(game_role)
            await self.update_signup_sheet(interaction.message)
            for st in st_role.members:
                await utility.dm_user(st,
                                      f"{interaction.user.display_name} ({interaction.user.name}) "
                                      f"has removed themself from the livetext sign ups")
            await self.helper.log(
                f"{interaction.user.display_name} ({interaction.user.name}) "
                f"has removed themself from the livetext sign ups")

    @nextcord.ui.button(label="Refresh List", custom_id="Refresh_Command", style=nextcord.ButtonStyle.gray,
                        emoji=refresh_emoji)
    async def refresh_callback(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.send_message(content=f"{button.label} has been selected!",
                                                ephemeral=True)
        await self.update_signup_sheet(interaction.message)

    async def update_signup_sheet(self, signup_message: nextcord.Message):
        st_names = [st.display_name for st in self.helper.STRole.members] if len(self.helper.STRole.members) != 0 else ["unknown"]

        # Update Message
        embed = nextcord.Embed(title="Livetext Game Sign Up",
                               description="Ran by " + ", ".join(st_names) +
                                            f"\nPress {green_square_emoji} to sign up for the game"
                                            f"\nPress {red_square_emoji} to remove yourself from the game"
                                            f"\nPress {refresh_emoji} if the list needs updating "
                                            "(if a command is used to assign roles)",
                                color=0xff0000)        
        player_list = self.helper.PlayerRole.members
        for i, player in enumerate(player_list):
            name = player.display_name
            embed.add_field(name=str(i + 1) + ". " + str(name),
                            value=f"{player_list[i].mention} has signed up",
                            inline=False)
        await signup_message.edit(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Signup(bot, utility.Helper(bot)))
