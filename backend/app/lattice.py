from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import product as cartesian_product
from math import gcd, sqrt
from random import Random

from app.tuning.analysis import cents, monzo
from app.tuning.ratios import reduce_to_octave

MAX_GENERATORS = 8
MAX_EXPONENT = 16
MAX_DOMAIN_POINTS = 4096
BOUNDARY_POLICIES = ("stop", "reflect", "wrap", "resample")

Vector = tuple[int, ...]


@dataclass(frozen=True)
class ExponentBasis:
    """Ordered integer generator basis for the exponent lattice."""

    generators: tuple[int, ...]
    labels: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if not 1 <= len(self.generators) <= MAX_GENERATORS:
            raise ValueError(f"basis must contain 1..{MAX_GENERATORS} generators")
        if any(generator < 2 for generator in self.generators):
            raise ValueError("generators must be integers >= 2")

    def prime_matrix(self) -> tuple[dict[int, int], ...]:
        return tuple({int(prime): exponent for prime, exponent in monzo(Fraction(generator)).items()} for generator in self.generators)

    def dependencies(self) -> list[Vector]:
        """Integer relations among generators (left nullspace of the prime matrix)."""
        matrix = self.prime_matrix()
        primes = sorted({prime for row in matrix for prime in row})
        if not primes:
            return []
        rows = [[Fraction(matrix[col].get(prime, 0)) for col in range(len(matrix))] for prime in primes]
        n_rows, n_cols = len(rows), len(matrix)
        pivot_columns: list[int] = []
        rank = 0
        for column in range(n_cols):
            pivot = next((i for i in range(rank, n_rows) if rows[i][column] != 0), None)
            if pivot is None:
                continue
            rows[rank], rows[pivot] = rows[pivot], rows[rank]
            scale = rows[rank][column]
            rows[rank] = [value / scale for value in rows[rank]]
            for i in range(n_rows):
                if i != rank and rows[i][column] != 0:
                    factor = rows[i][column]
                    rows[i] = [a - factor * b for a, b in zip(rows[i], rows[rank])]
            pivot_columns.append(column)
            rank += 1
            if rank == n_rows:
                break
        free_columns = [column for column in range(n_cols) if column not in pivot_columns]
        relations: list[Vector] = []
        for free in free_columns:
            vector = [Fraction(0)] * n_cols
            vector[free] = Fraction(1)
            for i, column in enumerate(pivot_columns):
                vector[column] = -rows[i][free]
            lcm = 1
            for value in vector:
                lcm = lcm * value.denominator // gcd(lcm, value.denominator)
            integers = [int(value * lcm) for value in vector]
            divisor = 0
            for integer in integers:
                divisor = gcd(divisor, abs(integer))
            if divisor > 1:
                integers = [value // divisor for value in integers]
            relations.append(tuple(integers))
        return relations

    def warnings(self) -> list[str]:
        warnings = []
        if 2 in self.generators:
            warnings.append("generator 2 is an octave-only (null) direction after normalization")
        for relation in self.dependencies():
            terms = [f"{generator}^{exponent}" for generator, exponent in zip(self.generators, relation) if exponent]
            warnings.append(f"dependent basis: product of {' · '.join(terms)} = 1")
        return warnings


@dataclass(frozen=True)
class LatticePitch:
    vector: Vector
    raw_ratio: Fraction
    normalized_ratio: Fraction
    octave_shift: int
    cents: float
    pitch_class_id: str
    collision_group: int


def _check_vector(basis: ExponentBasis, vector: Vector) -> None:
    if len(vector) != len(basis.generators):
        raise ValueError(f"vector must have {len(basis.generators)} dimensions")


def evaluate(basis: ExponentBasis, vector: Vector) -> Fraction:
    """Exact product of generators raised to the vector's exponents."""
    _check_vector(basis, vector)
    result = Fraction(1)
    for generator, exponent in zip(basis.generators, vector):
        result *= Fraction(generator) ** exponent
    return result


def normalize(ratio: Fraction) -> tuple[Fraction, int]:
    """Return (normalized in [1, 2), k) such that ratio * 2**k == normalized."""
    if ratio <= 0:
        raise ValueError("ratio must be positive")
    shift = 0
    while ratio >= 2:
        ratio /= 2
        shift -= 1
    while ratio < 1:
        ratio *= 2
        shift += 1
    return ratio, shift


def _check_domain(minimum: Vector, maximum: Vector) -> None:
    if len(minimum) != len(maximum):
        raise ValueError("domain bounds must have matching dimensions")
    if any(lo > hi for lo, hi in zip(minimum, maximum)):
        raise ValueError("domain minimum must not exceed maximum")
    if any(not -MAX_EXPONENT <= value <= MAX_EXPONENT for value in minimum + maximum):
        raise ValueError(f"exponents must stay within -{MAX_EXPONENT}..{MAX_EXPONENT}")


def enumerate_domain(basis: ExponentBasis, minimum: Vector, maximum: Vector, max_points: int = MAX_DOMAIN_POINTS) -> list[LatticePitch]:
    """Enumerate a bounded rectangular exponent domain with collision grouping."""
    _check_vector(basis, minimum)
    _check_domain(minimum, maximum)
    count = 1
    for lo, hi in zip(minimum, maximum):
        count *= hi - lo + 1
    if count > max_points:
        raise ValueError(f"domain contains {count} points, limit is {max_points}")
    vectors = sorted(cartesian_product(*[range(lo, hi + 1) for lo, hi in zip(minimum, maximum)]))
    evaluated = []
    for vector in vectors:
        raw = evaluate(basis, vector)
        normalized, shift = normalize(raw)
        evaluated.append((vector, raw, normalized, shift))
    unique_ratios = sorted({entry[2] for entry in evaluated})
    groups = {ratio: index for index, ratio in enumerate(unique_ratios)}
    return [
        LatticePitch(vector, raw, normalized, shift, round(cents(normalized), 5), str(normalized), groups[normalized])
        for vector, raw, normalized, shift in evaluated
    ]


def cumulative_offsets(differences: list[Vector]) -> list[Vector]:
    """Cumulative sums starting from the zero vector (s0 = origin)."""
    offsets = [tuple(0 for _ in differences[0])] if differences else []
    for difference in differences:
        offsets.append(tuple(a + b for a, b in zip(offsets[-1], difference)))
    return offsets


def differences_from_offsets(offsets: list[Vector]) -> list[Vector]:
    return [tuple(b - a for a, b in zip(offsets[i], offsets[i + 1])) for i in range(len(offsets) - 1)]


def reconstruct(root: Fraction, basis: ExponentBasis, chord_vectors: list[Vector]) -> tuple[list[Vector], list[LatticePitch]]:
    """Build a chord from independent root-relative exponent vectors."""
    for vector in chord_vectors:
        _check_vector(basis, vector)
    offsets = [tuple(0 for _ in basis.generators), *chord_vectors]
    tones = []
    for index, offset in enumerate(offsets):
        raw = root * evaluate(basis, offset)
        normalized, shift = normalize(raw)
        tones.append(LatticePitch(offset, raw, normalized, shift, round(cents(normalized), 5), str(normalized), index))
    return offsets, tones


def root_progression(
    basis: ExponentBasis, start: Vector, differences: list[Vector]
) -> list[Vector]:
    """Accumulate root-motion differences into an absolute root path."""
    _check_vector(basis, start)
    for difference in differences:
        _check_vector(basis, difference)
    roots = [start]
    for difference in differences:
        roots.append(tuple(a + b for a, b in zip(roots[-1], difference)))
    return roots


def generate_lattice_chord(
    root: Fraction,
    basis: ExponentBasis,
    allowed: list[Vector],
    tone_count: int,
    seed: int,
    minimum: Vector,
    maximum: Vector,
) -> tuple[list[Vector], list[Vector], list[LatticePitch]]:
    """Generate a deterministic self-avoiding harmony path in exponent space."""
    _check_vector(basis, minimum)
    _check_domain(minimum, maximum)
    if not 1 <= tone_count <= 16:
        raise ValueError("tone_count must be between 1 and 16")
    if not allowed:
        raise ValueError("allowed_differences must not be empty")
    for difference in allowed:
        _check_vector(basis, difference)

    origin = tuple(0 for _ in basis.generators)
    if not all(lo <= value <= hi for value, lo, hi in zip(origin, minimum, maximum)):
        raise ValueError("the exponent domain must contain the zero-vector root")

    random = Random(seed)
    offsets = [origin]
    used_pitch_classes = {normalize(root)[0]}
    visits = 0

    def search() -> bool:
        nonlocal visits
        if len(offsets) == tone_count:
            return True
        visits += 1
        if visits > MAX_DOMAIN_POINTS * 4:
            return False
        current = offsets[-1]
        candidates = []
        for difference in allowed:
            candidate = tuple(a + b for a, b in zip(current, difference))
            if not all(lo <= value <= hi for value, lo, hi in zip(candidate, minimum, maximum)):
                continue
            pitch_class = normalize(root * evaluate(basis, candidate))[0]
            if pitch_class in used_pitch_classes:
                continue
            candidates.append((candidate, pitch_class))
        random.shuffle(candidates)
        for candidate, pitch_class in candidates:
            offsets.append(candidate)
            used_pitch_classes.add(pitch_class)
            if search():
                return True
            used_pitch_classes.remove(pitch_class)
            offsets.pop()
        return False

    if not search():
        raise ValueError(
            f"cannot generate {tone_count} unique tones with the current "
            "domain and allowed differences"
        )
    chord_vectors = offsets[1:]
    _offsets, tones = reconstruct(root, basis, chord_vectors)
    return chord_vectors, offsets, tones


def transpose_root(root: Fraction, factor: Fraction) -> Fraction:
    if factor <= 0:
        raise ValueError("transposition factor must be positive")
    return root * factor


def rotate_path(differences: list[Vector], n: int) -> list[Vector]:
    if not differences:
        return []
    n %= len(differences)
    return differences[n:] + differences[:n]


def reverse_path(root: Fraction, basis: ExponentBasis, differences: list[Vector]) -> tuple[Fraction, list[Vector]]:
    """Reverse the construction path; the final tone becomes the new root."""
    offsets = cumulative_offsets(differences)
    new_root = root * evaluate(basis, offsets[-1])
    return new_root, [tuple(-value for value in difference) for difference in reversed(differences)]


def invert_signs(differences: list[Vector]) -> list[Vector]:
    return [tuple(-value for value in difference) for difference in differences]


def lattice_walk(
    basis: ExponentBasis,
    start: Vector,
    allowed: list[Vector],
    length: int,
    seed: int,
    minimum: Vector,
    maximum: Vector,
    boundary: str,
) -> list[Vector]:
    """Seeded lattice walk with domain boundary policies."""
    _check_vector(basis, start)
    _check_domain(minimum, maximum)
    if not allowed:
        raise ValueError("allowed_differences must not be empty")
    for difference in allowed:
        _check_vector(basis, difference)
    if boundary not in BOUNDARY_POLICIES:
        raise ValueError(f"boundary must be one of {', '.join(BOUNDARY_POLICIES)}")
    if length < 1:
        raise ValueError("length must be positive")

    def inside(vector: Vector) -> bool:
        return all(lo <= value <= hi for value, lo, hi in zip(vector, minimum, maximum))

    if not inside(start):
        raise ValueError("start_vector is outside the domain")
    random = Random(seed)
    path = [start]
    while len(path) <= length:
        candidate = None
        for _ in range(32):
            step = random.choice(allowed)
            nxt = tuple(a + b for a, b in zip(path[-1], step))
            if inside(nxt):
                candidate = nxt
                break
            if boundary == "stop":
                return path
            if boundary == "reflect":
                candidate = tuple(_reflect(value, lo, hi) for value, lo, hi in zip(nxt, minimum, maximum))
                break
            if boundary == "wrap":
                candidate = tuple(lo + (value - lo) % (hi - lo + 1) for value, lo, hi in zip(nxt, minimum, maximum))
                break
        if candidate is None:
            return path
        path.append(candidate)
    return path


def _reflect(value: int, lo: int, hi: int) -> int:
    while value < lo or value > hi:
        if value < lo:
            value = lo + (lo - value)
        else:
            value = hi - (value - hi)
    return value


def nearest_vector(basis: ExponentBasis, ratio: Fraction, minimum: Vector, maximum: Vector) -> tuple[Vector, float]:
    """Domain vector closest in cents to the ratio's pitch class, with deviation."""
    target, _ = normalize(ratio)
    target_cents = cents(target)
    best: tuple[Vector, float] | None = None
    for pitch in enumerate_domain(basis, minimum, maximum):
        deviation = abs(pitch.cents - target_cents)
        if best is None or deviation < best[1]:
            best = (pitch.vector, round(deviation, 5))
    if best is None:
        raise ValueError("domain is empty")
    return best


def lattice_distance(first: Vector, second: Vector, p: int = 1) -> float:
    if len(first) != len(second):
        raise ValueError("vectors must have matching dimensions")
    differences = [abs(a - b) for a, b in zip(first, second)]
    if p == 1:
        return float(sum(differences))
    if p == 2:
        return sqrt(sum(value**2 for value in differences))
    raise ValueError("p must be 1 or 2")


def monzo_distance(basis: ExponentBasis, first: Vector, second: Vector) -> float:
    """L1 distance after transforming the coordinate difference into prime space."""
    _check_vector(basis, first)
    _check_vector(basis, second)
    matrix = basis.prime_matrix()
    primes = sorted({prime for row in matrix for prime in row})
    difference = [a - b for a, b in zip(first, second)]
    return float(sum(abs(sum(d * row.get(prime, 0) for d, row in zip(difference, matrix))) for prime in primes))


def cents_distance(basis: ExponentBasis, first: Vector, second: Vector) -> float:
    interval = evaluate(basis, first) / evaluate(basis, second)
    return round(abs(cents(reduce_to_octave(interval))), 5)
