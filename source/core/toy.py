"""The Eddy Toy — pure physics for the one un-harnessed room.

A quiet pond of current. Pokes spawn eddies; eddies drift, bump,
and occasionally merge into one big wobbling eddy that cycles the
disco colors. No score, no timer, no persistence, no telemetry:
this module does no I/O, holds no state between calls beyond the
list it is handed, and is never wired to the memory service or the
floor — by construction, not by policy.

The step function is pure (positions, velocities, an injected
random source) so the pond can be tested headlessly.
"""
import math
import random as _random

MAX_EDDIES = 24          # housekeeping cap, not a rule of the game
BIG_RADIUS = 38.0        # at this size an eddy goes disco
MERGE_OVERLAP = 0.45     # centers closer than this fraction of the
                         # summed radii may merge on a bump
DISCO = [
    (0.93, 0.27, 0.38),  # disco pink
    (0.98, 0.65, 0.20),  # disco amber
    (0.35, 0.85, 0.45),  # disco green
    (0.25, 0.55, 0.95),  # disco blue
    (0.65, 0.40, 0.95),  # disco violet
    (0.95, 0.90, 0.35),  # disco gold
]
POND = (0.35, 0.55, 0.75)  # the quiet color of un-merged water


class Eddy:
    __slots__ = ("x", "y", "vx", "vy", "r", "spin", "hue", "phase")

    def __init__(self, x, y, vx, vy, r, spin, hue=0.0):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.r = r
        self.spin = spin        # -1..1, which way it turns
        self.hue = hue          # disco palette offset for big eddies
        self.phase = 0.0        # wobble clock

    @property
    def big(self):
        return self.r >= BIG_RADIUS

    def draw_radius(self):
        """Big eddies wobble; small ones hold their circle."""
        if self.big:
            return self.r * (1.0 + 0.07 * math.sin(self.phase))
        return self.r

    def color(self, t):
        """Disco colors cycle for the big merged eddy; the rest of
        the pond stays pond-colored."""
        if self.big:
            idx = int(t * 1.5 + self.hue) % len(DISCO)
            return DISCO[idx]
        return POND


def spawn(x, y, rng=None):
    """A poke becomes an eddy: modest size, a gentle drift, a spin."""
    rng = rng or _random
    angle = rng.uniform(0, 2 * math.pi)
    speed = rng.uniform(4.0, 14.0)  # px per second — a calm pond
    return Eddy(x=x, y=y,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                r=rng.uniform(13.0, 24.0),
                spin=rng.choice((-1.0, 1.0)) * rng.uniform(0.4, 1.0),
                hue=rng.uniform(0, len(DISCO)))


def _merge(a, b):
    """Two eddies become one: area adds, motion averages by area,
    the spin of the larger carries."""
    area_a, area_b = a.r * a.r, b.r * b.r
    total = area_a + area_b
    merged = Eddy(
        x=(a.x * area_a + b.x * area_b) / total,
        y=(a.y * area_a + b.y * area_b) / total,
        vx=(a.vx * area_a + b.vx * area_b) / total,
        vy=(a.vy * area_a + b.vy * area_b) / total,
        r=math.sqrt(total) * 1.03,
        spin=a.spin if area_a >= area_b else b.spin,
        hue=a.hue if area_a >= area_b else b.hue,
    )
    merged.phase = max(a.phase, b.phase)
    return merged


def step(eddies, width, height, dt, rng=None):
    """Advance the pond by dt seconds inside a width x height box.

    Drift, wall bounce, bumps (a simple normal-component exchange),
    and the occasional merge when two eddies meet deep enough.
    Returns the new list; the input list is not mutated.
    """
    rng = rng or _random
    out = [Eddy(e.x, e.y, e.vx, e.vy, e.r, e.spin, e.hue)
           for e in eddies]
    for e in out:
        e.phase += dt * 2.0
        e.x += e.vx * dt
        e.y += e.vy * dt
        if e.x < e.r:
            e.x, e.vx = e.r, abs(e.vx)
        elif e.x > width - e.r:
            e.x, e.vx = width - e.r, -abs(e.vx)
        if e.y < e.r:
            e.y, e.vy = e.r, abs(e.vy)
        elif e.y > height - e.r:
            e.y, e.vy = height - e.r, -abs(e.vy)

    merged_away = set()
    result = []
    for i, a in enumerate(out):
        if i in merged_away:
            continue
        for j in range(i + 1, len(out)):
            if j in merged_away:
                continue
            b = out[j]
            dx, dy = b.x - a.x, b.y - a.y
            dist = math.hypot(dx, dy)
            if dist == 0 or dist >= a.r + b.r:
                continue
            if dist < (a.r + b.r) * MERGE_OVERLAP \
                    and a.r + b.r <= 95.0 and rng.random() < 0.5:
                a = _merge(a, b)
                merged_away.add(j)
                continue
            # A bump: exchange the velocity components along the
            # line of centers, then ease the overlap apart.
            nx, ny = dx / dist, dy / dist
            rel = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
            if rel < 0:
                a.vx += rel * nx
                a.vy += rel * ny
                b.vx -= rel * nx
                b.vy -= rel * ny
            push = (a.r + b.r - dist) / 2.0
            a.x -= nx * push
            a.y -= ny * push
            b.x += nx * push
            b.y += ny * push
        result.append(a)
    return result


def poke(eddies, x, y, rng=None):
    """Add one eddy at a poke, capping the pond by folding the
    oldest eddy into the newest (housekeeping, not losing)."""
    out = list(eddies)
    out.append(spawn(x, y, rng=rng))
    while len(out) > MAX_EDDIES:
        out[1] = _merge(out[0], out[1])
        out.pop(0)
    return out
