"""Parse .shuttle project files.

Each line is `key: value`. Blank lines and anything after `#` are ignored.
Every problem is reported with its line number; nothing is skipped silently.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal

CM_PER_INCH = Decimal("2.54")
NUMBER = r"\d+(?:\.\d+)?"
LENGTH_RE = re.compile(rf"({NUMBER})\s*(in|cm)")
PERCENT_RE = re.compile(rf"({NUMBER})%")
YARN_RE = re.compile(rf"({NUMBER})\s+ypl\s+({NUMBER})")
WARP_ITEM_RE = re.compile(r"(.+?)\s+(\d+)")
REQUIRED = ("sett", "ppi", "width", "length", "shafts", "warp", "threading", "treadling", "weft")


@dataclass(frozen=True)
class Issue:
    message: str
    line: int | None = None
    level: str = "error"

    def render(self, path):
        where = f"{path}:{self.line}" if self.line else path
        return f"{where}: {self.level}: {self.message}"


@dataclass
class Yarn:
    name: str
    ypl: Decimal    # yards per pound
    price: Decimal  # money per pound


@dataclass
class Project:
    title: str = "Untitled"
    sett: Decimal | None = None      # ends per inch in the reed
    ppi: Decimal | None = None       # picks per inch
    width: Decimal | None = None     # inches, finished after wash
    length: Decimal | None = None    # inches, finished after wash
    shrink: Decimal = Decimal(0)     # wet-finishing shrinkage, fraction
    takeup: Decimal = Decimal(0)     # warp lost to take-up, fraction
    hems: Decimal = Decimal(0)       # inches of warp allowed at each end
    loom_waste: Decimal = Decimal(0)  # inches of tie-on and waste
    waste: Decimal = Decimal(0)      # yarn allowance added to all yardage
    shafts: int | None = None
    repeats: int = 1
    warp: list = field(default_factory=list)       # [(color, ends per repeat)]
    threading: list = field(default_factory=list)  # shaft for each end, cycled
    treadling: list = field(default_factory=list)  # treadle for each pick, cycled
    weft: str | None = None
    yarns: dict = field(default_factory=dict)      # name -> Yarn
    lines: dict = field(default_factory=dict)      # setting key -> line number


@dataclass
class ParseResult:
    project: Project
    issues: list

    @property
    def ok(self):
        return not any(issue.level == "error" for issue in self.issues)


def _positive(text):
    text = text.strip()
    if not re.fullmatch(NUMBER, text) or Decimal(text) <= 0:
        raise ValueError(f"expected a positive number, got {text!r}")
    return Decimal(text)


def _count(text):
    text = text.strip()
    if not re.fullmatch(r"\d+", text) or int(text) < 1:
        raise ValueError(f"expected a whole number of at least 1, got {text!r}")
    return int(text)


def _name(text):
    name = " ".join(text.lower().split())
    if not name:
        raise ValueError("a yarn name is required")
    return name


def parse_length(text):
    """Return inches for '16 in' or '40 cm'. The unit is required."""
    match = LENGTH_RE.fullmatch(text.strip())
    if not match:
        raise ValueError(f"length needs a number and a unit (in or cm), got {text.strip()!r}")
    value = _positive(match.group(1))
    return value if match.group(2) == "in" else value / CM_PER_INCH


def parse_percent(text):
    """Return a fraction for '10%'. The percent sign is required."""
    match = PERCENT_RE.fullmatch(text.strip())
    if not match:
        raise ValueError(f"percentage needs a % sign, e.g. '10%', got {text.strip()!r}")
    return Decimal(match.group(1)) / 100


def _numbers(text):
    tokens = text.replace(",", " ").split()
    if not tokens:
        raise ValueError("expected shaft numbers such as '1 2 3 4'")
    return [_count(token) for token in tokens]


def _warp(text):
    items = []
    for part in text.split(","):
        match = WARP_ITEM_RE.fullmatch(part.strip())
        if not match:
            raise ValueError(f"warp items look like 'navy 8', got {part.strip()!r}")
        items.append((_name(match.group(1)), _count(match.group(2))))
    return items


def _apply(project, key, value):
    if key.startswith("yarn "):
        name = _name(key[len("yarn "):])
        match = YARN_RE.fullmatch(value.strip())
        if not match:
            raise ValueError("yarn needs '<yards per pound> ypl <price per pound>', e.g. '2400 ypl 14.50'")
        project.yarns[name] = Yarn(name, _positive(match.group(1)), _positive(match.group(2)))
    elif key == "title":
        if not value:
            raise ValueError("title is empty")
        project.title = value
    elif key in ("sett", "ppi"):
        setattr(project, key, _positive(value))
    elif key in ("width", "length", "hems", "loom_waste"):
        setattr(project, key, parse_length(value))
    elif key in ("shrink", "takeup"):
        fraction = parse_percent(value)
        if fraction >= 1:
            raise ValueError(f"{key} must be below 100%")
        setattr(project, key, fraction)
    elif key == "waste":
        project.waste = parse_percent(value)
    elif key == "shafts":
        project.shafts = _count(value)
    elif key == "repeats":
        project.repeats = _count(value)
    elif key == "warp":
        project.warp = _warp(value)
    elif key == "threading":
        project.threading = _numbers(value)
    elif key == "treadling":
        project.treadling = _numbers(value)
    elif key == "weft":
        project.weft = _name(value)
    else:
        raise ValueError(f"unknown setting {key!r}")


def _check(project, failed):
    issues = []
    for key in REQUIRED:
        if key not in project.lines and key not in failed:
            issues.append(Issue(f"missing required setting '{key}'"))
    if "warp" in project.lines:
        for name, _ in project.warp:
            if f"yarn {name}" not in project.lines:
                issues.append(Issue(f"warp uses {name!r}, but there is no 'yarn {name}:' line", project.lines["warp"]))
    if "weft" in project.lines and f"yarn {project.weft}" not in project.lines:
        issues.append(Issue(f"weft uses {project.weft!r}, but there is no 'yarn {project.weft}:' line", project.lines["weft"]))
    if "shafts" in project.lines:
        for key in ("threading", "treadling"):
            if key in project.lines:
                for shaft in getattr(project, key):
                    if shaft > project.shafts:
                        issues.append(Issue(f"{key} uses shaft {shaft}, but shafts is {project.shafts}", project.lines[key]))
                        break
    return issues


def parse_text(text):
    project = Project()
    issues = []
    failed = set()
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            issues.append(Issue(f"expected 'key: value', got {line!r}", number))
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = " ".join(key.lower().split())
        if key in project.lines:
            issues.append(Issue(f"'{key}' is already set on line {project.lines[key]}", number))
            continue
        try:
            _apply(project, key, value)
        except ValueError as exc:
            issues.append(Issue(str(exc), number))
            failed.add(key)
            continue
        project.lines[key] = number
    issues.extend(_check(project, failed))
    return ParseResult(project, issues)
