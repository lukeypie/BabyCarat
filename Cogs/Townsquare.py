from __future__ import annotations
import io
import json
import logging
import os
import traceback
from dataclasses import dataclass, field
from math import ceil
from typing import List, Optional, Dict, Union, Callable, Literal

import nextcord
from dataclasses_json import dataclass_json
from nextcord.ext import commands
from nextcord.utils import get, utcnow, format_dt

import utility

not_voted_yet = "-"
confirmed_yes_vote = "confirmed_yes_vote"
confirmed_no_vote = "confirmed_no_vote"
voted_yes_emoji = '\U00002705'  # ✅
voted_no_emoji = '\U0000274C'  # ❌
clock_emoji = '\U0001f566'  # 🕦

@dataclass_json
@dataclass
class Player:
    id: int
    alias: str
    can_vote: bool = True
    dead: bool = False
    banshee: bool = False


    def __eq__(self, other):
        return isinstance(other, (Player, nextcord.User, nextcord.Member)) and self.id == other.id


@dataclass_json
@dataclass
class Vote:
    vote: str
    bureaucrat: bool = False
    thief: bool = False
    banshee: bool = False

@dataclass_json
@dataclass
class Nomination:
    nominator: Player
    nominee: Player
    votes: Dict[int, Vote]
    accusation: str = "TBD"
    defense: str = "TBD"
    player_index: int = 0
    message: int = None
    finished: bool = False


@dataclass_json
@dataclass
class TownSquare:
    players: List[Player]
    sts: List[Player]
    current_nomination: Nomination = None
    nomination_thread: int = None
    log_thread: int = None
    organ_grinder: bool = False
    player_noms_allowed: bool = True
    vote_threshold: int = 0
    auto_lock_votes: bool = False

class UnknownVoteError(Exception):
    pass

class NotVotedError(Exception):
    pass

def format_nom_message(game_role: nextcord.Role, town_square: TownSquare, nom: Nomination,
                       emoji: Dict[str, nextcord.PartialEmoji]) -> (str, nextcord.Embed):
    if town_square.vote_threshold == 0:
        votes_needed = ceil(len([player for player in town_square.players if not player.dead]) / 2)
    else:
        votes_needed = town_square.vote_threshold
    players = reordered_players(nom, town_square)
    current_voter = next((player for player in players if player.can_vote and
                          nom.votes[player.id].vote not in [confirmed_yes_vote, confirmed_no_vote]), None)
    content = f"{game_role.mention} {nom.nominator.alias} has nominated {nom.nominee.alias}.\n" \
              f"Accusation: {nom.accusation}\n" \
              f"Defense: {nom.defense}\n" \
              f"{votes_needed} votes required to put {nom.nominee.alias} on the block.\n"
    embed = nextcord.Embed(title="Votes",
                           color=0xff0000)
    counter = 0
    for player in players:
        name = player.alias + " (Nominator)" if player == nom.nominator else player.alias
        if player.dead:
            name = str(emoji["shroud"]) + " " + name
        if player == current_voter:
            name = clock_emoji + " " + name
        vote = nom.votes[player.id]
        if (not player.can_vote) and vote != confirmed_yes_vote:
            embed.add_field(name=f"~~{name}~~", value="", inline=True)
        else:
            if town_square.organ_grinder:
                embed.add_field(name=name,
                                value=str(emoji["organ_grinder"]),
                                inline=False)
            elif vote.vote == confirmed_yes_vote:
                value = 1
                if vote.thief:
                    value *= -1
                if vote.bureaucrat:
                    value *= 3
                if vote.banshee:
                    value *= 2
                counter += value
                embed.add_field(name=name,
                                value=f"{voted_yes_emoji} ({counter}/{votes_needed})",
                                inline=False)
            elif vote.vote == confirmed_no_vote:
                embed.add_field(name=name,
                                value=voted_no_emoji,
                                inline=False)
            else:
                embed.add_field(name=name,
                                value=nom.votes[player.id].vote,
                                inline=False)
    return content, embed


def reordered_players(nom: Nomination, town_square: TownSquare) -> List[Player]:
    if nom.nominee in town_square.players:
        last_vote_index = next(i for i, player in enumerate(town_square.players) if player == nom.nominee)
    elif nom.nominator in town_square.players:
        last_vote_index = next(i for i, player in enumerate(town_square.players) if player == nom.nominator)
    else:
        last_vote_index = len(town_square.players) - 1
    return town_square.players[last_vote_index + 1:] + town_square.players[:last_vote_index + 1]


