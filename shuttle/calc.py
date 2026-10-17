"""Yardage, weight, cost and fit math for a parsed project.

Ends and picks are rounded up to whole numbers. Money is quantized to cents.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_EVEN, ROUND_HALF_UP

from .parse import Issue

INCHES_PER_YARD = Decimal(36)
SELVEDGE_INCHES = Decimal(2)       # added to each weft pick for the two selvedges
WIDTH_TOLERANCE = Decimal("0.5")   # inches of finished-width slack before a warning
CENT = Decimal("0.01")


def _ceil(value):
    """Round up, ignoring division noise past the sixth decimal (640.000...01 is 640)."""
    value = value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def repeat_ends(project):
    return sum(count for _, count in project.warp)


def total_ends(project):
    return repeat_ends(project) * project.repeats


def raw_width(project):
    """Width on the loom, before wash shrinkage."""
    return project.width / (1 - project.shrink)


def raw_length(project):
    """Length on the loom, before wash shrinkage."""
    return project.length / (1 - project.shrink)


def warp_length(project):
    """Warp to tie on: cloth plus hems, grossed up for take-up, plus loom waste."""
    cloth = raw_length(project) + 2 * project.hems
    return cloth / (1 - project.takeup) + project.loom_waste


def target_ends(project):
    return _ceil(raw_width(project) * project.sett)


def predicted_width(project, ends=None):
    """Finished width that a given number of warp ends produces."""
    ends = total_ends(project) if ends is None else ends
    return ends / project.sett * (1 - project.shrink)


def picks(project):
    return _ceil(raw_length(project) * project.ppi)


def sett_for(width, ends, shrink=Decimal(0)):
    """Ends per inch needed to weave `ends` into a finished `width` after wash."""
    return ends / (width / (1 - shrink))


@dataclass(frozen=True)
class YarnLine:
    name: str
    ends: int
    yards: Decimal
    pounds: Decimal
    cost: Decimal


@dataclass(frozen=True)
class Plan:
    ends: int
    picks: int
    raw_width: Decimal
    raw_length: Decimal
    warp_length: Decimal
    predicted_width: Decimal
    lines: tuple
    total_pounds: Decimal
    total_cost: Decimal


def make_plan(project):
    warp_ends = {}
    for name, count in project.warp:
        warp_ends[name] = warp_ends.get(name, 0) + count * project.repeats
    per_yard = warp_length(project) / INCHES_PER_YARD
    yards = {name: ends * per_yard for name, ends in warp_ends.items()}
    weft_yards = picks(project) * (raw_width(project) + SELVEDGE_INCHES) / INCHES_PER_YARD
    yards[project.weft] = yards.get(project.weft, Decimal(0)) + weft_yards

    lines = []
    for name, yarn in project.yarns.items():
        if name not in yards:
            continue
        needed = yards[name] * (1 + project.waste)
        pounds = needed / yarn.ypl
        cost = (pounds * yarn.price).quantize(CENT, rounding=ROUND_HALF_UP)
        lines.append(YarnLine(name, warp_ends.get(name, 0), needed, pounds, cost))
    return Plan(
        ends=total_ends(project),
        picks=picks(project),
        raw_width=raw_width(project),
        raw_length=raw_length(project),
        warp_length=warp_length(project),
        predicted_width=predicted_width(project),
        lines=tuple(lines),
        total_pounds=sum((line.pounds for line in lines), Decimal(0)),
        total_cost=sum((line.cost for line in lines), Decimal(0)),
    )


@dataclass(frozen=True)
class FitOption:
    repeats: int
    ends: int
    width: Decimal


def repeat_options(project):
    """The two whole-repeat warps either side of the target width."""
    unit = repeat_ends(project)
    low = max(1, target_ends(project) // unit)
    return [FitOption(k, unit * k, predicted_width(project, unit * k)) for k in (low, low + 1)]


def warnings(project):
    issues = []
    fit = predicted_width(project)
    if abs(fit - project.width) > WIDTH_TOLERANCE:
        issues.append(Issue(
            f"warp makes {fit:.2f} in finished width, target is {project.width:.2f} in; see `repeat`",
            project.lines.get("width"), "warning"))
    threaded = set(project.threading)
    for shaft in range(1, project.shafts + 1):
        if shaft not in threaded:
            issues.append(Issue(f"shaft {shaft} is never threaded", project.lines.get("threading"), "warning"))
    used = {name for name, _ in project.warp} | {project.weft}
    for name in project.yarns:
        if name not in used:
            issues.append(Issue(f"yarn {name!r} is defined but never used", project.lines.get(f"yarn {name}"), "warning"))
    return issues
