"""Headless replay / difficulty tests for Task 3.

Run from the project root:
    python -m unittest discover -s tests -v
"""
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.game_engine import (GameEngine, GAME_OVER_INPUT_DELAY, DIFFICULTIES,
                              DEFAULT_DIFFICULTY, FPS)
from tests.test_game_over import key, hit_player
from tests.test_collision import bullet_below

WIDTH, HEIGHT = 600, 700


def snapshot(engine):
    """Every attribute of the engine as plain comparable values. Objects such as
    the player, grid, enemies and bullets are expanded into their own fields."""
    def plain(value):
        if isinstance(value, list):
            return [plain(v) for v in value]
        if hasattr(value, "__dict__"):
            return {k: plain(v) for k, v in vars(value).items()}
        return value

    skip = {"font", "big_font", "overlay", "sounds"}   # shared resources, kept on purpose
    return {k: plain(v) for k, v in vars(engine).items() if k not in skip}


def play_and_die(engine):
    """Dirty every piece of game state, then end the game and wait out the delay."""
    engine.handle_event(key(pygame.K_SPACE))          # bullet in flight + cooldown
    engine.player.move(-100, WIDTH)                   # player moved
    target = engine.enemy_grid.enemies[-1]
    engine.player_bullets.append(bullet_below(target))
    for _ in range(40):                               # grid moved, maybe dropped
        engine.update()
    engine.enemy_fire_chance = 0
    hit_player(engine)                                # game over + reason
    for _ in range(GAME_OVER_INPUT_DELAY):
        engine.update()


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_first_game_is_medium(self):
        engine = GameEngine(WIDTH, HEIGHT)
        self.assertEqual(engine.difficulty, DEFAULT_DIFFICULTY)
        self.assertEqual(engine.enemy_grid.speed, DIFFICULTIES["Medium"]["enemy_speed"])

    def test_restart_leaves_no_stale_state(self):
        # After a played game, restarting must equal a brand-new engine on that difficulty
        for k, name in ((pygame.K_1, "Easy"), (pygame.K_2, "Medium"), (pygame.K_3, "Hard")):
            random.seed(0)
            engine = GameEngine(WIDTH, HEIGHT)
            play_and_die(engine)
            self.assertTrue(engine.game_over)
            self.assertGreater(engine.score, 0)

            engine.handle_event(key(k))

            fresh = GameEngine(WIDTH, HEIGHT)
            fresh.reset(name)
            self.assertEqual(snapshot(engine), snapshot(fresh), name)

    def test_restart_five_times_in_a_row(self):
        engine = GameEngine(WIDTH, HEIGHT)
        for i in range(6):
            play_and_die(engine)
            engine.handle_event(key([pygame.K_1, pygame.K_2, pygame.K_3][i % 3]))
            self.assertFalse(engine.game_over)
            self.assertEqual(engine.score, 0)
            self.assertEqual(len(engine.enemy_grid.alive_enemies()), 32)

    def test_new_game_can_shoot_immediately(self):
        engine = GameEngine(WIDTH, HEIGHT)
        play_and_die(engine)
        engine.handle_event(key(pygame.K_2))
        engine.handle_event(key(pygame.K_SPACE))
        self.assertEqual(len(engine.player_bullets), 1)

    def test_fire_rate_matches_difficulty(self):
        # Total enemy shots per second should match the setting, not the enemy count
        for name, settings in DIFFICULTIES.items():
            random.seed(1)
            engine = GameEngine(WIDTH, HEIGHT)
            engine.reset(name)
            seconds = 300   # long sample so random spread stays well inside the delta
            for _ in range(seconds * FPS):
                engine._enemy_fire()
            rate = len(engine.enemy_bullets) / seconds
            self.assertAlmostEqual(rate, settings["shots_per_second"], delta=0.3, msg=name)

    def test_fire_rate_independent_of_enemies_alive(self):
        random.seed(2)
        engine = GameEngine(WIDTH, HEIGHT)
        for e in engine.enemy_grid.enemies[1:]:
            e.alive = False                      # one enemy left
        seconds = 300
        for _ in range(seconds * FPS):
            engine._enemy_fire()
        self.assertAlmostEqual(len(engine.enemy_bullets) / seconds, 2.0, delta=0.3)

    def test_no_fire_when_all_dead(self):
        engine = GameEngine(WIDTH, HEIGHT)
        engine.enemy_fire_chance = 1.0
        for e in engine.enemy_grid.enemies:
            e.alive = False
        engine._enemy_fire()
        self.assertEqual(engine.enemy_bullets, [])

    def test_clearing_the_grid_ends_the_game(self):
        engine = GameEngine(WIDTH, HEIGHT)
        engine.enemy_fire_chance = 0
        for e in engine.enemy_grid.enemies[:-1]:
            e.alive = False
        engine.player_bullets = [bullet_below(engine.enemy_grid.enemies[-1])]
        engine.update()
        self.assertTrue(engine.game_over)
        self.assertIn("win", engine.game_over_reason)


if __name__ == "__main__":
    unittest.main()
