"""Game logic for the five mini-games (UI lives in ui/minigames.py).

All puzzles are self-contained simulations - the "firewalls", "ciphers" and
"networks" are fictional constructs created here.
"""
from __future__ import annotations

import heapq
import itertools
import random
import string
from dataclasses import dataclass, field

SYMBOLS = ["◆", "▲", "●", "■", "✚", "★", "⬢", "✖"]


# =====================================================================
# A) Firewall puzzle - Mastermind style symbol combination
# =====================================================================
class FirewallPuzzle:
    def __init__(self, symbols: int = 6, length: int = 4, attempts: int = 6,
                 rng: random.Random | None = None, reveal_one: bool = False, name: str = "FIREWALL"):
        rng = rng or random.Random()
        self.symbols = min(symbols, len(SYMBOLS))
        self.length = length
        self.max_attempts = attempts
        self.name = name
        self.secret = [rng.randrange(self.symbols) for _ in range(length)]
        self.history: list[tuple[list[int], int, int]] = []
        self.revealed: dict[int, int] = {}
        if reveal_one:
            idx = rng.randrange(length)
            self.revealed[idx] = self.secret[idx]

    @property
    def attempts_left(self) -> int:
        return self.max_attempts - len(self.history)

    @property
    def solved(self) -> bool:
        return bool(self.history) and self.history[-1][1] == self.length

    @property
    def failed(self) -> bool:
        return not self.solved and self.attempts_left <= 0

    def guess(self, seq: list[int]) -> tuple[int, int]:
        if len(seq) != self.length:
            raise ValueError("wrong guess length")
        exact = sum(1 for a, b in zip(seq, self.secret) if a == b)
        remaining_secret = [b for a, b in zip(seq, self.secret) if a != b]
        remaining_guess = [a for a, b in zip(seq, self.secret) if a != b]
        misplaced = 0
        for sym in remaining_guess:
            if sym in remaining_secret:
                remaining_secret.remove(sym)
                misplaced += 1
        self.history.append((list(seq), exact, misplaced))
        return exact, misplaced


# =====================================================================
# B) Encryption puzzle - simulated ciphers
# =====================================================================
def caesar(text: str, shift: int) -> str:
    out = []
    for ch in text:
        if ch.isalpha() and ch.isascii():
            base = ord("A") if ch.isupper() else ord("a")
            out.append(chr((ord(ch) - base + shift) % 26 + base))
        else:
            out.append(ch)
    return "".join(out)


def atbash(text: str) -> str:
    out = []
    for ch in text:
        if ch.isalpha() and ch.isascii():
            base = ord("A") if ch.isupper() else ord("a")
            out.append(chr(base + 25 - (ord(ch) - base)))
        else:
            out.append(ch)
    return "".join(out)


def vigenere(text: str, key: str, decrypt: bool = False) -> str:
    key = "".join(c for c in key.upper() if c.isalpha())
    if not key:
        return text
    out, i = [], 0
    for ch in text:
        if ch.isalpha() and ch.isascii():
            base = ord("A") if ch.isupper() else ord("a")
            shift = ord(key[i % len(key)]) - ord("A")
            out.append(chr((ord(ch) - base + (-shift if decrypt else shift)) % 26 + base))
            i += 1
        else:
            out.append(ch)
    return "".join(out)


class EncryptionPuzzle:
    """Cipher types: caesar (key = shift), atbash (no key), vigenere (key = word)."""

    def __init__(self, plain: str, cipher_type: str, key, hints: list[str] | None = None,
                 free_hints: int = 0, title: str = "ENCRYPTED PAYLOAD"):
        self.plain = plain
        self.type = cipher_type
        self.key = key
        self.hints = hints or []
        self.free_hints = free_hints
        self.title = title
        self.ciphertext = self.encrypt()
        self.hints_used = 0
        self.attempts = 0

    def encrypt(self) -> str:
        if self.type == "caesar":
            return caesar(self.plain, int(self.key))
        if self.type == "atbash":
            return atbash(self.plain)
        if self.type == "vigenere":
            return vigenere(self.plain, str(self.key))
        raise ValueError(f"unknown cipher {self.type}")

    def decode_with(self, key_input) -> str:
        try:
            if self.type == "caesar":
                return caesar(self.ciphertext, -int(key_input))
            if self.type == "atbash":
                return atbash(self.ciphertext)
            return vigenere(self.ciphertext, str(key_input), decrypt=True)
        except (TypeError, ValueError):
            return self.ciphertext

    def check(self, key_input) -> bool:
        self.attempts += 1
        return self.decode_with(key_input) == self.plain

    def next_hint(self) -> str | None:
        if self.hints_used >= len(self.hints):
            return None
        hint = self.hints[self.hints_used]
        self.hints_used += 1
        return hint


