import logging
from typing import Optional

import nextcord
from nextcord.ext import commands

import utility
from Cogs.Townsquare import Townsquare, Player
from Cogs.Game import Game

class Grimoire(commands.Cog):
    def __init__(self, bot: commands.Bot, helper: utility.Helper):
        self.bot = bot
        self.helper = helper

    @commands.command(aliases=["ClaimGrim"])
    async def ClaimGrimoire(self, ctx: commands.Context):
        """Grants you the ST role. Fails if there is already an ST."""
        st_role = self.helper.STRole
        if len(st_role.members) == 0 or self.helper.authorize_mod_command(ctx.author):
            await utility.start_processing(ctx)
            await ctx.author.add_roles(st_role)
            await utility.dm_user(ctx.author, "You are now the current ST for livetext")
            # print(self.helper.KibitzChannel.type, self.helper.KibitzChannel.type == 0)
            # if self.helper.KibitzChannel.type == 0:
            #     game_cog: Optional[Game] = self.bot.get_cog("Game")
            #     await game_cog.CloseKibitz(ctx)
            townsquare: Optional[Townsquare] = self.bot.get_cog('Townsquare')
            if townsquare.town_square:
                await utility.dm_user(ctx.author, "Warning, there is already a townsquare set up, " \
                                      "you may need to <endgame to fix this.")
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx,
                                       "This channel already has {0} STs. These users are:\n{1}".format(
                                           str(len(st_role.members)),
                                           "\n".join([ST.display_name for ST in st_role.members]))
                                       )                
        await self.helper.log(f"{ctx.author.mention} has run the ClaimGrimoire Command for livetext")
        
    @commands.command(aliases=["GiveGrim"])
    async def GiveGrimoire(self, ctx: commands.Context, member: nextcord.Member):
        """Removes the ST role from you and gives it to the given user."""
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)
            st_role = self.helper.STRole
            await member.add_roles(st_role)
            await ctx.author.remove_roles(st_role)
            await utility.dm_user(ctx.author,
                                  "You have assigned the current ST role for livetext to " + 
                                  member.display_name)
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx, "You are not the current ST for livetext ")

        await self.helper.log(
            f"{ctx.author.mention} has run the GiveGrimoire Command on {member.mention} for livetext")

    @commands.command(aliases=["DropGrim"])
    async def DropGrimoire(self, ctx: commands.Context):
        """Removes the ST role for the game from you.
        Also announces the free channel if there is no other ST."""

        if self.helper.authorize_st_command(ctx.author):
            # React on Approval
            await utility.start_processing(ctx)
            st_role = self.helper.STRole
            if len(st_role.members) == 1:
                townsquare: Optional[Townsquare] = self.bot.get_cog('Townsquare')
                if townsquare.town_square:
                    dm_content = """You have removed the current ST role from yourself however you have 
                    not yet ended the game, if this is how it's supposed to be carry on, otherwise please 
                    reclaim the ST role and run <EndGame."""
                else:
                    #game_cog: Optional[Game] = self.bot.get_cog("Game") #*
                    #await game_cog.OpenKibitz(ctx) #*
                    dm_content = "You have removed the current ST role from yourself for livetext"
            else:
                dm_content = "You have removed the current ST role from yourself for livetext"
            await ctx.author.remove_roles(st_role)
            dm_success = await utility.dm_user(ctx.author, dm_content)
            if not dm_success:
                await ctx.send(content=dm_content, reference=ctx.message)
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx, "You are not the current ST for livetext")

        await self.helper.log(f"{ctx.author.mention} has run the DropGrimoire Command for livetext")

    @commands.command(aliases=["ShareGrim"])
    async def ShareGrimoire(self, ctx: commands.Context, member: nextcord.Member):
        """Gives the ST role for the game to the given user without removing it from you.
        Use this if you want to co-ST a game."""
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)
            await member.add_roles(self.helper.STRole)
            townsquare: Optional[Townsquare] = self.bot.get_cog('Townsquare')
            if townsquare:
                townsquare.town_square.sts.append(Player(member.id, member.display_name))
            dm_content = f"You have assigned the ST role for livetext to {member.display_name}"
            dm_success = await utility.dm_user(ctx.author, dm_content)
            if not dm_success:
                await ctx.send(content=dm_content, reference=ctx.message)
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx, "You are not the current ST for livetext")

        await self.helper.log(
            f"{ctx.author.mention} has run the ShareGrimoire Command on {member.mention} for livetext")
        
    @commands.command(aliases=["RemoveGrim"])
    async def RemoveGrimoire(self, ctx: commands.Context, member: nextcord.Member):
        """Removes the ST role for targeted player"""

        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)
            st_role = self.helper.STRole
            await member.remove_roles(st_role)
            if len(st_role.members) == 0:
                dm_content = f"""You have removed the current ST role from {member.display_name},however 
                you have not yet ended the game, if this is how it's supposed to be carry on, otherwise 
                please reclaim the ST role and run <EndGame."""
                dm_success = await utility.dm_user(ctx.author, dm_content)
                if not dm_success:
                    await ctx.send(content=dm_content, reference=ctx.message)
            dm_content = f"{ctx.author} has removed the current ST role from you"
            dm_success = await utility.dm_user(member, dm_content)
            if not dm_success:
                await ctx.send(content=dm_content, reference=ctx.message)
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx, "You are not a current ST for livetext")

        await self.helper.log(f"{ctx.author.mention} has run the RemoveGrimoire Command on {member.mention} for livetext")

def setup(bot: commands.Bot):
    bot.add_cog(Grimoire(bot, utility.Helper(bot)))
