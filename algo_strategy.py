import gamelib
import random
import math
import warnings
from sys import maxsize

"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

Additional functions are made available by importing the AdvancedGameState 
class from gamelib/advanced.py as a replacement for the regular GameState class 
in game.py.

You can analyze action frames by modifying algocore.py.

The GameState.map object can be manually manipulated to create hypothetical 
board states. Though, we recommended making a copy of the map to preserve 
the actual current map state.
"""

"""
Because we'll lose 25% of our bits every round, it's not beneficial to
hoard more than 24 bits
"""
BATCH_PINGS_NUM_CAP = 24

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        random.seed()

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        global FILTER, ENCRYPTOR, DESTRUCTOR, PING, EMP, SCRAMBLER
        FILTER = config["unitInformation"][0]["shorthand"]
        ENCRYPTOR = config["unitInformation"][1]["shorthand"]
        DESTRUCTOR = config["unitInformation"][2]["shorthand"]
        PING = config["unitInformation"][3]["shorthand"]
        EMP = config["unitInformation"][4]["shorthand"]
        SCRAMBLER = config["unitInformation"][5]["shorthand"]
        # Batch ping threshold
        self.batch_ping_num = 10
        # If we sent out our ping batch last round
        self.sent_pings_last_round = False
        # Enemy health before we sent out our last ping batch
        self.enemy_health_before_attack = 30

    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        #game_state.suppress_warnings(True)  #Uncomment this line to suppress warnings.
        # Call our strategy function to perform our moves
        self.battle_strategy(game_state)
        game_state.submit_turn()

    def battle_strategy(self, game_state):
        """
        For every round, we first check if there's any missing spot in our
        defense base, then we depoly our attacking unit
        """
        # Check if our last attack succeed
        self.check_last_attack(game_state)
        # Build or fix our defense base
        self.build_base(game_state)
        # Deploy our attacking units
        self.deploy_attackers(game_state)

    def check_last_attack(self, game_state):
        """
        Check if our last attack succeeded and adjust the batch pings number
        accordingly
        """
        if self.sent_pings_last_round:  # If we deployed attack last round
            if game_state.enemy_health >= self.enemy_health_before_attack:
                # Enemy still has the same health. Our attack didn't succeed
                self.batch_ping_num += 4  # Add 4 more pings next time
                gamelib.debug_write(('Last attack failed. Next batch: '
                                     '{}'.format(self.batch_ping_num)))
        # Reset the flag
        self.sent_pings_last_round = False

    def build_base(self, game_state):
        """
        Every turn we go through our base setup and see if there's any destroyed
        or unbuilt part.
        """
        # We use these filters to form a funnel
        funnel_walls = [
            [0, 13], [1, 13], [2, 13], [3, 13], [24, 13], [25, 13], [26, 13],
            [27, 13], [4, 12], [23, 12], [5, 11], [22, 11], [6, 10], [21, 10],
            [7, 9], [20, 9], [8, 8], [19, 8], [9, 7], [10, 7], [11, 7],
            [12, 7], [15, 7], [16, 7], [17, 7], [18, 7]
        ]
        for loc in funnel_walls:
            if game_state.can_spawn(FILTER, loc):
                gamelib.debug_write('Add funnel wall at {}'.format(loc))
                game_state.attempt_spawn(FILTER, loc)
        # Our basic defense line, placed at the bottom and two corners
        basic_destructors = [
            [12, 6], [15, 6], [12, 5], [15, 5], [12, 4], [15, 4], [3, 12], [24, 12]
        ]
        for loc in basic_destructors:
            if game_state.can_spawn(DESTRUCTOR, loc):
                gamelib.debug_write('Add basic desctructor at {}'.format(loc))
                game_state.attempt_spawn(DESTRUCTOR, loc)
        # Our bottom encryptor will boost our out going units
        bottom_encryptors = [[12, 3], [15, 3], [12, 2], [15, 2]]
        for loc in bottom_encryptors:
            if game_state.can_spawn(ENCRYPTOR, loc):
                gamelib.debug_write('Add bottom encryptor at {}'.format(loc))
                game_state.attempt_spawn(ENCRYPTOR, loc)
        # Add some extra destructors to protect our wings
        wing_destructors = [
            [5, 10], [22, 10], [7, 8], [20, 8], [9, 6], [18, 6], [1, 12], [26, 12]
        ]
        for loc in wing_destructors:
            if game_state.can_spawn(DESTRUCTOR, loc):
                gamelib.debug_write('Add wing desctructor at {}'.format(loc))
                game_state.attempt_spawn(DESTRUCTOR, loc)

    def deploy_attackers(self, game_state):
        """
        Our attacking strategy is simple, hoard bits until we can send units
        in batch
        """
        # First we deploy 2 scramblers to kill units that come from the front
        gamelib.debug_write('Deploy 2 sweeper scramblers')
        scramblers = [[13, 0], [14, 0]]
        for each in scramblers:
            if game_state.can_spawn(SCRAMBLER, each):
                game_state.attempt_spawn(SCRAMBLER, each)
        # Hoard bits until we can send out a big batch of pings
        pings = [[13, 0], [14, 0]]
        # We're sending out a batch of pings
        cur_batch_num = min(self.batch_ping_num, BATCH_PINGS_NUM_CAP)
        if (game_state.get_resource(game_state.BITS) >= cur_batch_num):
            # Help track if this attack succeed
            self.enemy_health_before_attack = game_state.enemy_health
            self.sent_pings_last_round = True
            deploy_loc = pings[random.randint(0, 1)]  # Pick a spot to deploy
            if game_state.can_spawn(PING, deploy_loc, cur_batch_num):
                msg = 'Deploy {} pings at {}'.format(cur_batch_num, deploy_loc)
                gamelib.debug_write(msg)
                game_state.attempt_spawn(PING, deploy_loc, cur_batch_num)


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
