"""Command-line interface: `python3 -m shuttle <command> ...`."""

import argparse
import json
import sys
from decimal import Decimal

from . import calc, draft
from .parse import Issue, parse_length, parse_percent, parse_text


def _length_arg(text):
    try:
        return parse_length(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))


def _percent_arg(text):
    try:
        fraction = parse_percent(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))
    if fraction >= 1:
        raise argparse.ArgumentTypeError("must be below 100%")
    return fraction


def _ends_arg(text):
    if not text.isdigit() or int(text) < 1:
        raise argparse.ArgumentTypeError(f"expected a whole number of ends, got {text!r}")
    return int(text)


def _load(path):
    """Return (project, issues). The project is None when the file has errors."""
    try:
        with open(path, encoding="utf-8") as handle:
            result = parse_text(handle.read())
    except OSError as exc:
        return None, [Issue(f"cannot read file: {exc.strerror}")]
    if not result.ok:
        return None, result.issues
    return result.project, result.issues + calc.warnings(result.project)


def _report(path, issues):
    for issue in issues:
        print(issue.render(path), file=sys.stderr)


def cmd_check(args):
    project, issues = _load(args.file)
    _report(args.file, issues)
    if project is None:
        return 2
    if issues:
        return 1
    print(f"OK: {args.file} is valid ({calc.total_ends(project)} ends, {calc.picks(project)} picks)")
    return 0


def _plan_dict(project, plan):
    return {
        "title": project.title,
        "ends": plan.ends,
        "picks": plan.picks,
        "raw_width_in": f"{plan.raw_width:.2f}",
        "raw_length_in": f"{plan.raw_length:.2f}",
        "warp_length_in": f"{plan.warp_length:.2f}",
        "finished_width_in": f"{plan.predicted_width:.2f}",
        "total_pounds": f"{plan.total_pounds:.3f}",
        "total_cost": f"{plan.total_cost:.2f}",
        "yarns": [
            {
                "name": line.name,
                "ends": line.ends,
                "yards": f"{line.yards:.1f}",
                "pounds": f"{line.pounds:.3f}",
                "cost": f"{line.cost:.2f}",
            }
            for line in plan.lines
        ],
    }


def _plan_text(project, plan):
    out = [
        project.title,
        "",
        f"Warp         {plan.ends} ends ({project.repeats} x {calc.repeat_ends(project)} per repeat)",
        f"Loom         {plan.raw_width:.2f} in wide, {plan.raw_length:.2f} in long before wash",
        f"Warp length  {plan.warp_length:.2f} in ({plan.warp_length / 36:.2f} yd)",
        f"Finished     {plan.predicted_width:.2f} in wide (target {project.width:.2f} in)",
        f"Picks        {plan.picks}",
        "",
        f"{'Yarn':<14}{'Ends':>6}{'Yards':>10}{'Pounds':>10}{'Cost':>10}",
    ]
    for line in plan.lines:
        out.append(
            f"{line.name:<14}{line.ends:>6}{line.yards:>10.1f}{line.pounds:>10.3f}{line.cost:>10.2f}"
        )
    out.append(
        f"{'Total':<14}{'':>6}{'':>10}{plan.total_pounds:>10.3f}{plan.total_cost:>10.2f}"
    )
    return "\n".join(out)


def cmd_plan(args):
    project, issues = _load(args.file)
    _report(args.file, issues)
    if project is None:
        return 2
    plan = calc.make_plan(project)
    if args.json:
        print(json.dumps(_plan_dict(project, plan), indent=2))
    else:
        print(_plan_text(project, plan))
    return 0


def cmd_threading(args):
    project, issues = _load(args.file)
    _report(args.file, issues)
    if project is None:
        return 2
    print(draft.threading_chart(project))
    return 0


def cmd_treadling(args):
    project, issues = _load(args.file)
    _report(args.file, issues)
    if project is None:
        return 2
    summary = draft.treadling_summary(project)
    use = "  ".join(f"{treadle}: {count}" for treadle, count in summary.counts.items())
    print(f"Picks: {summary.picks}")
    print(f"Full treadling repeats: {summary.full_repeats}, leftover picks: {summary.leftover}")
    print(f"Treadle use: {use}")
    preview = draft.pick_sequence(project, 16)
    print("First picks: " + " ".join(str(t) for t in preview))
    return 0


def cmd_repeat(args):
    project, issues = _load(args.file)
    _report(args.file, issues)
    if project is None:
        return 2
    print(f"Pattern repeat: {calc.repeat_ends(project)} ends")
    print(f"Target for {project.width:.2f} in finished: {calc.target_ends(project)} ends")
    for option in calc.repeat_options(project):
        marker = "  (current)" if option.repeats == project.repeats else ""
        print(f"  {option.repeats} repeats = {option.ends} ends, finished {option.width:.2f} in{marker}")
    return 0


def cmd_sett(args):
    epi = calc.sett_for(args.width, args.ends, args.shrink)
    raw = args.width / (1 - args.shrink)
    print(
        f"{args.ends} ends for {args.width:.2f} in finished "
        f"({raw:.2f} in before wash) needs {epi:.2f} ends per inch"
    )
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="shuttle", description="Plan weaving projects from plain-text files.")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="validate a project file; exit 0 ok, 1 warnings, 2 errors")
    check.add_argument("file")
    check.set_defaults(handler=cmd_check)

    plan = sub.add_parser("plan", help="ends, yardage, weight and cost")
    plan.add_argument("file")
    plan.add_argument("--json", action="store_true", help="print machine-readable JSON")
    plan.set_defaults(handler=cmd_plan)

    threading = sub.add_parser("threading", help="draw the threading as a grid")
    threading.add_argument("file")
    threading.set_defaults(handler=cmd_threading)

    treadling = sub.add_parser("treadling", help="count treadle use over the finished length")
    treadling.add_argument("file")
    treadling.set_defaults(handler=cmd_treadling)

    repeat = sub.add_parser("repeat", help="nearest whole-repeat warps for the target width")
    repeat.add_argument("file")
    repeat.set_defaults(handler=cmd_repeat)

    sett = sub.add_parser("sett", help="ends per inch needed for a finished width")
    sett.add_argument("--width", required=True, type=_length_arg, help="finished width, e.g. 16in or 40cm")
    sett.add_argument("--ends", required=True, type=_ends_arg)
    sett.add_argument("--shrink", default=Decimal(0), type=_percent_arg, help="wash shrinkage, e.g. 10%%")
    sett.set_defaults(handler=cmd_sett)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.handler(args)
