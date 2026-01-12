import typing

import nextcord
from nextcord.ext import commands

import utility
from Cogs.Townsquare import Townsquare, TownSquare

import os
import datetime
from nextcord.utils import utcnow

class Other(commands.Cog):

    def __init__(self, bot: commands.Bot, helper: utility.Helper):
        self.bot = bot
        self.helper = helper
        self.StarttimeStorage = os.path.join(self.helper.StorageLocation, "starttime.json")

        if not os.path.exists(self.StarttimeStorage):
            self.start_time = utcnow()
            with open(self.StarttimeStorage, 'w') as f:
                f.write(self.start_time.strftime("%d/%m/%Y, %H:%M:%S"))
        else:
            with open(self.StarttimeStorage, 'r') as f:
                self.start_time: datetime.datetime = datetime.datetime.strptime(f.read(), "%d/%m/%Y, %H:%M:%S").astimezone(tz=None)

    async def record_time(self):
        """Records current UTC time and stores it
        """
        self.start_time = utcnow()
        with open(self.StarttimeStorage, 'w') as f:
            f.write(self.start_time.strftime("%d/%m/%Y, %H:%M:%S"))

    @commands.command()
    async def SetStart(self, ctx: commands.Context):
        """Allows the bot to know when to consider threads from for <subplayer and <sendtothreads
        Run this command before any ST threads are made even if the bots systems are not being used
        """
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)
            await self.record_time()
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx, "You are not a livetext ST")

    @commands.command(aliases=("sw",))
    async def StartWhisper(self, ctx: commands.Context, title: str, players: commands.Greedy[nextcord.Member]):
        """Creates a new thread with the specified title and included members
        """
        channel = ctx.channel.parent if isinstance(ctx.channel, nextcord.Thread) else ctx.channel
        if channel.category and channel.category == self.helper.GameChannel.category:
            await utility.start_processing(ctx)
            if len(title) > 100:
                await utility.dm_user(ctx.author, "Thread title too long, will be shortened")

            thread = await channel.create_thread(
                name=title[:100],
                type=nextcord.ChannelType.private_thread,
                reason=f"Starting whisper for {ctx.author.display_name}"
            )

            await thread.add_user(ctx.author)
            for player in players:
                await thread.add_user(player)
            await utility.finish_processing(ctx)
        else:
            await ctx.author.send("This is a livetext exclusive command that is only usable within the livetext category, " \
                                  "use carat's >sw command instead.")

    @commands.command()
    async def CreateThreads(self, ctx: commands.Context, setup_message: str = None):
        """Creates a private thread in the game's channel for each player.
        The player and all STs are automatically added to each thread. The threads are named "ST Thread [player name]".
        """
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)
            townsquare: typing.Optional[Townsquare] = self.bot.get_cog("Townsquare")
            if townsquare:
                townsquare: typing.Optional[TownSquare] = townsquare.town_square
            for player in self.helper.PlayerRole.members:
                name = player.display_name
                if townsquare:
                    name = next((p.alias for p in townsquare.players if p.id == player.id), name)

                thread = await self.helper.GameChannel.create_thread(
                    name=f"ST Thread {name}"[:100],
                    auto_archive_duration=60,  # 1 hr
                    type=nextcord.ChannelType.private_thread,
                    invitable=False,
                    reason=f"Preparing livetext ST Threads"
                )
                                
                await thread.add_user(player)
                for st in self.helper.STRole.members:
                    await thread.add_user(st)
                if setup_message:
                    await thread.send(setup_message)
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx, "You are not a livetext ST")

    @commands.command()
    async def SendToThreads(self, ctx: commands.Context, message: str):
        """Sends the same message to all active ST threads with "ST Thread" in the thread name,  
        that were created since SetStart was ran or 3 hrs ago, whichever is soonest.
        """
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)

            default_time = utcnow() - datetime.timedelta(hours = 3)
            last_set_time = self.start_time
            min_creation_time = default_time if default_time > last_set_time else last_set_time

            threads = self.helper.GameChannel.threads
            for thread in threads:
                if "st thread" in thread.name.lower() and thread.created_at > min_creation_time:
                    await thread.send(message)
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx, "You are not a livetext ST")

    @commands.command()
    async def HelpMe(self, ctx: commands.Context, command_type: typing.Optional[str] = "no-mod"):
        """Sends a message listing and explaining available commands.
        Can be filtered by appending one of `all, anyone, st, townsquare, mod, no-mod`. Default is `no-mod`"""
        await utility.start_processing(ctx)
        anyone_embed = nextcord.Embed(title="Unofficial livetext Game Bot",
                                      description="Commands that can be executed by anyone", color=0xe100ff)
        anyone_embed.set_thumbnail(url=self.bot.user.avatar.url)

        anyone_embed.add_field(name="<FindGrimoire",
                               value="Sends you a DM listing everyone who currently has the stlivetext role.",
                               inline=False)
        anyone_embed.add_field(name="<ShowSignups",
                               value="Sends you a DM listing the STs and players of the game.",
                               inline=False)
        anyone_embed.add_field(name="<ClaimGrimoire",
                               value='Grants you the stlivetext, unless it is already occupied. ',
                               inline=False)
        anyone_embed.add_field(name="<ShowReminders",
                               value="Sends you a DM listing all the currently set reminders.",
                               inline=False)
        anyone_embed.add_field(name="<StartWhisper [thread title] [at least one user]",
                               value="Can use `<sw` for short. Creates a new thread with the specified title and "
                                     "included members. Works exactly like carat's version.\n"
                                     "Usage examples: `<StartWhisper \"Vanilla JohnDoe\" @johndoe`,"
                                     "\n`<sw \"group thread\" @johndoe @maryjane @BobJohnson`")
        anyone_embed.add_field(name="<HelpMe",
                               value="Sends this message. Can be filtered by appending one of `all, anyone, st, mod, "
                                     "no-mod`. Default is `no-mod`\n"
                                     "Usage example: `<HelpMe all`",
                               inline=False)
        anyone_embed.set_footer(text="1/4")

        st_embed = nextcord.Embed(title="Unofficial livetext Game Bot",
                                  description="Commands that can be executed by the ST of the relevant game - mods "
                                              "can ignore this restriction",
                                  color=0xe100ff)
        st_embed.set_thumbnail(url=self.bot.user.avatar.url)
        # st_embed.add_field(name=">OpenKibitz [game number]",
        #                    value='Makes the kibitz channel to the game visible to the public. Players will still need '
        #                          'to remove their game role to see it. Use after the game has concluded. Will also '
        #                          'send a message reminding players to give feedback for the ST and provide a link to '
        #                          'do so. In most cases, EndGame may be the more appropriate command.\n',
        #                    inline=False)
        # st_embed.add_field(name=">CloseKibitz [game number]",
        #                    value='Makes the kibitz channel to the game hidden from the public. This is typically '
        #                          'already the case when you claim a grimoire, but might not be in some cases. Make '
        #                          'sure none of your players have the kibitz role, as they could still see the channel '
        #                          'in that case.\n',
        #                    inline=False)
        st_embed.add_field(name="<EndGame",
                           value='Removes the game role from all players and the kibitz role from your kibitzers, '
                                 'makes the kibitz channel visible to the public, and sends a message reminding '
                                 'players to give feedback for the ST and providing a link to do so.',
                           inline=False)
        st_embed.add_field(name="<StartSignups",
                           value='Posts a message listing the signed up players and sts with buttons that players '
                                 'can use to sign up or leave the game. If players are added or removed in other ways, '
                                 'may need to be updated explicitly with the appropriate button to reflect those changes. ',
                           inline=False)
        st_embed.add_field(name="<CreateThreads [setup message]",
                           value='Creates a private thread for each player, named "ST Thread [player name]", adds the '
                                 'player and all STs to it, then posts [setup message] into each thread.',
                           inline=False)
        st_embed.add_field(name="<SetReminders [event] [times]",
                           value="At the given times, sends reminders to the players how long they have until the "
                                 "event occurs. The event argument is optional and defaults to 'Whispers close'. Times "
                                 "must be given in minutes from the current time, either as integer, decimal number or "
                                 "in mm:ss format. You can give any number of times. The event is assumed to occur at "
                                 "the latest given time. You can have the reminders also ping Storytellers and/or not "
                                 "ping players by adding 'ping-st'/'no-player-ping'\n"
                                 "Usage examples: `<SetReminders \"Votes on Alice close\" 12 18 23 24 ping-st`, "
                                 "`<SetReminders 18 24 30 33 36`, "
                                 "`<SetReminders \"Count the votes\" 12 ping-st no-player-ping`",
                           inline=False)
        st_embed.add_field(name="<DeleteReminders",
                           value='Deletes all reminders currently set.',
                           inline=False)
        st_embed.add_field(name="<GiveGrimoire [User]",
                           value='Removes the livetextst role from you and gives it to the given user. You must '
                                 'ping the user.\n' +
                                 'Usage examples: `<GiveGrimoire @Ben`',
                           inline=False)
        st_embed.add_field(name="<DropGrimoire",
                           value='Removes the ST role for the game from you.',
                           inline=False)
        st_embed.add_field(name="<ShareGrimoire [User]",
                           value='Gives the livetextst role to the given user without removing it from you. Use '
                                 'if you want to co-ST a game. You must ping the user.\n' +
                                 'Usage examples: `<ShareGrimoire @Ben`',
                           inline=False)
        st_embed.add_field(name="<AddPlayer [at least one user]",
                           value='Gives the game role to the given users. You must ping the users.\n' +
                                 'Usage examples: `<AddPlayer x3 @Alex @Ben @Celia`',
                           inline=False)
        st_embed.add_field(name="<RemovePlayer [at least one user]",
                           value='Removes the game role from the given users. You must ping the users.\n' +
                                 'Usage examples:`<RemovePlayer x3 @Alex @Ben @Celia`',
                           inline=False)
        st_embed.add_field(name="<WipePlayers",
                           value="Removes the game role from everyone who currently has it, usedul for when "
                                 "a game doesn't fire.",
                           inline = False)
        # st_embed.add_field(name=">AddKibitz [game number] [at least one user] (Requires ST Role or Mod)",
        #                    value='Gives the appropriate kibitz role to the given users. You can provide a user by ID, '
        #                          'mention/ping, or nickname, though giving the nickname may find the wrong user.\n' +
        #                          'Usage examples: `>AddKibitz 1 793448603309441095`, `>AddKibitz x3 @Alex @Ben @Celia`',
        #                    inline=False)
        # st_embed.add_field(name=">RemoveKibitz [game number] [at least one user] (Requires ST Role or Mod)",
        #                    value='Removes the appropriate kibitz role from the given users. You can provide a user by '
        #                          'ID, mention/ping, or nickname, though giving the nickname may find the wrong '
        #                          'user.\n' +
        #                          'Usage examples: `>RemoveKibitz 1 793448603309441095`, '
        #                          '`>RemoveKibitz x3 @Alex @Ben @Celia`',
        #                    inline=False)
        st_embed.set_footer(text="2/4")

        ts_embed = nextcord.Embed(title="Unofficial livetext Game Bot",
                                  description="Commands related to the town square", color=0xe100ff)
        ts_embed.set_thumbnail(url=self.bot.user.avatar.url)
        ts_embed.add_field(name="<SetupTownSquare [players]",
                           value="Creates the town square for the given game, with the given players. "
                                 "Ping them in order of seating.\n"
                                 "Usage example: `<SetupTownSquare @Alex @Ben @Celia @Derek @Eli @Fiona @Gabe @Hannah`",
                           inline=False)
        ts_embed.add_field(name="<UpdateTownSquare [players]",
                           value="Updates the town square with the given players. Ping them in order of seating. "
                                 "The difference to rerunning SetupTownSquare is that the latter will lose information "
                                 "like aliases, spent deadvotes, and nominations - UpdateTownSquare will not, except for "
                                 "nominations of or by removed players.\n"
                                 "Usage example: `>UpdateTownSquare x1 @Alex @Ben @Celia @Derek @Eli @Fiona @Gideon @Hannah`",
                           inline=False)
        ts_embed.add_field(name="<SubstitutePlayer [player] [substitute]",
                           value="Exchanges a player in the town square with a substitute. Transfers the position, "
                                 "status, nominations and votes of the exchanged player to the substitute, adds the "
                                 "substitute to all threads the exchanged player was in, and adds/removes the "
                                 "game role. Can be used without the town square.\n"
                                 "Usage example: `<SubstitutePlayer @Alex @Amy`",
                           inline=False)
        ts_embed.add_field(name="<CreateNomThread [name]",
                           value='Creates a thread for nominations to be run in. The name of the thread is optional, '
                                 'with `Nominations` as default.\n'
                                 'Usage examples: `<CreateNomThread`, `<CreateNomThread "D2 Nominations"`',
                           inline=False)
        ts_embed.add_field(name="<Nominate [nominee] [nominator]",
                           value="Create a nomination for the given nominee. If you are a ST, provide the nominator. "
                                 "If you are a player, leave the nominator out or give yourself. In either case, you "
                                 "don't need to ping, a name should work. The ST may disable this command for players.\n"
                                 "Usage examples: `<Nominate Alex Ben`, <Nominate 3 Alex`",
                           inline=False)
        ts_embed.add_field(name="<AddAccusation [accusation]",
                           value='Add an accusation to the nomination. You must be the nominator or a storyteller for this.\n'
                                 'Usage examples: `<AddAccusation "In a doubleclaim"`',
                           inline=False)
        ts_embed.add_field(name=">AddDefence [defence]",
                           value='Add a defence to the nomination. You must be the nominee or a storyteller for this.\n'
                                 'Usage examples: `<AddDefence "I\'m good I promise"`',
                           inline=False)
        ts_embed.add_field(name="<SetVoteThreshold [threshold]",
                           value='Set the vote threshold to put a player on the block to the given number. Can\'t be 0.'
                                 'You must be a storyteller for this.\n'
                                 'Usage examples: `<SetVoteThreshold 4`',
                           inline=False)
        ts_embed.add_field(name="<Vote [vote] [voter]",
                           value='Set your vote for the current nomination. You can change your vote until it is counted. '
                                 'If you are a player you only have to provide a vote, an st must provide the player they are '
                                 'voting on behalf of. \n'
                                 'WARNING: The bot will accept any vote but only understands "yes", "no", "y" or "n".\n'
                                 'Usage examples: `<Vote Yes`, `<v n` (shorthand)',
                           inline=False)
        ts_embed.add_field(name="<CloseNomination ",
                           value='Marks the nomination as closed. '
                                 'You must be a storyteller for this.\n',
                           inline=False)
        ts_embed.add_field(name="<SetAlias [alias]",
                           value='Set your preferred alias for the this game. This will be used anytime the bot '
                                 'refers to you. The default is your username. Can be used by players and storytellers.\n'
                                 'Usage examples: `<SetAlias "Alex"`',
                           inline=False)
        ts_embed.add_field(name="<ToggleOrganGrinder",
                           value='Activates or deactivates Organ Grinder for the display of nominations in the game. '
                                 'You must be a storyteller for this.',
                           inline=False)
        ts_embed.add_field(name="<TogglePlayerNoms",
                           value='Activates or deactivates the ability of players to nominate directly. '
                                 'You must be a storyteller for this.',
                           inline=False)
        ts_embed.add_field(name="<ToggleMarkedDead [player_identifier]",
                           value="Marks the given player as dead or alive for display on nominations. "
                                 "You must be a storyteller for this.\n"
                                 "Usage examples: `<ToggleMarkedDead Alex`",
                           inline=False)
        ts_embed.add_field(name="<ToggleCanVote [player_identifier]",
                           value="Allows or disallows the given player to vote. You must be a storyteller for this.\n"
                                 "Usage examples: `<ToggleCanVote Alex`",
                           inline=False)
        ts_embed.add_field(name="<LockVote [Vote]",
                           value="Lock the player who current has the clockhand on them's vote, a vote can be provided "
                                 "to overide their current vote if needed. You must be a storyteller for this.\n"
                                 "Usage examples: `<LockVote`, `<LockVote Yes`",
                           inline=False)
        ts_embed.add_field(name="<CountVotes",
                           value="Starting counting the votes from whoever currently has the clockhand on them, each "
                                 "player will have an amount of time (default 5 seconds) to vote before their vote is "
                                 "defaulted to no, if the bot can't figure out the vote it is set to no. "
                                 "Can be paused by `<PauseCounting`. You must be an ST to use this. ",
                           inline=False)
        ts_embed.add_field(name="<PauseCounting",
                           value="Pauses <CountVotes immedately, can be ran at any time but will only have an effect "
                                 "on currently counting nominations.",
                           inline=False)
        
        ts_embed.set_footer(text="3/4")

        mod_embed = nextcord.Embed(title="Unofficial livetext Game Bot",
                                   description="Commands that can only be executed by moderators", color=0xe100ff)
        mod_embed.set_thumbnail(self.bot.user.avatar.url)
        mod_embed.add_field(name="<RemoveGrimoire [User]",
                            value="Removes the grimoire from the given user. You must ping the user.",
                            inline=False)
        mod_embed.set_footer(
            text="4/4")
        try:
            command_type = command_type.lower()
            if command_type == "all":
                await ctx.author.send(embed=anyone_embed)
                await ctx.author.send(embed=st_embed)
                await ctx.author.send(embed=ts_embed)
                await ctx.author.send(embed=mod_embed)
            elif command_type == "anyone":
                await ctx.author.send(embed=anyone_embed)
            elif command_type == "st":
                await ctx.author.send(embed=st_embed)
            elif command_type == "townsquare":
                await ctx.author.send(embed=ts_embed)
            elif command_type == "mod":
                await ctx.author.send(embed=mod_embed)
            elif command_type == "no-mod":
                await ctx.author.send(embed=anyone_embed)
                await ctx.author.send(embed=st_embed)
                await ctx.author.send(embed=ts_embed)
            else:
                await ctx.author.send(
                    'Use `all`, `anyone`, `st`, `townsquare`, `mod` or `no-mod` to filter the help message. '
                    'Default is `no-mod`.')
            await ctx.author.send("Note: If you believe that there is an error with the bot, please let Lukey or a "
                                  "mod know."
                                  "\nThank you!")
        except nextcord.Forbidden:
            await ctx.send("Please enable DMs to receive the help message")
        await utility.finish_processing(ctx)

def setup(bot: commands.Bot):
    bot.add_cog(Other(bot, utility.Helper(bot)))
