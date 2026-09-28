from __future__ import annotations

import argparse
import csv
from collections.abc import Iterator
from pathlib import Path


Frame = tuple[int, tuple[float, float], list[tuple[int, float]]]


def read_frames(path: Path) -> Iterator[Frame]:
    """Yield timestep, x bounds, and (type, x) atoms from a LAMMPS dump."""
    with path.open("r", encoding="utf-8") as handle:
        while True:
            marker = handle.readline()
            if not marker:
                return
            if marker.strip() != "ITEM: TIMESTEP":
                continue

            timestep = int(handle.readline())
            if handle.readline().strip() != "ITEM: NUMBER OF ATOMS":
                raise ValueError("Invalid dump: missing atom-count header")
            atom_count = int(handle.readline())

            box_header = handle.readline().strip()
            if not box_header.startswith("ITEM: BOX BOUNDS"):
                raise ValueError("Invalid dump: missing box-bounds header")
            bounds = [tuple(map(float, handle.readline().split()[:2])) for _ in range(3)]

            atom_header = handle.readline().split()[2:]
            try:
                type_index = atom_header.index("type")
                x_index = atom_header.index("x")
            except ValueError as error:
                raise ValueError("The dump must contain type and x fields") from error

            atoms: list[tuple[int, float]] = []
            for _ in range(atom_count):
                values = handle.readline().split()
                atoms.append((int(values[type_index]), float(values[x_index])))
            yield timestep, bounds[0], atoms


def mixing_index(
    atoms: list[tuple[int, float]], x_low: float, x_high: float, bins: int
) -> tuple[float, int, int]:
    counts = [[0, 0] for _ in range(bins)]
    width = x_high - x_low
    for atom_type, x in atoms:
        index = min(bins - 1, max(0, int((x - x_low) / width * bins)))
        counts[index][atom_type - 1] += 1

    type1 = sum(pair[0] for pair in counts)
    type2 = sum(pair[1] for pair in counts)
    total = type1 + type2
    mixing = 1.0 - sum(abs(a - b) for a, b in counts) / total
    return mixing, type1, type2


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate a frame-by-frame mixing index from a LAMMPS dump")
    parser.add_argument(
        "trajectory",
        nargs="?",
        type=Path,
        default=Path("preview/p_0p30/trajectory.lammpstrj"),
    )
    parser.add_argument("--bins", type=int, default=20)
    parser.add_argument("--timestep-size", type=float, default=0.005)
    parser.add_argument("--output", type=Path, default=Path("examples/mixing_p030.csv"))
    args = parser.parse_args()

    if args.bins <= 0:
        parser.error("--bins must be a positive integer")
    if args.timestep_size <= 0:
        parser.error("--timestep-size must be positive")

    rows: list[dict[str, float | int]] = []
    for timestep, x_bounds, atoms in read_frames(args.trajectory):
        mixing, type1, type2 = mixing_index(atoms, x_bounds[0], x_bounds[1], args.bins)
        rows.append(
            {
                "timestep": timestep,
                "time_lj": timestep * args.timestep_size,
                "mixing_index": mixing,
                "type1_count": type1,
                "type2_count": type2,
            }
        )

    if not rows:
        raise ValueError(f"No frames found: {args.trajectory}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Read {len(rows)} frames: {args.trajectory}")
    print(f"Initial M={rows[0]['mixing_index']:.6f}; final M={rows[-1]['mixing_index']:.6f}")
    print(f"Wrote: {args.output}")


if __name__ == "__main__":
    main()