class Townsquare(commands.Cog):
    bot: commands.Bot
    helper: utility.Helper
    TownSquareStorage: str
    town_square: TownSquare
    emoji: Dict[str, nextcord.PartialEmoji]

    def __init__(self, bot: commands.Bot, helper: utility.Helper):
        self.bot = bot
        self.helper = helper
        self.TownSquareStorage = os.path.join(self.helper.StorageLocation, "townsquare.json")
        self.emoji = {}
        self.vote_count_view = None
        self.town_square = None
        if not os.path.exists(self.TownSquareStorage):
            with open(self.TownSquareStorage, 'w') as f:
                json.dump({}, f, indent=2)
        else:
            with open(self.TownSquareStorage, 'r') as f:
                json_data = json.load(f)
                if json_data != {}:
                    self.town_square = TownSquare.from_dict(json_data)

    async def load_emoji(self):
        self.emoji = {}
        shroud_emoji = get(self.helper.Guild.emojis, name="shroud")
        if shroud_emoji is not None:
            self.emoji["shroud"] = nextcord.PartialEmoji.from_str(
                '{emoji.name}:{emoji.id}'.format(emoji=shroud_emoji))
        else:
            self.emoji["shroud"] = nextcord.PartialEmoji.from_str('\U0001F480')  # 💀
            await self.helper.log("Shroud emoji not found, using default")
        thief_emoji = get(self.helper.Guild.emojis, name="thief")
        if thief_emoji is not None:
            self.emoji["thief"] = nextcord.PartialEmoji.from_str(
                '{emoji.name}:{emoji.id}'.format(emoji=thief_emoji))
        else:
            self.emoji["thief"] = nextcord.PartialEmoji.from_str('\U0001F48E')  # 💎
            await self.helper.log("Thief emoji not found, using default")
        bureaucrat_emoji = get(self.helper.Guild.emojis, name="bureaucrat")
        if bureaucrat_emoji is not None:
            self.emoji["bureaucrat"] = nextcord.PartialEmoji.from_str(
                '{emoji.name}:{emoji.id}'.format(emoji=bureaucrat_emoji))
        else:
            self.emoji["bureaucrat"] = nextcord.PartialEmoji.from_str('\U0001f4ce')  # 📎
            await self.helper.log("Bureaucrat emoji not found, using default")
        banshee_emoji = get(self.helper.Guild.emojis, name="banshee")
        if banshee_emoji is not None:
            self.emoji["banshee"] = nextcord.PartialEmoji.from_str(
                '{emoji.name}:{emoji.id}'.format(emoji=banshee_emoji))
        else:
            self.emoji["banshee"] = nextcord.PartialEmoji.from_str('\U0001f47b')  # 👻
            await self.helper.log("Banshee emoji not found, using default")
        organ_grinder_emoji = get(self.helper.Guild.emojis, name="organ_grinder")
        if organ_grinder_emoji is not None:
            self.emoji["organ_grinder"] = nextcord.PartialEmoji.from_str(
                '{emoji.name}:{emoji.id}'.format(emoji=organ_grinder_emoji))
        else:
            self.emoji["organ_grinder"] = nextcord.PartialEmoji.from_str('\U0001f648')  # 🙈
            await self.helper.log("Organ grinder emoji not found, using default")

    def update_storage(self):
        json_data = {}
        if self.town_square:
            json_data = self.town_square.to_dict()
        with open(self.TownSquareStorage, 'w') as f:
            json.dump(json_data, f, indent=2)

    async def log(self, message: str):
        log_thread = get(self.helper.GameChannel.threads, id=self.town_square.log_thread)
        await log_thread.send((format_dt(utcnow()) + ": " + message)[:2000])

    async def update_nom_message(self, nom: Nomination):
        game_role = self.helper.PlayerRole
        content, embed = format_nom_message(game_role, self.town_square, nom, self.emoji)
        game_channel = self.helper.GameChannel
        nom_thread = get(game_channel.threads, id=self.town_square.nomination_thread)
        try:
            nom_message = await nom_thread.fetch_message(nom.message)
            await nom_message.edit(content=content, embed=embed)
        except nextcord.HTTPException as e:
            if e.code == 10008:  # Discord's 404
                logging.error(f"Missing message for nomination of {nom.nominee.alias} in livetext")
                st_role = self.helper.STRole
                await self.log(f"{st_role.mention} Could not find the nomination message for the "
                                f"nomination of {nom.nominee.alias} to update it. Please close the "
                                f"nomination to prevent this happening again.")
                return
            else:
                raise e
        logging.debug(f"Updated nomination for livetext: {nom}")

    def get_game_participant(self, identifier: str) -> Union[nextcord.Member, None]:
        participants = self.town_square.players + self.town_square.sts
        # handle explicit mentions
        if utility.is_mention(identifier):
            member = get(self.helper.Guild.members, id=int(identifier[2:-1]))
            if member is not None and member.id in [p.id for p in participants]:
                return member
            else:
                return None
        # check alternatives for identifying the player
        alias_matches = self.try_get_matching_player(participants, identifier, lambda p: p.alias)
        display_names = {p.id: get(self.helper.Guild.members, id=p.id).display_name for p in participants}
        display_name_matches = self.try_get_matching_player(participants, identifier, lambda p: display_names[p.id])
        usernames = {p.id: get(self.helper.Guild.members, id=p.id).name for p in participants}
        username_matches = self.try_get_matching_player(participants, identifier, lambda p: usernames[p.id])
        if len(alias_matches) == 1:
            target_id = alias_matches[0]
        elif len(alias_matches) > 1:
            if len(set(alias_matches).intersection(set(display_name_matches))) == 1:
                target_id = list(set(alias_matches).intersection(set(display_name_matches)))[0]
            elif len(set(alias_matches).intersection(set(username_matches))) == 1:
                target_id = list(set(alias_matches).intersection(set(username_matches)))[0]
            elif len(set(display_name_matches).intersection(set(display_name_matches)).intersection(
                    set(username_matches))) == 1:
                target_id = list(set(display_name_matches).intersection(set(display_name_matches)).intersection(
                    set(username_matches)))[0]
            else:
                return None
        elif len(display_name_matches) == 1:
            target_id = display_name_matches[0]
        elif len(display_name_matches) > 1:
            if len(set(display_name_matches).intersection(set(username_matches))) == 1:
                target_id = list(set(display_name_matches).intersection(set(username_matches)))[0]
            else:
                return None
        elif len(username_matches) == 1:
            target_id = username_matches[0]
        else:
            return None
        return get(self.helper.Guild.members, id=target_id)

    # runs before each command - checks a town square exists
    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.command.name in ["SetupTownSquare", "SubstitutePlayer"]:
            return True
        if not self.town_square:
            await utility.deny_command(ctx, "Town Square has not been set up for this game, " \
                                        "please run <SetUpTownSquare to use this functionality")
            return False
        else:
            return True

    @staticmethod
    def try_get_matching_player(player_list: List[Player], identifier: str, attribute: Callable[[Player], str]) \
            -> List[int]:
        matches = [p.id for p in player_list if identifier.lower() in attribute(p).lower()]
        if len(matches) > 1:
            matches = [p.id for p in player_list if attribute(p).lower().startswith(identifier.lower())]
            if len(matches) < 1:
                matches = [p.id for p in player_list if identifier in attribute(p)]
            elif len(matches) > 1:
                matches = [p.id for p in player_list if attribute(p).startswith(identifier)]
                if len(matches) < 1:
                    matches = [p.id for p in player_list if attribute(p).lower() == identifier.lower()]
                elif len(matches) > 1:
                    matches = [p.id for p in player_list if attribute(p) == identifier]
        return matches

    @commands.command()
    async def SetupTownSquare(self, ctx: commands.Context, 
                              players: commands.Greedy[nextcord.Member]):
        """Creates the town square for the given game, with the given players.
        Ping them in order of seating.
        Overwrites information like nominations and votes if a town square existed already.
        Use UpdateTownSquare if that is not what you want."""
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)

            player_list = [Player(p.id, p.display_name) for p in players]
            st_list = [Player(st.id, st.display_name) for st in self.helper.STRole.members]
            self.town_square = TownSquare(player_list, st_list)
            channel = self.helper.GameChannel

            try:
                log_thread = await channel.create_thread(
                    name="Nomination & Vote Logging Thread",
                    auto_archive_duration=60, # 1h
                    type=nextcord.ChannelType.private_thread)
            except nextcord.HTTPException:
                old_logging_threads = [t for t in channel.threads if t.name == "Nomination & Vote Logging Thread"]
                old_logging_threads.sort(key=lambda t: t.create_timestamp)
                try:
                    await old_logging_threads[0].delete()
                    log_thread = await channel.create_thread(
                        name="Nomination & Vote Logging Thread",
                        auto_archive_duration=60, # 1h
                        type=nextcord.ChannelType.private_thread)
                except nextcord.HTTPException:
                    self.town_square = None
                    await utility.deny_command(ctx, "Failed to create logging thread.")
                    return
                
            for st in self.helper.STRole.members:
                await log_thread.add_user(st)

            self.town_square.log_thread = log_thread.id
            await self.log(f"Town square created: {self.town_square}")
            self.update_storage()
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx, "You are not the storyteller for this game")

    @commands.command()
    async def UpdateTownSquare(self, ctx: commands.Context,
                               players: commands.Greedy[nextcord.Member]):
        """Updates the town square for the given game, with the given players.
        Ping them in order of seating. The difference to rerunning SetupTownSquare is that the latter will
        lose information like aliases, spent deadvotes, and nominations. UpdateTownSquare will not. However, it will
        stop nominations of or by players who are removed. If you need to prevent that, use SubstitutePlayer."""
        if self.helper.authorize_st_command(ctx.author):
            if not self.town_square:
                await utility.deny_command(ctx, "No townsquare exists for this game, please run <SetUpTownSquare first.")   
                return 
            await utility.start_processing(ctx)

            new_player_list = [self.reuse_or_convert_player(p) for p in players]
            removed_players = [p for p in self.town_square.players if p not in new_player_list]
            added_players = [p for p in new_player_list if p not in self.town_square.players]
            self.town_square.players = new_player_list
            nom = self.town_square.current_nomination

            if nom:
                for player in removed_players:
                    nom.votes.pop(player.id)
                for player in added_players:
                    nom.votes[player.id] = Vote(not_voted_yet)
                await self.update_nom_message(nom)
            self.update_storage()
            await utility.finish_processing(ctx)
            await self.log(f"{ctx.author.mention} has updated the town square: {new_player_list}")
        else:
            await utility.deny_command(ctx, "You are not the storyteller for this game")

    def reuse_or_convert_player(self, player: nextcord.Member) -> Player:
        existing_player = next((p for p in self.town_square.players if p.id == player.id), None)
        if existing_player:
            return existing_player
        else:
            return Player(player.id, player.display_name)

    @commands.command(aliases=["SubPlayer"])
    async def SubstitutePlayer(self, ctx: commands.Context, player: nextcord.Member,
                               substitute: nextcord.Member):
        """Exchanges a player in the town square with a substitute.
        Transfers the position, status, nominations and votes of the exchanged player to the substitute, adds the
        substitute to all threads the exchanged player was in, and adds/removes the game role.
        Can be used without the town square."""
        if not self.town_square:
            await self.SubstitutePlayerNoTownsquare(ctx, player, substitute)
            return
        
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)

            player_list = self.town_square.players
            current_player = next((p for p in player_list if p.id == player.id), None)
            if current_player is None:
                await utility.deny_command(ctx, f"{player.display_name} is not a participant.")
                return
            substitute_existing_player = next((p for p in player_list if p.id == substitute.id), None)
            if substitute_existing_player is not None:
                await utility.deny_command(ctx, f"{substitute.display_name} is already a player.")
                return
            
            game_role = self.helper.PlayerRole
            await player.remove_roles(game_role, reason="substituted out")
            await substitute.add_roles(game_role, reason="substituted in")
            current_player.id = substitute.id
            current_player.alias = substitute.display_name

            game_channel = self.helper.GameChannel
            other_cog = self.bot.get_cog("Other")
            for thread in game_channel.threads:
                thread_members = await thread.fetch_members()
                if player in [tm.member for tm in thread_members] and thread.create_timestamp > other_cog.start_time:
                    await thread.add_user(substitute)

            nom = self.town_square.current_nomination
            if nom and not nom.finished:
                nom.votes[substitute.id] = nom.votes.pop(player.id)
                await self.update_nom_message(nom)

            await self.log(f"{ctx.author.mention} has substituted {player.display_name} with "
                           f"{substitute.display_name}")
            logging.debug(f"Substituted {player} with {substitute} in livetext - "
                          f"current town square: {self.town_square}")
            self.update_storage()
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx, "You are not the storyteller for this game")

    async def SubstitutePlayerNoTownsquare(self, ctx: commands.Context, player: nextcord.Member,
                                           substitute: nextcord.Member):
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)

            game_role = self.helper.PlayerRole
            if game_role not in player.roles:
                await utility.deny_command(ctx, f"{player.display_name} is not a player.")
                return
            if game_role in substitute.roles:
                await utility.deny_command(ctx, f"{substitute.display_name} is already a player.")
                return

            await player.remove_roles(game_role, reason="substituted out")
            await substitute.add_roles(game_role, reason="substituted in")

            game_channel = self.helper.GameChannel
            other_cog = self.bot.get_cog("Other")
            for thread in game_channel.threads:
                thread_members = await thread.fetch_members()
                if player in [tm.member for tm in thread_members] and thread.create_timestamp > other_cog.start_time:
                    await thread.add_user(substitute)

            logging.debug(f"Substituted {player} with {substitute} in livetext")
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx, "You are not the storyteller for this game")

    @commands.command(aliases=["CreateNomThread", "CreateNominationsThread"])
    async def CreateNominationThread(self, ctx: commands.Context, name: Optional[str]):
        """Creates a thread for nominations to be run in.
        The name of the thread is optional, with `Nominations` as default."""
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)
            if name is not None and len(name) > 100:
                await utility.dm_user(ctx.author, "Thread name is too long, will be shortened")
            game_channel = self.helper.GameChannel
            thread = await game_channel.create_thread(name=name[:100] if name is not None else "Nominations",
                                                      auto_archive_duration=60, # 1h
                                                      type=nextcord.ChannelType.public_thread)
            for st in self.helper.STRole.members:
                await thread.add_user(st)
            self.town_square.nomination_thread = thread.id
            self.update_storage()
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx, "You are not the storyteller for this game")

    @commands.command(aliases=["Nom"])
    async def Nominate(self, ctx: commands.Context,nominee_identifier: str, 
                       nominator_identifier: Optional[str]):
        """Create a nomination for the given nominee.
        If you are an ST, provide the nominator. If you are a player, leave the nominator out or give yourself.
        In either case, you don't need to ping, a name should work."""
        game_role = self.helper.PlayerRole
        can_nominate = self.helper.authorize_st_command(ctx.author) or game_role in ctx.author.roles
        if self.town_square.current_nomination and not self.town_square.current_nomination.finished:
            await utility.deny_command(ctx, "There is already a nomination underway please wait until" \
                                       "that nomination has finished before starting another.")
            return
        nominee = self.get_game_participant(nominee_identifier)
        nominator = self.get_game_participant(nominator_identifier) if nominator_identifier else None
        nom_thread = get(self.helper.Guild.threads, id=self.town_square.nomination_thread)
        if not can_nominate:
            await utility.deny_command(ctx, "You must participate in the game to nominate!")
        elif not self.helper.authorize_st_command(ctx.author) and nominator and nominator.id != ctx.author.id:
            await utility.deny_command(ctx, "You may not nominate in the name of others")
        elif nominator_identifier and not nominator:
            await utility.deny_command(ctx, "The nominator must be a game participant")
        elif not nominee:  # Atheist allows ST to be nominated
            await utility.deny_command(ctx, "The nominee must be a game participant")
        elif not nom_thread:
            await utility.deny_command(ctx, "The nomination thread has not been created. Ask an ST to fix this.")
        else:
            await utility.start_processing(ctx)
            participants = self.town_square.players + self.town_square.sts
            converted_nominee = next((p for p in participants if p.id == nominee.id), None)
            if not converted_nominee:
                await utility.deny_command(ctx,
                                           "The Nominee is not included in the town square. Ask an ST to fix this.")
                return
            if not nominator_identifier:
                converted_nominator = next((p for p in participants if p.id == ctx.author.id), None)
            else:
                converted_nominator = next((p for p in participants if p.id == nominator.id), None)
            if not converted_nominator:
                await utility.deny_command(ctx,
                                           "The Nominator is not included in the town square. Ask an ST to fix this.")
                return
            votes = {}
            for player in self.town_square.players:
                votes[player.id] = Vote(not_voted_yet)
            nom = Nomination(converted_nominator, converted_nominee, votes)

            content, embed = format_nom_message(game_role, self.town_square, nom, self.emoji)
            nom_message = await nom_thread.send(content=content, embed=embed, view=NominationView(self.helper, self.town_square, self.emoji))
            nom.message = nom_message.id
            self.town_square.current_nomination = nom
            logging.debug(f"Nomination created: in livetext: {nom}")
            await utility.finish_processing(ctx)
            self.update_storage()
            await self.log(f"{converted_nominator.alias} has nominated {converted_nominee.alias}")
    
    @commands.command()
    async def AddAccusation(self, ctx: commands.Context, accusation: str):
        """Add an accusation to the nomination of the given nominee.
         You must be the nominator or a storyteller for this."""
        if len(accusation) > 900:
            await utility.deny_command(ctx, "Your accusation is too long. Consider posting it in public and "
                                            "setting a link to the message as your accusation.")
            return
        await utility.start_processing(ctx)
        nom = self.town_square.current_nomination
        if not nom or nom.finished:
            await utility.deny_command(ctx, "No ongoing nominations")
            return
        if ctx.author.id == nom.nominator.id or self.helper.authorize_st_command(ctx.author):
            nom.accusation = accusation
            self.update_storage()
            await self.update_nom_message(nom)
            await utility.finish_processing(ctx)
            await self.log(f"{ctx.author} has added this accusation to the nomination of "
                           f"{nom.nominee.alias}: {accusation}")
        else:
            await utility.deny_command(ctx, "You must be the ST or nominator to use this command")

    @commands.command(aliases=["AddDefence"])
    async def AddDefense(self, ctx: commands.Context, defense: str):
        """Add a defense to your nomination or that of the given nominee.
        You must be a storyteller for the latter."""
        if len(defense) > 900:
            await utility.deny_command(ctx, "Your defense is too long. Consider posting it in public and "
                                            "setting a link to the message as your defense.")
            return
        await utility.start_processing(ctx)
        nom = self.town_square.current_nomination
        if not nom or nom.finished:
            await utility.deny_command(ctx, "No ongoing nominations")
            return
        if ctx.author.id == nom.nominee.id or self.helper.authorize_st_command(ctx.author):
            nom.defense = defense
            self.update_storage()
            await self.update_nom_message(nom)
            await utility.finish_processing(ctx)
            await self.log(f"{ctx.author} has added this defense to the nomination of " 
                           f"{nom.nominee.alias}: {defense}")
        else:
            await utility.deny_command(ctx, "You must be the ST or nominee to use this command")

    @commands.command()
    async def SetVoteThreshold(self, ctx: commands.Context, target: int):
        """Set the vote threshold to put a player on the block to the given number.
        You must be a storyteller for this."""
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)
            if target < 0:
                await utility.deny_command(ctx, "Vote threshold cannot be negative")
                return
            self.town_square.vote_threshold = target
            nom = self.town_square.current_nomination
            if nom and not nom.finished:
                await self.update_nom_message(nom)
                self.update_storage()
            await utility.finish_processing(ctx)
            await self.log(f"{ctx.author} has set the vote threshold to {target}")

    @commands.command()
    async def Vote(self, ctx: commands.Context, vote: str, voter_identifier: str = None):
        """Set your vote for the given nominee or nominees."""
        if self.town_square.organ_grinder and (ctx.channel == self.helper.GameChannel or
                                                             ctx.channel.type == nextcord.ChannelType.public_thread):
            await ctx.message.delete()
            await utility.dm_user(ctx.author, "Please do not vote in public while the Organ Grinder is active. Your "
                                              "vote was not registered.")
            await self.log(f"{ctx.author} tried to vote '{vote}' in public. Vote was not registered")
            return
        
        game_role = self.helper.PlayerRole
        if voter_identifier is not None:
            voter = self.get_game_participant(voter_identifier)
            if voter is None:
                await utility.deny_command(ctx, f"Could not clearly identify any player from {voter_identifier}")
                return
        else:
            voter = ctx.author
        voter = next((p for p in self.town_square.players if p.id == voter.id), None)

        if len(vote) > 400:
            await utility.deny_command(ctx, "Your vote is too long. Consider simplifying your condition. If that is "
                                            "somehow impossible, just let the ST know.")
            return
        if not voter:
            await utility.deny_command(ctx, "You are not included in the town square. Ask the ST to correct this.")
            return
        if not voter.can_vote:
            await utility.deny_command(ctx, "You seem to have spent your vote already.")
            return
        if vote in [confirmed_yes_vote, confirmed_no_vote, not_voted_yet]:
            await utility.deny_command(ctx, "Nice try. That's a reserved string for internal handling, "
                                            "you cannot set your vote to it.")
            return
        
        if game_role in ctx.author.roles or self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)
            nom = self.town_square.current_nomination
            if not nom or nom.finished:
                await utility.deny_command(ctx, "No ongoing nominations")
                return
            if nom.votes[voter.id].vote in [confirmed_yes_vote, confirmed_no_vote]:
                await utility.deny_command(ctx, f"Your vote is already locked in and cannot be changed.")
                return
            
            nom.votes[voter.id] = Vote(vote)
            if ctx.author == voter.id:
                await self.log(f"{voter.alias} has set their vote on the nomination of {nom.nominee.alias} to {vote}")
            else:
                await self.log(f"{ctx.author} has set {voter.alias}'s vote on the nomination of {nom.nominee.alias} to {vote}")
            await self.update_nom_message(nom)

            players = reordered_players(nom, self.town_square)
            if voter.id == players[self.town_square.current_nomination.player_index].id: # If player has clockhand on them
                done = False
                player_no = len(self.town_square.players)
                # loops until someone hasn't voted, bot can't figure vote out or all players have been locked
                while not (done or self.town_square.current_nomination.player_index >= player_no):
                    try:
                        await self.LockNextVote()
                    except NotVotedError:
                        done = True
                    except UnknownVoteError:
                        player = get(self.helper.Guild.members, 
                                     id=players[self.town_square.current_nomination.player_index].id)
                        nom_thread = utility.get(self.helper.GameChannel.threads, id = self.town_square.nomination_thread)
                        if nom_thread:
                            await nom_thread.send(f"Unable to lock {player.mention}'s vote, "
                                                  f"please make your vote either 'yes' or 'no'")
                        done = True
                if self.town_square.current_nomination.player_index == player_no:
                    nom.finished == True
                    await self.update_nom_message(nom)
            self.update_storage()
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx, "You must be a player or storyteller to vote. "
                                            "If you are, the ST may have to add you to the town square.")

    @commands.command(aliases=["CloseNom"])
    async def CloseNomination(self, ctx: commands.Context):
        """Marks the nomination for the given nominee as closed.
        You must be a storyteller for this."""
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)
            nom = self.town_square.current_nomination
            if not nom:
                await utility.deny_command(ctx, "No ongoing nominations")
                return
            nom.finished = True
            self.update_storage()
            await utility.finish_processing(ctx)
            await self.log(f"{ctx.author} has closed the nomination of {nom.nominee.alias}")
        else:
            await utility.deny_command(ctx, "You must be the Storyteller to close a nomination")

    @commands.command()
    async def SetAlias(self, ctx: commands.Context, alias: str):
        """Set your preferred alias for the given game.
        This will be used anytime the bot refers to you. The default is your username.
        Can be used by players and storytellers."""
        game_role = self.helper.PlayerRole
        st_role = self.helper.STRole
        if len(alias) > 100 or utility.is_mention(alias):
            await utility.deny_command(ctx, f"not an allowed alias: {alias}"[:2000])
            return
        
        if game_role in ctx.author.roles:
            await utility.start_processing(ctx)
            player = next((p for p in self.town_square.players if p.id == ctx.author.id), None)
            if not player:
                await utility.deny_command(ctx,
                                           "You are not included in the town square. Ask the ST to correct this.")
                return
            player.alias = alias
            self.update_storage()
            await self.log(f"{ctx.author.name} has set their alias to {alias}")
            await utility.finish_processing(ctx)
        elif st_role in ctx.author.roles:
            await utility.start_processing(ctx)
            st = next((st for st in self.town_square.sts if st.id == ctx.author.id), None)
            if not st:
                await utility.deny_command(ctx, "Something went wrong and you are not included in the townsquare. "
                                                "Try dropping and re-adding the grimoire")
                return
            st.alias = alias
            self.update_storage()
            await self.log(f"{ctx.author.name} has set their alias to {alias}")
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx, "You must be a player to set your alias. "
                                            "If you are, the ST may have to add you to the town square.")

    @commands.command(aliases=["TOrganGrinder"])
    async def ToggleOrganGrinder(self, ctx: commands.Context):
        """Activates or deactivates Organ Grinder for the display of nominations in the game.
        Finished nominations are not updated.
        You must be a storyteller for this."""
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)
            self.town_square.organ_grinder = not self.town_square.organ_grinder
            self.update_storage()
            nom = self.town_square.current_nomination
            if nom and not nom.finished:
                await self.update_nom_message(nom)
            await utility.finish_processing(ctx)
            await utility.dm_user(ctx.author,
                                  f"Organ Grinder is now "
                                  f"{'enabled' if self.town_square.organ_grinder else 'disabled'}")
        else:
            await utility.deny_command(ctx, "You must be the Storyteller to toggle the Organ Grinder")

    @commands.command(aliases=["TPlayerNoms"])
    async def TogglePlayerNoms(self, ctx: commands.Context):
        """Activates or deactivates the ability of players to nominate directly.
        You must be a storyteller for this."""
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)
            self.town_square.player_noms_allowed = not self.town_square.player_noms_allowed
            self.update_storage()
            await utility.finish_processing(ctx)
            await utility.dm_user(ctx.author,
                                  f"Player nominations are now "
                                  f"{'enabled' if self.town_square.player_noms_allowed else 'disabled'}")
        else:
            await utility.deny_command(ctx, "You must be the Storyteller to toggle player nominations")

    @commands.command(aliases=["TMarkedDead","togglemarkdead"])
    async def ToggleMarkedDead(self, ctx: commands.Context, player_identifier: str):
        """Marks the given player as dead or alive for display on nominations.
        You must be a storyteller for this."""
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)
            player_user = self.get_game_participant(player_identifier)
            if not player_user:
                await utility.deny_command(ctx, f"Could not find player with identifier {player_identifier}")
                return
            player = next((p for p in self.town_square.players if p.id == player_user.id), None)
            if not player:
                await utility.deny_command(ctx, f"{player_user.display_name} is not included in the town square.")
                return
            player.dead = not player.dead
            self.update_storage()
            await utility.finish_processing(ctx)
            await utility.dm_user(ctx.author, f"{player.alias} is now "
                                              f"{'marked as dead' if player.dead else 'marked as living'}")
            await self.log(f"{ctx.author} has marked {player.alias} as "
                           f"{'dead' if player.dead else 'living'}")
        else:
            await utility.deny_command(ctx, "You must be the Storyteller to mark a player as dead")

    @commands.command(aliases=["TCanVote"])
    async def ToggleCanVote(self, ctx: commands.Context, player_identifier: str):
        """Allows or disallows the given player to vote.
        You must be a storyteller for this."""
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)
            player_user = self.get_game_participant(player_identifier)
            if not player_user:
                await utility.deny_command(ctx, f"Could not clearly identify any player from {player_identifier}")
                return
            player = next((p for p in self.town_square.players if p.id == player_user.id), None)
            if not player:
                await utility.deny_command(ctx, f"{player_user.display_name} is not included in the town square.")
                return
            player.can_vote = not player.can_vote
            self.update_storage()
            await utility.finish_processing(ctx)
            await utility.dm_user(ctx.author, f"{player.alias} can now "
                                              f"{'vote' if player.can_vote else 'not vote'}")
            await self.log(f"{ctx.author} has set {player.alias} as "
                           f"{'able to vote' if player.can_vote else 'unable to vote'}")
        else:
            await utility.deny_command(ctx, "You must be the Storyteller to toggle a player's voting ability")
            
    @commands.command()
    async def LockVote(self, ctx: commands.Context, vote: str = None):
        """Locks the next vote in the nomination
        """
        if self.helper.authorize_st_command(ctx.author):
            await utility.start_processing(ctx)
            nom = self.town_square.current_nomination
            if not nom or nom.finished:
                await utility.deny_command(ctx, "No ongoing nomination")
                return
            try:
                await self.LockNextVote(vote)
            except UnknownVoteError:
                await utility.deny_command(ctx, "Unknown vote, please either get the player to change their vote" \
                                     " to 'yes' or 'no', or manually set it by adding the vote to the end of " \
                                     "this command e.g. '<LockVote yes'.")
                return
            except NotVotedError:
                await utility.deny_command(ctx, "Player has not voted yet, if needed you can manually fo this by " \
                                           "adding the vote to the end of this command e.g. '<LockVote yes'.")
                return
            await utility.finish_processing(ctx)
        else:
            await utility.deny_command(ctx, "You must be the Storyteller to lock a vote")

    async def LockNextVote(self, vote: str = None):
        nom = self.town_square.current_nomination
        players = reordered_players(nom, self.town_square)
        player = players[nom.player_index]
        if not vote:
            vote = nom.votes[player.id].vote.lower()
        if vote == not_voted_yet:
            raise NotVotedError
        if vote == "yes" or vote == "y":
            nom.votes[player.id].vote = confirmed_yes_vote
        elif vote == "no" or vote == "n":
            nom.votes[player.id].vote = confirmed_no_vote
        else:
            raise UnknownVoteError
        nom.player_index += 1
        if nom.player_index >= len(players):
            nom.finished = True
        await self.update_nom_message(nom)
        await self.log(f"The vote of {player.alias} has been locked on the nomination of {nom.nominee.alias}") 
    
    @commands.command(aliases=["TAutoLockVotes", "TALV"])
    async def ToggleAutoLockVotes(self, ctx: commands.context):
        await utility.start_processing(ctx)
        self.town_square.auto_lock_votes = not self.town_square.auto_lock_votes
        await utility.finish_processing(ctx)
        