# =====================================================================
# C) Routing puzzle - find a low-risk path through a virtual network
# =====================================================================
@dataclass
class RouteNode:
    id: int
    label: str
    x: float
    y: float
    risk: int
    latency: int


class RoutingPuzzle:
    def __init__(self, seed: int, difficulty: int = 1, budget_bonus: int = 0,
                 reveal: bool = False, target_name: str = "TARGET"):
        rng = random.Random(seed)
        self.difficulty = difficulty
        self.reveal = reveal
        self.target_name = target_name
        layers = 3 + min(difficulty, 3)
        self.nodes: list[RouteNode] = []
        self.edges: set[frozenset[int]] = set()
        columns: list[list[int]] = []

        def add(label: str, x: float, y: float, risk: int) -> int:
            node = RouteNode(len(self.nodes), label, x, y, risk, rng.randint(8, 90))
            self.nodes.append(node)
            return node.id

        self.start = add("YOU", 0.04, 0.5, 0)
        columns.append([self.start])
        for layer in range(1, layers + 1):
            count = rng.randint(2, 4)
            col = []
            for row in range(count):
                x = 0.04 + 0.92 * layer / (layers + 1)
                y = (row + 1) / (count + 1) + rng.uniform(-0.06, 0.06)
                risk = rng.choices([0, 1, 2, 3], weights=[2, 4, 3, 2])[0]
                col.append(add(f"RLY-{rng.randint(10, 99)}", x, y, risk))
            columns.append(col)
        self.goal = add(target_name, 0.96, 0.5, 0)
        columns.append([self.goal])

        for left, right in zip(columns, columns[1:]):
            for a in left:                      # every node reaches forward
                for b in rng.sample(right, k=min(len(right), rng.randint(1, 2))):
                    self._link(a, b)
            for b in right:                     # every node is reachable
                if not any(frozenset((a, b)) in self.edges for a in left):
                    self._link(rng.choice(left), b)
        for col in columns[1:-1]:               # a few lateral links for variety
            if len(col) > 1 and rng.random() < 0.6:
                a, b = rng.sample(col, 2)
                self._link(a, b)

        best_risk, best_path = self._optimal()
        self.optimal_path = best_path
        self.optimal_risk = best_risk
        self.max_hops = len(best_path) - 1 + 2
        self.budget = best_risk + max(0, 3 - difficulty) + budget_bonus

    def _link(self, a: int, b: int) -> None:
        if a != b:
            self.edges.add(frozenset((a, b)))

    def neighbors(self, node: int) -> list[int]:
        return [next(iter(e - {node})) for e in self.edges if node in e]

    def _optimal(self) -> tuple[int, list[int]]:
        queue = [(0, 0, self.start, [self.start])]
        seen: dict[int, tuple[int, int]] = {}
        while queue:
            risk, hops, node, path = heapq.heappop(queue)
            if node == self.goal:
                return risk, path
            if node in seen and seen[node] <= (risk, hops):
                continue
            seen[node] = (risk, hops)
            for nb in self.neighbors(node):
                if nb not in path:
                    heapq.heappush(queue, (risk + self.nodes[nb].risk, hops + 1, nb, path + [nb]))
        raise RuntimeError("unreachable goal")  # generation guarantees a path

    def path_risk(self, path: list[int]) -> int:
        return sum(self.nodes[n].risk for n in path)

    def validate(self, path: list[int]) -> tuple[bool, str]:
        if not path or path[0] != self.start or path[-1] != self.goal:
            return False, "Route must run from YOU to the target."
        for a, b in zip(path, path[1:]):
            if frozenset((a, b)) not in self.edges:
                return False, "Broken link in route."
        if len(path) - 1 > self.max_hops:
            return False, f"Too many hops (max {self.max_hops})."
        if self.path_risk(path) > self.budget:
            return False, f"Detection risk too high ({self.path_risk(path)}/{self.budget})."
        return True, "ROUTE ESTABLISHED"


