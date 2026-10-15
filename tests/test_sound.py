"""Headless sound tests for Task 4 (SDL_AUDIODRIVER=dummy - nothing is heard).

Run from the project root:
    python -m unittest discover -s tests -v
"""
import array
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import sound_manager
from game.sound_manager import SoundManager
from game.game_engine import GAME_OVER_INPUT_DELAY
from tests.test_collision import make_engine, bullet_below
from tests.test_game_over import key, hit_player

SOUNDS = {  # name -> (intended seconds, volume constant)
    "fire": (0.12, sound_manager.FIRE_VOLUME),
    "enemy_destroyed": (0.25, sound_manager.ENEMY_DESTROYED_VOLUME),
    "game_over": (1.2, sound_manager.GAME_OVER_VOLUME),
}


class SoundManagerTests(unittest.TestCase):
    def tearDown(self):
        pygame.quit()

    def test_sounds_built_with_right_length(self):
        # Several mixer formats: a wrong channel count or rate would change the length
        for freq, channels in ((44100, 2), (22050, 1), (48000, 2)):
            pygame.mixer.quit()
            pygame.mixer.init(frequency=freq, size=-16, channels=channels)
            manager = SoundManager()
            self.assertTrue(manager.enabled)
            for name, (seconds, _) in SOUNDS.items():
                sound = getattr(manager, name)
                self.assertGreater(sound.get_length(), 0)
                self.assertAlmostEqual(sound.get_length(), seconds, delta=0.005,
                                       msg=f"{name} at {freq} Hz x{channels}")

    def test_no_clipping_and_silent_edges(self):
        pygame.mixer.init(frequency=44100, size=-16, channels=2)
        manager = SoundManager()
        for name, (_, volume) in SOUNDS.items():
            samples = array.array("h", getattr(manager, name).get_raw())
            self.assertLessEqual(max(abs(v) for v in samples), volume * 32767, name)
            # Fade in/out: first and last frames are (near) silent, so no clicks
            self.assertLess(abs(samples[0]), 50, name)
            self.assertLess(abs(samples[-1]), 50, name)

    def test_stereo_is_interleaved(self):
        pygame.mixer.init(frequency=44100, size=-16, channels=2)
        samples = array.array("h", SoundManager().fire.get_raw())
        self.assertEqual(samples[0::2], samples[1::2])   # left == right

    def test_no_audio_device_is_silent_noop(self):
        pygame.mixer.quit()
        with mock.patch("pygame.mixer.init", side_effect=pygame.error("no audio device")):
            manager = SoundManager()
        self.assertFalse(manager.enabled)
        manager.play_fire()
        manager.play_enemy_destroyed()
        manager.play_game_over()

    def test_mixer_module_missing_is_silent_noop(self):
        # pygame built without SDL_mixer: any pygame.mixer call raises NotImplementedError
        with mock.patch("pygame.mixer.get_init", side_effect=NotImplementedError):
            manager = SoundManager()
            self.assertFalse(manager.enabled)
            manager.play_fire()
            manager.play_game_over()

    def test_mixer_closed_after_build_does_not_raise(self):
        manager = SoundManager()
        pygame.mixer.quit()
        manager.play_fire()
        manager.play_enemy_destroyed()
        manager.play_game_over()

    def test_engine_runs_without_audio(self):
        pygame.init()
        pygame.mixer.quit()
        with mock.patch("pygame.mixer.init", side_effect=pygame.error("no audio device")):
            engine = make_engine()
        engine.handle_event(key(pygame.K_SPACE))
        hit_player(engine)
        self.assertTrue(engine.game_over)


class CountingSounds:
    """Stand-in for SoundManager that counts calls instead of playing."""
    def __init__(self):
        self.fire = self.destroyed = self.game_over = 0

    def play_fire(self):
        self.fire += 1

    def play_enemy_destroyed(self):
        self.destroyed += 1

    def play_game_over(self):
        self.game_over += 1


class SoundHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.engine = make_engine()
        self.sounds = self.engine.sounds = CountingSounds()

    def test_fire_only_when_bullet_created(self):
        self.engine.handle_event(key(pygame.K_SPACE))
        self.engine.handle_event(key(pygame.K_SPACE))   # blocked by cooldown
        self.assertEqual(len(self.engine.player_bullets), 1)
        self.assertEqual(self.sounds.fire, 1)

    def test_destroyed_once_per_enemy(self):
        bottom_row = self.engine.enemy_grid.enemies[-8:]
        target = bottom_row[0]
        self.engine.player_bullets = [bullet_below(e) for e in bottom_row]
        self.engine.player_bullets.append(bullet_below(target, gap=6))  # second bullet, same enemy
        self.engine.update()
        self.assertEqual(self.engine.score, 8)
        self.assertEqual(self.sounds.destroyed, 8)

    def test_game_over_plays_exactly_once(self):
        hit_player(self.engine)
        self.engine.enemy_grid.enemies[-1].y = self.engine.player.y   # second end reason
        for _ in range(GAME_OVER_INPUT_DELAY + 60):
            self.engine.update()
            self.engine.handle_event(key(pygame.K_SPACE))
        self.assertEqual(self.sounds.game_over, 1)
        self.assertEqual(self.sounds.fire, 0)

    def test_game_over_rearmed_after_restart(self):
        hit_player(self.engine)
        for _ in range(GAME_OVER_INPUT_DELAY):
            self.engine.update()
        self.engine.handle_event(key(pygame.K_2))   # new game
        self.engine.enemy_fire_chance = 0
        self.engine.enemy_grid.speed = 0
        hit_player(self.engine)
        self.assertEqual(self.sounds.game_over, 2)


if __name__ == "__main__":
    unittest.main()
