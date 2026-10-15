import pygame
import random
from .player import Player
from .enemy import EnemyGrid
from .bullet import Bullet
from .sound_manager import SoundManager

# Game Engine

WHITE = (255, 255, 255)
GREEN = (0, 200, 0)
RED = (220, 60, 60)

FPS = 60  # main.py runs the loop at this rate; fire rates below are converted per frame

# Frames (~0.5 s at 60 FPS) the Game Over screen ignores keys, so a player
# still mashing Space doesn't dismiss it by accident
GAME_OVER_INPUT_DELAY = 30

# Difficulty settings - tune here.
#   enemy_speed:      px per frame the grid moves sideways (it drops 20 px at each edge)
#   shots_per_second: average enemy shots per second in total, whatever the number alive
DIFFICULTIES = {
    "Easy":   {"enemy_speed": 1.0, "shots_per_second": 1.0},
    "Medium": {"enemy_speed": 1.5, "shots_per_second": 2.0},
    "Hard":   {"enemy_speed": 2.5, "shots_per_second": 3.0},
}
DEFAULT_DIFFICULTY = "Medium"

# Keys on the Game Over screen that start a new game (number row or keypad)
DIFFICULTY_KEYS = {
    pygame.K_1: "Easy",   pygame.K_KP1: "Easy",
    pygame.K_2: "Medium", pygame.K_KP2: "Medium",
    pygame.K_3: "Hard",   pygame.K_KP3: "Hard",
}

