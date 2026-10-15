"""Sound effects generated in code - no audio files, only the standard library and pygame."""
import array
import math
import random

import pygame

# Peak loudness of each sound as a fraction of full scale (0.0 - 1.0).
# Kept low so a few sounds overlapping in the mixer still stay below full scale.
FIRE_VOLUME = 0.15
ENEMY_DESTROYED_VOLUME = 0.30
GAME_OVER_VOLUME = 0.25

ATTACK_SECONDS = 0.005     # fade-in, stops a click at the start
FADE_OUT_SECONDS = 0.04    # default fade-out, stops a click at the end

# Mixer sample format from pygame.mixer.get_init() -> (array typecode, full scale, value for silence)
SAMPLE_FORMATS = {
    -16: ("h", 32767, 0),       # signed 16-bit - pygame's default
    16:  ("H", 32767, 32768),   # unsigned 16-bit
    -8:  ("b", 127, 0),         # signed 8-bit
    8:   ("B", 127, 128),       # unsigned 8-bit
}


class SoundManager:
    def __init__(self):
        """Build all sounds once. If there is no usable audio device, every
        play_* method quietly does nothing."""
        self.fire = None
        self.enemy_destroyed = None
        self.game_over = None

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.frequency, self.format, self.channels = pygame.mixer.get_init()
            if self.format not in SAMPLE_FORMATS:
                return  # unusual format we don't generate - stay silent

            # Short high "pew": square wave sliding down
            self.fire = self._build(1200, 500, 0.12, FIRE_VOLUME, wave="square")
            # Quick crunch: falling tone mixed with noise, dying away
            self.enemy_destroyed = self._build(500, 80, 0.25, ENEMY_DESTROYED_VOLUME,
                                               noise=0.6, decay=True)
            # Long low "wah": slow slide down with a long fade
            self.game_over = self._build(400, 70, 1.2, GAME_OVER_VOLUME, wave="square",
                                         fade_seconds=0.4)
        except (pygame.error, NotImplementedError):
            # No audio device or mixer failed (pygame.error), or pygame was built
            # without its mixer module (NotImplementedError) - stay silent
            pass

    @property
    def enabled(self):
        return self.fire is not None

    def play_fire(self):
        self._play(self.fire)

    def play_enemy_destroyed(self):
        self._play(self.enemy_destroyed)

    def play_game_over(self):
        self._play(self.game_over)

    def _play(self, sound):
        # Check the mixer is still running: in pygame 2.6 playing a Sound after
        # mixer.quit() crashes the whole process instead of raising pygame.error
        if sound is None or not pygame.mixer.get_init():
            return
        try:
            sound.play()
        except pygame.error:
            pass  # any other mixer problem - just skip the sound

    def _build(self, start_hz, end_hz, seconds, volume, wave="sine", noise=0.0,
               decay=False, fade_seconds=FADE_OUT_SECONDS):
        """Generate a Sound that slides from start_hz to end_hz.

        noise:  0-1, how much white noise to mix in (for explosion-like sounds)
        decay:  if True the whole sound fades steadily, not just the last moment
        """
        typecode, full_scale, silence = SAMPLE_FORMATS[self.format]
        rate = self.frequency
        n = int(seconds * rate)
        attack = max(1, int(ATTACK_SECONDS * rate))
        fade = max(1, int(fade_seconds * rate))
        rng = random.Random(0)   # own RNG: same sound every run, game's random untouched

        samples = array.array(typecode)
        phase = 0.0
        for i in range(n):
            t = i / n
            # Add up phase step by step so the pitch slides smoothly
            phase += 2 * math.pi * (start_hz + (end_hz - start_hz) * t) / rate
            value = math.sin(phase)
            if wave == "square":
                value = 1.0 if value >= 0 else -1.0
            value = value * (1 - noise) + rng.uniform(-1, 1) * noise   # stays within -1..1

            envelope = min(1.0, i / attack, (n - 1 - i) / fade)
            if decay:
                envelope *= 1 - t

            level = int(value * envelope * volume * full_scale) + silence
            # Same sample on every channel; stereo needs them interleaved L, R, L, R...
            samples.extend([level] * self.channels)

        return pygame.mixer.Sound(buffer=samples.tobytes())
