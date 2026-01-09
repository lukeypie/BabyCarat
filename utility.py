import logging
import os
from typing import Union, Optional

import nextcord
from dotenv import load_dotenv
from nextcord.ext import commands
from nextcord.utils import get

WorkingEmoji = '\U0001F504'
CompletedEmoji = '\U0001F955'
DeniedEmoji = '\U000026D4'

async def dm_user(user: Union[nextcord.User, nextcord.Member], content: str) -> bool:
    try:
        await user.send(content)
        return True
    except nextcord.Forbidden:
        logging.warning(f"Could not DM {user} - user has DMs disabled")
        return False
    except Exception as e:
        logging.exception(f"Could not DM {user}: {e}")
        return False


async def deny_command(ctx: commands.Context, reason: Optional[str]):
    try:
        await ctx.message.remove_reaction(WorkingEmoji, ctx.bot.user)
    except:
        pass # don't care if it fails
    await ctx.message.add_reaction(DeniedEmoji)
    if reason is not None:
        await dm_user(ctx.author, reason)
        logging.info(f"The {ctx.command.name} command was stopped against {ctx.author.name} because of {reason}")
    else:
        logging.info(f"The {ctx.command.name} command was stopped against {ctx.author.name}")


async def finish_processing(ctx: commands.Context):
    try:
        await ctx.message.remove_reaction(WorkingEmoji, ctx.bot.user)
    except:
        pass # don't care if it fails
    await ctx.message.add_reaction(CompletedEmoji)
    logging.info(f"The {ctx.command.name} command was used successfully by {ctx.author.name}")


async def start_processing(ctx: commands.Context):
    await ctx.message.add_reaction(WorkingEmoji)


def is_mention(string: str) -> bool:
    return string.startswith("<@") and string.endswith(">") and string[2:-1].isdigit()


class Helper:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        load_dotenv()
        self.Guild = get(bot.guilds, id=int(os.environ['GUILD_ID']))
        self.GameChannel = get(self.Guild.channels, id=int(os.environ['GAME_CHANNEL_ID']))
        #self.KibitzChannel = get(self.Guild.channels, id=int(os.environ['KIBITZ_CHANNEL_ID']))
        self.STRole = get(self.Guild.roles, id=int(os.environ['ST_ROLE_ID']))
        self.PlayerRole = get(self.Guild.roles, id=int(os.environ['PLAYER_ROLE_ID']))
        #self.KibitzRole = get(self.Guild.roles, id=int(os.environ['KIBITZ_ROLE_ID']))
        self.ModRole = get(self.Guild.roles, id=int(os.environ['DOOMSAYER_ROLE_ID']))
        self.OwnerID = int(os.environ['OWNER_ID'])
        self.DevIDs = list(map(int, os.environ['DEVELOPERIDS'].split()))
        self.LogChannel = get(self.Guild.channels, id=int(os.environ['LOG_CHANNEL_ID']))
        self.StorageLocation = os.environ['STORAGE_LOCATION']
        if None in [self.Guild, self.GameChannel, self.STRole, self.PlayerRole, self.ModRole, 
                    self.OwnerID, self.LogChannel, self.StorageLocation]:
            logging.error("Failed to find required discord entity. Check .env file is correct and Guild is set up")
            raise EnvironmentError

    def authorize_st_command(self, author: Union[nextcord.Member, nextcord.User]):
        if isinstance(author, nextcord.User):
            member = get(self.Guild.members, id=author.id)
            if member is None:
                logging.warning("Non guild member attempting to use ST command")
                return False
        else:
            member = author
        return (self.ModRole in member.roles) or (self.STRole in member.roles) \
            or (member.id == self.OwnerID)

    def authorize_mod_command(self, author: Union[nextcord.Member, nextcord.User]):
        if isinstance(author, nextcord.User):
            member = get(self.Guild.members, id=author.id)
            if member is None:
                logging.warning("Non guild member attempting to use mod command")
                return False
        else:
            member = author
        return (self.ModRole in author.roles) or (author.id == self.OwnerID)

    async def log(self, log_string: str):
        await self.LogChannel.send(log_string)