# =====================================================================
# D) Access puzzle - combine clues to deduce a code
# =====================================================================
class AccessPuzzle:
    def __init__(self, code: str, clues: list[str], attempts: int = 4, title: str = "ACCESS CODE REQUIRED"):
        self.code = code
        self.clues = clues
        self.max_attempts = attempts
        self.title = title
        self.tries = 0

    @property
    def length(self) -> int:
        return len(self.code)

    @property
    def attempts_left(self) -> int:
        return self.max_attempts - self.tries

    def check(self, guess: str) -> tuple[bool, int]:
        """Returns (solved, digits in the correct position)."""
        self.tries += 1
        correct = sum(1 for a, b in zip(guess, self.code) if a == b)
        return guess == self.code, correct

    @classmethod
    def generate(cls, rng: random.Random, length: int = 4, attempts: int = 4) -> "AccessPuzzle":
        """Create a random puzzle whose clues identify exactly one code."""
        digits = list(range(10))
        code = rng.sample(digits, length)
        names = ["first", "second", "third", "fourth", "fifth", "sixth"]
        pool: list[tuple[str, object]] = []
        total = sum(code)
        pool.append((f"All digits add up to {total}.", lambda c, t=total: sum(c) == t))
        for i in range(length):
            parity = "even" if code[i] % 2 == 0 else "odd"
            pool.append((f"The {names[i]} digit is {parity}.", lambda c, i=i, p=code[i] % 2: c[i] % 2 == p))
            thr = code[i] + rng.randint(1, 3)
            if thr <= 9:
                pool.append((f"The {names[i]} digit is smaller than {thr}.", lambda c, i=i, t=thr: c[i] < t))
            thr2 = code[i] - rng.randint(1, 3)
            if thr2 >= 0:
                pool.append((f"The {names[i]} digit is greater than {thr2}.", lambda c, i=i, t=thr2: c[i] > t))
            for j in range(length):
                if i != j and code[i] > code[j]:
                    pool.append((f"The {names[i]} digit is larger than the {names[j]} digit.",
                                 lambda c, i=i, j=j: c[i] > c[j]))
                if i < j:
                    diff = abs(code[i] - code[j])
                    pool.append((f"The {names[i]} and {names[j]} digits differ by {diff}.",
                                 lambda c, i=i, j=j, d=diff: abs(c[i] - c[j]) == d))
        pool.append(("No digit appears twice.", lambda c: len(set(c)) == len(c)))
        rng.shuffle(pool)

        candidates = [list(p) for p in itertools.product(digits, repeat=length)]
        chosen: list[str] = []
        for text, test in pool:
            filtered = [c for c in candidates if test(c)]
            if len(filtered) < len(candidates):
                candidates = filtered
                chosen.append(text)
            if len(candidates) == 1:
                break
        for i in range(length):          # fallback: pin digits down until the code is unique
            if len(candidates) == 1:
                break
            chosen.append(f"The {names[i]} digit is {code[i]}.")
            candidates = [c for c in candidates if c[i] == code[i]]
        return cls("".join(map(str, code)), chosen, attempts)


# =====================================================================
# E) Trace minigame - parameters only; the stream is animated in the UI
# =====================================================================
@dataclass
class TraceConfig:
    required_hits: int = 5
    max_misses: int = 3
    speed: float = 1.0
    decoys: int = 6
    title: str = "TRACE DATA STREAM"


# =====================================================================
# Helpers shared by commands/tests
# =====================================================================
def random_label(rng: random.Random, n: int = 4) -> str:
    return "".join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(n))
