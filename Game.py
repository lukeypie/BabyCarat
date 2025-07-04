from time import strftime, gmtime
from typing import Optional

from nextcord.ext import commands

import utility
from Cogs.Townsquare import Townsquare
from Cogs.Reminders import Reminders

class Game(commands.Cog):
    def __init__(self, bot: commands.Bot, helper: utility.Helper):
        self.bot = bot
        self.helper = helper

    @commands.command()
    async def OpenKibitz(self, ctx):
        """Makes the kibitz channel to the game visible to the public.
        Players will still need to remove their game role to see it. Use after the game has concluded.
        Will also send a message reminding players to give feedback for the ST and provide a link to do so.
        In most cases, EndGame may be the more appropriate command."""
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)

            # Change permission of Kibitz to allow Townsfolk to view
            townsfolk_role = self.helper.Guild.default_role
            kibitz_channel = self.helper.KibitzChannel
            await kibitz_channel.set_permissions(townsfolk_role, view_channel=True)

            # React for completion
            await utility.finish_processing(ctx)
        else:
            # React on Disapproval
            await utility.deny_command(ctx, "You are not the current ST")

        await self.helper.log(f"{ctx.author.mention} has run the OpenKibitz Command in livetext")

    @commands.command()
    async def CloseKibitz(self, ctx):
        """Makes the kibitz channel to the game hidden from the public.
        This is typically already the case when you claim a grimoire, but might not be in some cases. Make sure none of
         your players have the kibitz role, as they could still see the channel in that case."""
        if self.helper.authorize_st_command(ctx.author):
            # React on Approval
            await utility.start_processing(ctx)

            # Change permission of Kibitz to allow Townsfolk to not view
            townsfolk_role = self.helper.Guild.default_role

            kibitz_channel = self.helper.KibitzChannel
            await kibitz_channel.set_permissions(townsfolk_role, view_channel=False)

            # React for completion
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx, "You are not the current ST")

        await self.helper.log(f"{ctx.author.mention} has run the CloseKibitz Command in livetext")

    @commands.command()
    async def EndGame(self, ctx: commands.Context):
        """Opens Kibitz to the public and cleans up after the game.
        This includes removing the game role from players and the kibitz role from kibitzers, sending a message
        reminding players to give feedback for the ST with a link to do so,
        and resetting the town square if there is one."""
        if self.helper.authorize_st_command(ctx.author):
            # React on Approval
            await utility.start_processing(ctx)

            # Gather member list & role information
            kibitz_role = self.helper.KibitzRole
            game_role = self.helper.PlayerRole
            members = game_role.members + kibitz_role.members

            # Remove roles from non-bot players
            for member in members:
                if not member.bot:
                    await member.remove_roles(kibitz_role)
                    await member.remove_roles(game_role)

            townsquare: Optional[Townsquare] = self.bot.get_cog("Townsquare")
            if townsquare:
                townsquare.town_square = None
                townsquare.update_storage()

            reminders: Optional[Reminders] = self.bot.get_cog("Reminders")
            if reminders:
                reminders.reminder_list = []
                reminders.update_storage()

            # Change permission of Kibitz to allow Townsfolk to view
            townsfolk_role = self.helper.Guild.default_role
            kibitz_channel = self.helper.KibitzChannel
            await kibitz_channel.set_permissions(townsfolk_role, view_channel=True)

            # React for completion
            await utility.finish_processing(ctx)

        else:
            # React on Disapproval
            await utility.deny_command(ctx, "You are not the current ST for livetext")

        await self.helper.log(f"{ctx.author.mention} has run the EndGame Command for livetext")

def setup(bot):
    bot.add_cog(Game(bot, utility.Helper(bot)))
