"""Headless Game Over tests for Task 2.

Run from the project root:
    python -m unittest discover -s tests -v
"""
import contextlib
import io
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game.game_engine import GameEngine, GAME_OVER_INPUT_DELAY
from game.bullet import Bullet
from tests.test_collision import make_engine


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def hit_player(engine):
    """Put an enemy bullet just above the player and run one frame."""
    p = engine.player
    engine.enemy_bullets = [Bullet(p.center_x(), p.y - 16, direction=1)]
    engine.update()


class GameOverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.display.set_mode((600, 700))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_hit_sets_reason(self):
        engine = make_engine()
        hit_player(engine)
        self.assertTrue(engine.game_over)
        self.assertEqual(engine.game_over_reason, "You were hit")

    def test_bottom_sets_reason(self):
        engine = make_engine()
        engine.enemy_grid.enemies[-1].y = engine.player.y
        engine.update()
        self.assertTrue(engine.game_over)
        self.assertEqual(engine.game_over_reason, "Invaders reached the bottom")

    def test_first_reason_wins(self):
        # Hit and reached-bottom on the same frame: the hit is checked first
        engine = make_engine()
        engine.enemy_grid.enemies[-1].y = engine.player.y
        hit_player(engine)
        self.assertEqual(engine.game_over_reason, "You were hit")

    def test_no_shooting_after_game_over(self):
        engine = make_engine()
        hit_player(engine)
        engine.handle_event(key(pygame.K_SPACE))
        self.assertEqual(engine.player_bullets, [])

    def test_world_is_frozen(self):
        engine = make_engine()
        engine.enemy_grid.speed = 1.5
        hit_player(engine)
        xs = [e.x for e in engine.enemy_grid.enemies]
        for _ in range(10):
            engine.update()
        self.assertEqual(xs, [e.x for e in engine.enemy_grid.enemies])

    def quit_posted(self):
        return bool(pygame.event.get(pygame.QUIT))

    def test_keys_ignored_during_delay(self):
        engine = make_engine()
        hit_player(engine)
        pygame.event.clear()
        for k in (pygame.K_ESCAPE, pygame.K_q, pygame.K_1):
            engine.handle_event(key(k))
        self.assertFalse(self.quit_posted())
        self.assertTrue(engine.game_over)

    def test_quit_keys_post_quit_after_delay(self):
        for k in (pygame.K_q, pygame.K_ESCAPE):
            engine = make_engine()
            hit_player(engine)
            for _ in range(GAME_OVER_INPUT_DELAY):
                engine.update()
            pygame.event.clear()
            engine.handle_event(key(pygame.K_SPACE))   # other keys do nothing
            self.assertFalse(self.quit_posted())
            engine.handle_event(key(k))
            self.assertTrue(self.quit_posted())

    def test_render_draws_without_printing(self):
        engine = make_engine()
        hit_player(engine)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            for _ in range(GAME_OVER_INPUT_DELAY + 1):
                engine.update()
                engine.render(self.screen)
        self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