class NominationView(nextcord.ui.View):
    def __init__(self, helper: utility.Helper, townsquare: TownSquare, emoji: Dict[str, nextcord.PartialEmoji]):
        super().__init__(timeout=60) # 1hr 
        self.helper = helper
        self.townsquare = townsquare
        self.emoji = emoji

    async def on_error(self, error: Exception, item: nextcord.ui.Item, interaction: nextcord.Interaction) -> None:
        traceback_buffer = io.StringIO()
        traceback.print_exception(type(error), error, error.__traceback__, file=traceback_buffer)
        traceback_text = traceback_buffer.getvalue()
        logging.exception(f"Ignoring exception in NominationView:\n{traceback_text}")
        await interaction.response.send_message(content="Issue registering your vote.", 
                                                ephemeral=True)

    @nextcord.ui.button(label="Yes", custom_id="Nom_Vote_Yes", style=nextcord.ButtonStyle.green)
    async def yes_callback(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        player = next((p for p in self.townsquare.players if p.id == interaction.user.id), None)
        if not player:
            await interaction.response.send_message(content="You are not in the townsquare, ask an ST to fix this",
                                                    ephemeral=True)
            return
        nom = self.townsquare.current_nomination
        if not nom or nom.finished:
            await interaction.response.send_message(content="This nominition has already been processed.",
                                                    ephemeral=True)
            return
        if nom.votes[player.id].vote in [confirmed_yes_vote, confirmed_no_vote]:
            await interaction.response.send_message(content="Your vote is already locked in and cannot be changed.",
                                                    ephemeral=True)
            return
        
        nom.votes[player.id] = Vote("Yes")
        await self.update_nomination_view(interaction.message)
        await interaction.response.send_message(content="Your vote has been registered as 'Yes'",
                                                ephemeral=True)
        log_thread = get(self.helper.GameChannel.threads, id=self.townsquare.log_thread)
        await log_thread.send((format_dt(utcnow()) + ": " + f"{player.alias} has set "
                               f"their vote on the nomination of {nom.nominee.alias} to 'Yes'")[:2000])

    @nextcord.ui.button(label="No", custom_id="Nom_Vote_No", style=nextcord.ButtonStyle.red)
    async def no_callback(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        player = next((p for p in self.townsquare.players if p.id == interaction.user.id), None)
        if not player:
            await interaction.response.send_message(content="You are not in the townsquare, ask an ST to fix this",
                                                    ephemeral=True)
            return
        nom = self.townsquare.current_nomination
        if not nom or nom.finished:
            await interaction.response.send_message(content="This nominition has already been processed.",
                                                    ephemeral=True)
            return
        if nom.votes[player.id].vote in [confirmed_yes_vote, confirmed_no_vote]:
            await interaction.response.send_message(content="Your vote is already locked in and cannot be changed.",
                                                    ephemeral=True)
            return
        
        nom.votes[player.id] = Vote("No")
        await self.update_nomination_view(interaction.message)
        await interaction.response.send_message(content="Your vote has been registered as 'No'",
                                                ephemeral=True)
        log_thread = get(self.helper.GameChannel.threads, id=self.townsquare.log_thread)
        await log_thread.send((format_dt(utcnow()) + ": " + f"{player.alias} has set "
                               f"their vote on the nomination of {nom.nominee.alias} to 'No'")[:2000])

    async def update_nomination_view(self, nomination_message: nextcord.Message):
        content, embed = format_nom_message(self.helper.PlayerRole, self.townsquare, self.townsquare.current_nomination, self.emoji)
        await nomination_message.edit(content=content, embed=embed)



async def setup(bot: commands.Bot):
    cog = Townsquare(bot, utility.Helper(bot))
    await cog.load_emoji()
    bot.add_cog(cog)
