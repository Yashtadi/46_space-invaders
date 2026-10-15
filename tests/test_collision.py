"""Headless collision tests for Task 1.

Run from the project root:
    python -m unittest discover -s tests -v
"""
import os
import unittest

# No window or audio device needed - must be set before pygame is imported
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.game_engine import GameEngine
from game.bullet import Bullet

WIDTH, HEIGHT = 600, 700


def make_engine():
    """Engine with a frozen enemy grid and no enemy fire, so every frame is predictable."""
    engine = GameEngine(WIDTH, HEIGHT)
    engine.enemy_fire_chance = 0
    engine.enemy_grid.speed = 0
    return engine


def bullet_below(enemy, speed=8, gap=4):
    """Player bullet centred under `enemy`, `gap` px below it, so it reaches the enemy after one move."""
    x = enemy.x + enemy.width // 2 - 2
    return Bullet(x, enemy.y + enemy.height + gap, speed=speed, direction=-1)


class PlayerBulletTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_n_bullets_on_n_enemies_same_frame(self):
        # Rapid fire / several hits at once: every bullet must register in the same frame
        engine = make_engine()
        bottom_row = engine.enemy_grid.enemies[-8:]
        engine.player_bullets = [bullet_below(e) for e in bottom_row]

        engine.update()

        self.assertEqual(sum(not e.alive for e in bottom_row), 8)
        self.assertEqual(engine.score, 8)
        self.assertEqual(engine.player_bullets, [])

    def test_fast_bullet_does_not_tunnel(self):
        # Speed 50 jumps past a 30 px enemy in one frame (overlap window is 30 + 12 = 42 px)
        engine = make_engine()
        target = engine.enemy_grid.enemies[-1]
        for e in engine.enemy_grid.enemies:
            e.alive = e is target
        bullet = Bullet(target.x + 18, target.y + target.height + 1, speed=50, direction=-1)
        engine.player_bullets = [bullet]

        engine.update()

        self.assertFalse(target.alive)
        self.assertEqual(engine.score, 1)

    def test_fast_bullet_hits_nearest_enemy_first(self):
        # A path crossing two rows must kill the lower (first reached) enemy, not the one it lands on
        engine = make_engine()
        lower = engine.enemy_grid.enemies[24]   # row 3, col 0
        upper = engine.enemy_grid.enemies[16]   # row 2, col 0
        engine.player_bullets = [Bullet(lower.x + 18, lower.y + lower.height + 1, speed=100, direction=-1)]

        engine.update()

        self.assertFalse(lower.alive)
        self.assertTrue(upper.alive)
        self.assertEqual(sum(not e.alive for e in engine.enemy_grid.enemies), 1)

    def test_two_bullets_one_enemy_scores_once(self):
        # Each enemy scores once; the second bullet survives and keeps flying
        engine = make_engine()
        target = engine.enemy_grid.enemies[-1]
        engine.player_bullets = [bullet_below(target), bullet_below(target, gap=6)]

        engine.update()

        self.assertFalse(target.alive)
        self.assertEqual(engine.score, 1)
        self.assertEqual(len(engine.player_bullets), 1)

    def test_bullet_in_gap_passes_between_enemies(self):
        # The 15 px gap between columns is a legitimate miss, not a bug
        engine = make_engine()
        left = engine.enemy_grid.enemies[24]
        gap_x = left.x + left.width + 5
        bullet = Bullet(gap_x, left.y + left.height + 4, direction=-1)
        engine.player_bullets = [bullet]

        engine.update()

        self.assertEqual(engine.score, 0)
        self.assertEqual(engine.player_bullets, [bullet])

    def test_off_screen_bullets_are_removed(self):
        engine = make_engine()
        engine.player_bullets = [Bullet(5, 2, direction=-1)]   # far left column, no enemy there

        engine.update()

        self.assertEqual(engine.player_bullets, [])


class EnemyBulletTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_enemy_bullet_hits_player(self):
        engine = make_engine()
        p = engine.player
        engine.enemy_bullets = [Bullet(p.center_x(), p.y - 12 - 4, direction=1)]

        engine.update()

        self.assertTrue(engine.game_over)

    def test_fast_enemy_bullet_does_not_tunnel_through_player(self):
        # Player is 20 px tall, so speed 50 would skip over it without a swept test
        engine = make_engine()
        p = engine.player
        engine.enemy_bullets = [Bullet(p.center_x(), p.y - 12 - 1, speed=50, direction=1)]

        engine.update()

        self.assertTrue(engine.game_over)


if __name__ == "__main__":
    unittest.main()
