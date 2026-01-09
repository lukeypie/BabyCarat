import nextcord
from nextcord.ext import commands

import utility


class Users(commands.Cog):
    def __init__(self, bot: commands.Bot, helper: utility.Helper):
        self.bot = bot
        self.helper = helper

    @commands.command()
    async def AddPlayer(self, ctx: commands.Context, players: commands.Greedy[nextcord.Member]):
        """Gives the appropriate game role to the given users.
        """
        if len(players) == 0:
            await utility.dm_user(ctx.author, "Usage: <AddPlayer [at least one user]")
            return

        player_names = [p.display_name for p in players]
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)
            for player in players:
                await player.add_roles(self.helper.PlayerRole)
            await utility.dm_user(ctx.author,
                                  "You have assigned the livetext game player role to " + ", ".join(player_names))
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx, "You are not the current ST")

        await self.helper.log(
            f"{ctx.author.mention} has run the AddPlayer command on {', '.join(player_names)} for livetext")

    @commands.command()
    async def RemovePlayer(self, ctx: commands.Context, players: commands.Greedy[nextcord.Member]):
        """Removes the appropriate game role from the given users.
        """
        if len(players) == 0:
            await utility.dm_user(ctx.author, "Usage: <RemovePlayer [at least one user]")
            return

        player_names = [p.display_name for p in players]
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)
            for player in players:
                await player.remove_roles(self.helper.PlayerRole)
            await utility.dm_user(ctx.author,
                                  "You have removed the livetext game player role from " + ", ".join(player_names))
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx, "You are not the current ST")

        await self.helper.log(f"{ctx.author.mention} has run the RemovePlayer command "
                              f"on {', '.join(player_names)} for livetext")

    @commands.command()
    async def WipePlayers(self, ctx: commands.Context):
        """Removes the game role from everyone, useful for when a game doesn't fire.
        """
        if self.helper.authorize_st_command(ctx.author):
            utility.start_processing(ctx)
            role = self.helper.PlayerRole
            players = role.members
            player_names = [p.display_name for p in players]
            for player in players:
                player.remove_roles(role)
            await utility.dm_user(ctx.author,
                                  "You have removed the livetext game player role from " + ", ".join(player_names))
        else:
            utility.deny_command(ctx, "You need to be an ST to run this command")
        
        await self.helper.log(f"{ctx.author.mention} has run the WipePlayers command removing the role from "
                              f"{', '.join(player_names)} for livetext")

    # Wait for kibitz integration
    # @commands.command()
    # async def AddKibitz(self, ctx: commands.Context, kibitzers: commands.Greedy[nextcord.Member]):
    #     """Gives the appropriate kibitz role to the given users.
    #     You can provide a user by ID, mention/ping, or nickname, though giving the nickname may find the wrong user."""
    #     if len(kibitzers) == 0:
    #         await utility.dm_user(ctx.author, "Usage: <AddKibitz [at least one user]")
    #         return

    #     kibitz_role = self.helper.KibitzRole
    #     kibitzer_names = [k.display_name for k in kibitzers]

    #     if self.helper.authorize_st_command(ctx.author):
    #         # React on Approval
    #         await utility.start_processing(ctx)
    #         for watcher in kibitzers:
    #             await watcher.add_roles(kibitz_role)
    #         await utility.dm_user(ctx.author,
    #                               "You have assigned the kibitz role for livetext to " + ", ".join(kibitzer_names)
    #                               )
    #         await utility.finish_processing(ctx)
    #     else:
    #         await utility.deny_command(ctx, "You are not the current ST for livetext")

    #     await self.helper.log(
    #         f"{ctx.author.mention} has run the AddKibitz command on {', '.join(kibitzer_names)} for livetext")

    # @commands.command()
    # async def RemoveKibitz(self, ctx: commands.Context, kibitzers: commands.Greedy[nextcord.Member]):
    #     """Removes the appropriate kibitz role from the given users.
    #     You can provide a user by ID, mention/ping, or nickname, though giving the nickname may find the wrong user."""
    #     if len(kibitzers) == 0:
    #         await utility.dm_user(ctx.author, "Usage: <RemoveKibitz [at least one user]")
    #         return
    #     kibitz_role = self.helper.KibitzRole
    #     kibitzer_names = [k.display_name for k in kibitzers]
    #     if self.helper.authorize_st_command(ctx.author):
    #         # React on Approval
    #         await utility.start_processing(ctx)
    #         for watcher in kibitzers:
    #             await watcher.remove_roles(kibitz_role)
    #         await utility.dm_user(ctx.author,
    #                               "You have removed the kibitz role for livetext to " + ", ".join(kibitzer_names))
    #         await utility.finish_processing(ctx)
    #     else:
    #         await utility.deny_command(ctx, "You are not the current ST for livetext")
    #     await self.helper.log(
    #         f"{ctx.author.mention} has run the RemoveKibitz command on "
    #         f"{', '.join(kibitzer_names)} for livetext")


def setup(bot: commands.Bot):
    bot.add_cog(Users(bot, utility.Helper(bot)))