class GameEngine:
    def __init__(self, width, height):
        self.width = width
        self.height = height

        # Resources that never change between games
        self.font = pygame.font.SysFont("Arial", 30)
        self.big_font = pygame.font.SysFont("Arial", 64, bold=True)

        # Dark see-through layer drawn over the frozen last frame on Game Over
        self.overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        self.overlay.fill((0, 0, 0, 170))

        self.sounds = SoundManager()   # built once; silent if there is no audio device

        self.reset(DEFAULT_DIFFICULTY)

    def reset(self, difficulty):
        """Start a brand-new game. Every attribute that changes during play is set here."""
        settings = DIFFICULTIES[difficulty]
        self.difficulty = difficulty

        self.player = Player(self.width // 2 - 20, self.height - 50, 40, 20)
        self.enemy_grid = EnemyGrid(self.width, speed=settings["enemy_speed"])

        self.player_bullets = []
        self.enemy_bullets = []
        self._shoot_cooldown = 0
        # Chance per frame that one random enemy fires
        self.enemy_fire_chance = settings["shots_per_second"] / FPS

        self.score = 0
        self.game_over = False
        self.game_over_reason = None   # text shown on the Game Over screen
        self._game_over_frames = 0     # frames since Game Over, for the input delay

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return

        if self.game_over:
            if self._game_over_frames < GAME_OVER_INPUT_DELAY:
                return
            if event.key in DIFFICULTY_KEYS:
                self.reset(DIFFICULTY_KEYS[event.key])
            elif event.key in (pygame.K_q, pygame.K_ESCAPE):
                # Let main.py's loop see a normal QUIT and shut down cleanly
                pygame.event.post(pygame.event.Event(pygame.QUIT))
            return

        if event.key == pygame.K_SPACE:
            if self._shoot_cooldown <= 0:
                bullet_x = self.player.center_x() - 2
                self.player_bullets.append(Bullet(bullet_x, self.player.y, direction=-1))
                self._shoot_cooldown = 15
                self.sounds.play_fire()

    def handle_input(self):
        if self.game_over:
            return
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.player.move(-self.player.speed, self.width)
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.player.move(self.player.speed, self.width)

    def update(self):
        if self.game_over:
            self._game_over_frames += 1
            return

        if self._shoot_cooldown > 0:
            self._shoot_cooldown -= 1

        self.enemy_grid.move()
        self._enemy_fire()

        player_paths = self._move_and_sweep(self.player_bullets)
        enemy_paths = self._move_and_sweep(self.enemy_bullets)

        # Player bullets vs enemies. Build a new list instead of removing
        # from the one being iterated (that skipped the next bullet).
        remaining = []
        for bullet, path in player_paths:
            enemy = self._first_enemy_hit(path)
            if enemy:
                enemy.alive = False  # dead enemies drop out of alive_enemies(), so each scores once
                self.score += 1
                self.sounds.play_enemy_destroyed()
            else:
                remaining.append(bullet)
        # Off-screen check comes after collisions so a fast bullet can still
        # hit the top row on the frame it leaves the screen
        self.player_bullets = [b for b in remaining if not b.off_screen(self.height)]

        # Enemy bullets vs player, same pattern
        player_rect = self.player.rect()
        remaining = []
        for bullet, path in enemy_paths:
            if path.colliderect(player_rect):
                self._end_game("You were hit")
            else:
                remaining.append(bullet)
        self.enemy_bullets = [b for b in remaining if not b.off_screen(self.height)]

        if self.enemy_grid.reached_bottom(self.player.y):
            self._end_game("Invaders reached the bottom")
        elif not self.enemy_grid.alive_enemies():
            self._end_game("You win - all invaders destroyed")

    def _enemy_fire(self):
        """At most one shot per frame, from a random alive enemy, so the total
        fire rate stays the same however many enemies are left."""
        alive = self.enemy_grid.alive_enemies()
        if alive and random.random() < self.enemy_fire_chance:
            enemy = random.choice(alive)
            bullet_x = enemy.x + enemy.width // 2
            self.enemy_bullets.append(Bullet(bullet_x, enemy.y + enemy.height, direction=1))

    def _end_game(self, reason):
        """Single place the game switches to Game Over. The first reason wins
        if two things end the game on the same frame."""
        if self.game_over:
            return
        self.game_over = True
        self.game_over_reason = reason
        self._game_over_frames = 0
        # Plays once: the guard above blocks repeats, reset() re-arms it
        self.sounds.play_game_over()

    def _move_and_sweep(self, bullets):
        """Move each bullet and return (bullet, path) pairs, where path is the
        rect covering everywhere the bullet travelled this frame. Testing the
        path instead of the end position stops fast bullets tunnelling."""
        paths = []
        for bullet in bullets:
            start = bullet.rect()
            bullet.move()
            paths.append((bullet, start.union(bullet.rect())))
        return paths

    def _first_enemy_hit(self, path):
        """Return the alive enemy a player bullet reaches first along `path`, or None.
        Player bullets travel upward, so the first one reached is the lowest."""
        hits = [e for e in self.enemy_grid.alive_enemies() if path.colliderect(e.rect())]
        if not hits:
            return None
        return max(hits, key=lambda e: e.y + e.height)

    def render(self, screen):
        pygame.draw.rect(screen, GREEN, self.player.rect())

        for enemy in self.enemy_grid.alive_enemies():
            pygame.draw.rect(screen, WHITE, enemy.rect())

        for bullet in self.player_bullets:
            pygame.draw.rect(screen, WHITE, bullet.rect())
        for bullet in self.enemy_bullets:
            pygame.draw.rect(screen, RED, bullet.rect())

        score_text = self.font.render(f"Score: {self.score}", True, WHITE)
        screen.blit(score_text, (10, 10))
        difficulty_text = self.font.render(self.difficulty, True, WHITE)
        screen.blit(difficulty_text, difficulty_text.get_rect(topright=(self.width - 10, 10)))

        if self.game_over:
            self._render_game_over(screen)

    def _render_game_over(self, screen):
        screen.blit(self.overlay, (0, 0))

        cy = self.height // 2
        self._draw_centered(screen, "GAME OVER", self.big_font, RED, cy - 120)
        self._draw_centered(screen, f"Final score: {self.score}", self.font, WHITE, cy - 40)
        self._draw_centered(screen, self.game_over_reason, self.font, WHITE, cy)

        # Only show the options once keys are accepted, so it never looks unresponsive
        if self._game_over_frames >= GAME_OVER_INPUT_DELAY:
            self._draw_centered(screen, "Play again:", self.font, WHITE, cy + 70)
            self._draw_centered(screen, "1 = Easy    2 = Medium    3 = Hard", self.font, WHITE, cy + 110)
            self._draw_centered(screen, "Q / Esc = Exit", self.font, WHITE, cy + 160)

    def _draw_centered(self, screen, text, font, color, center_y):
        surface = font.render(text, True, color)
        screen.blit(surface, surface.get_rect(center=(self.width // 2, center_y)))
