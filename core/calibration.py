"""Agreement math for validating graders (judge, metric) against human adjudication.
Stdlib-only so it rides into the deposit like the metric does."""
import random


def cohens_kappa(a: list[str], b: list[str]) -> float:
    """Agreement between two parallel label lists, corrected for chance agreement."""
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in set(a) | set(b))
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def coverage_ffr(flagged: list[bool], truly_bad: list[bool]) -> tuple[float, float]:
    """Grader as failure detector: (share of true failures caught,
    share of good records falsely flagged). Shankar's coverage / false-failure rate."""
    bad = [f for f, t in zip(flagged, truly_bad) if t]
    good = [f for f, t in zip(flagged, truly_bad) if not t]
    coverage = sum(bad) / len(bad) if bad else 0.0
    ffr = sum(good) / len(good) if good else 0.0
    return coverage, ffr


def bootstrap_ci(stat_fn, *cols, n: int = 1000, seed: int = 0) -> tuple[float, float]:
    """95% CI for stat_fn(*cols) by resampling records with replacement."""
    rng = random.Random(seed)
    m = len(cols[0])
    stats = sorted(
        stat_fn(*[[c[i] for i in idx] for c in cols])
        for idx in ([rng.randrange(m) for _ in range(m)] for _ in range(n))
    )
    return stats[int(0.025 * n)], stats[int(0.975 * n)]
