# Shuttle

**Plan a weaving project from one plain-text file: sett, take-up, shrinkage, yardage, cost, threading and treadling, all offline.**

Shuttle reads a short `.shuttle` project file and works out what you actually need to put on the loom. It handles sett, wash shrinkage, warp take-up, and hem and loom waste, then tells you how many ends and picks you need, how many yards and pounds of each yarn to buy, and what it will cost. It also draws the threading and counts treadle use. Errors are reported with file names and line numbers. Nothing is skipped quietly.

It uses only the Python standard library. There are no network calls, no accounts, and no API keys.

## Features

- **Plain-text project files** with `key: value` lines, comments after `#`, and no nested syntax.
- **Line-numbered validation.** Bad values, duplicate settings, unknown keys, missing required settings, undefined yarns, and out-of-range shafts all point at the offending line.
- **Unit-aware lengths.** `16in`, `16 in` and `40 cm` all work. A length with no unit is an error.
- **Shrinkage and take-up math.** Finished size is converted to the size on the loom, and warp length is grossed up for take-up and loom waste.
- **Warp and weft ends and picks.** Ends come from the stripe pattern times the repeat count. Picks are rounded up to whole numbers.
- **Yardage per yarn**, with a configurable waste allowance. Warp and weft yardage for the same yarn are combined.
- **Weight and cost** per yarn, from yards per pound and price per pound. Costs are rounded to cents.
- **Threading draw** as a text grid with color, end-number and shaft rows, wrapped at 60 ends.
- **Treadling counts** over the finished length: full repeats, leftover picks, use per treadle, and a preview of the first picks.
- **Repeat fit.** Shows the whole-repeat warps either side of your target width, with the finished width each would give.
- **Sett calculator** for a standalone finished width and end count.
- **Warnings** for a width that the warp will not hit, shafts that are never threaded, and yarns that are defined but unused.
- **JSON output** from `plan --json` for use in other tools.
- **Exit codes** from `check` that scripts can rely on: `0` OK, `1` warnings only, `2` errors. The other commands exit `0` on success and `2` on errors.

## Quick start

The repository includes a 4-shaft striped towel in `examples/striped-towel.shuttle`:

```
$ python3 -m shuttle check examples/striped-towel.shuttle
OK: examples/striped-towel.shuttle is valid (280 ends, 640 picks)
```

Then ask for the plan. `plan` prints a header with the warp, loom and finished sizes, then a table with ends, yards, pounds and cost per yarn, and a total:

```
$ python3 -m shuttle plan examples/striped-towel.shuttle
```

`repeat` shows the two whole-repeat warps either side of the 16 in target, with the finished width each gives:

```
$ python3 -m shuttle repeat examples/striped-towel.shuttle
```

## Project file

```
title: Striped hand towel
sett: 16              # ends per inch in the reed
ppi: 24               # picks per inch
width: 16 in          # finished width, after wash
length: 24 in         # finished length, after wash
shrink: 10%           # wet-finishing shrinkage
takeup: 10%           # warp lost to take-up on the loom
hems: 2 in            # warp allowed at each end for hems
loom_waste: 36 in     # tie-on and loom waste
waste: 10%            # allowance for samples and breakage
shafts: 4
warp: navy 8, white 4, navy 8
repeats: 14
threading: 1 2 3 4
treadling: 1 2 3 4
weft: white
yarn navy: 2400 ypl 14.50
yarn white: 2400 ypl 13.00
```

| Setting | Meaning |
| --- | --- |
| `sett`, `ppi` | Ends per inch and picks per inch. |
| `width`, `length` | Finished size after wash, as a length with a unit. |
| `shrink`, `takeup`, `waste` | Percentages with a `%` sign. `shrink` and `takeup` must be below 100%. |
| `hems`, `loom_waste` | Lengths added to the warp. `hems` applies at each end. Omit either for zero. |
| `shafts` | Number of shafts on the loom. |
| `warp` | One stripe unit as `color count` pairs separated by commas. |
| `repeats` | How many times the stripe unit is repeated across the warp. |
| `threading`, `treadling` | Shaft and treadle sequences, cycled. |
| `weft` | The weft yarn name. |
| `yarn <name>` | `<yards per pound> ypl <price per pound>`. |

## Formulas

- Raw width = `width / (1 - shrink)`. Raw length = `length / (1 - shrink)`.
- Ends = `repeats × (sum of warp counts)`. Target ends = `ceil(raw width × sett)`.
- Warp length = `(raw length + 2 × hems) / (1 - takeup) + loom_waste`.
- Picks = `ceil(raw length × ppi)`.
- Weft yards = `picks × (raw width + 2 in) / 36`.
- Yards per yarn = `(warp ends × warp length / 36 + weft yards) × (1 + waste)`. Pounds = yards / ypl. Cost = pounds × price, to the cent.

The tool does not model the tie-up. It counts how often each treadle is used, but it does not map treadles to shafts.

## Commands

```
python3 -m shuttle check FILE              validate; exit 0 OK, 1 warnings, 2 errors
python3 -m shuttle plan FILE [--json]      ends, picks, yardage, pounds and cost
python3 -m shuttle threading FILE          threading draw grid
python3 -m shuttle treadling FILE          picks and treadle use over the finished length
python3 -m shuttle repeat FILE             whole-repeat warps near the target width
python3 -m shuttle sett --width 16in --ends 285 [--shrink 10%]
```

Errors and warnings go to stderr as `path:line: level: message`. Results go to stdout.

## How to run

Requires Python 3.10 or later. Run from the repository root so that `shuttle` is on the import path:

```
python3 -m shuttle plan examples/striped-towel.shuttle
```

Your own project works the same way. Save a file with the settings above and pass its path.

## How to test

The tests use the standard `unittest` module, so they run under either pytest or unittest:

```
python3 -m pytest -q
python3 -m unittest discover -s tests
```

The suite covers parsing and line-numbered errors, shrink and take-up math, rounding of picks and costs, repeat fit, threading and treadling counts, and CLI exit codes and output.

## Layout

```
shuttle/
  parse.py    .shuttle parser and validation
  calc.py     ends, picks, yardage, weight, cost, repeat fit, warnings
  draft.py    threading grid and treadle counts
  cli.py      argparse commands
examples/     sample project
tests/        unittest suite, also run by pytest
```

