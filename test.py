from nextcord.ext import commands
import json
import os

bot = commands.Bot(command_prefix="<")

@bot.command(name="createts")
async def createts(ctx):
    await ctx.send('')
    return

class Player():

    def __init__(self, ID):
        self.ID = ID
        self.alive = True
        self.can_vote = True
        self.banshee = False

    def toggle_marked_dead(self):
        self.alive = not self.alive

    def toggle_can_vote(self):
        self.can_vote = not self.can_vote
    
    def toggle_banshee_rights(self):
        self.banshee = not self.banshee

class Townsquare():
    def __init__(self):
        self.players = []
        self.sts = set()
        self.active_nom = (-1, -1) # blank nominator and nominee # livetext should only ever have one nom active at once


    # current sts
    def add_player(self, player):
        # convert player to discord ID and convert to Player object
        if not player in self.players:
            # give player role
            self.players.append(Player(player))
        else:
            pass # Error message because player is already in game
    
    # current sts
    def remove_player(self, player):
        # convert player to discord ID and convert to Player object
        if player in self.players:
            # take away player role
            self.players.append(Player(player))
        else:
            pass # Error message because player is not in game

    # current sts
    def set_up_townsquare(self, *args): # Technically pointless bc of how it's made but allows st to reorder players
        # check all the players are in the game
        # if they all are then change the order
        pass

    # current sts
    def add_st(self, st):
        # convert st to discord ID
        if not st in self.sts:
            # give st role
            self.sts.add(st)
        else:
            pass # Error message because person is already an st
    
    # mods / minions only
    def remove_st(self, st):
        # convert st to discord ID
        if st in self.sts:
            # take away sts role
            self.sts.remove(st)
        else:
            pass # Error message because person isn't a st

    # mods / sts only 
    def reset_ts(self):
        # prompt "are you sure, this will wipe all player and st data"
        for player in self.players:
            self.remove_player(player)
        for st in self.sts:
            self.remove_st(st)
        
    # runable by anyone if there is not already an st
    def claim_grim_livetext(self, st):
        if self.sts == set():
            self.add_st(st)
        else:
            pass # return error message because there is already an st

    # mods / sts only
    def close_nom(self):
        self.active_nom = (-1, -1)

    # mods / sts only
    def create_nom(self, nominator, nominee):
        # covert nominator and nominee to ID's and get their respective Player objects
        if nominator.alive == True or nominator.banshee == True:
            self.active_nom = (nominator, nominee)
        else:
            pass # Error message