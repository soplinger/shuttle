"""Threading draft and treadling counts."""

from dataclasses import dataclass

from .calc import picks, total_ends


def end_shafts(project):
    """Shaft for every warp end, cycling through the threading sequence."""
    return [project.threading[i % len(project.threading)] for i in range(total_ends(project))]


def end_colors(project):
    unit = [name for name, count in project.warp for _ in range(count)]
    return unit * project.repeats


def threading_chart(project, per_row=60):
    """Draft grid: one row per shaft (highest first), one column per end."""
    shafts = end_shafts(project)
    colors = end_colors(project)
    blocks = []
    for start in range(0, len(shafts), per_row):
        stop = min(start + per_row, len(shafts))
        rows = [
            f"ends {start + 1}-{stop}",
            "color     " + "".join(colors[i][0].upper() for i in range(start, stop)),
            "tens      " + "".join(str((i + 1) // 10 % 10) if (i + 1) % 10 == 0 else " " for i in range(start, stop)),
            "ones      " + "".join(str((i + 1) % 10) for i in range(start, stop)),
        ]
        for shaft in range(project.shafts, 0, -1):
            cells = "".join("x" if shafts[i] == shaft else "." for i in range(start, stop))
            rows.append(f"shaft {shaft:>2}  {cells}")
        blocks.append("\n".join(rows))
    return "\n\n".join(blocks)


@dataclass(frozen=True)
class TreadlingSummary:
    picks: int
    full_repeats: int
    leftover: int
    counts: dict


def treadling_summary(project):
    total = picks(project)
    sequence = project.treadling
    full, leftover = divmod(total, len(sequence))
    counts = {
        treadle: full * sequence.count(treadle) + sequence[:leftover].count(treadle)
        for treadle in sorted(set(sequence))
    }
    return TreadlingSummary(total, full, leftover, counts)


def pick_sequence(project, count):
    """Treadle used on each of the first `count` picks."""
    return [project.treadling[i % len(project.treadling)] for i in range(count)]
