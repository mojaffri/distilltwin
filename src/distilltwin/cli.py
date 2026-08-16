"""Command-line entry point for repeatable scenario runs."""

from __future__ import annotations

import argparse
from pathlib import Path

from distilltwin.scenarios import Scenario, ScenarioRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a DistillTwin closed-loop scenario")
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--disturbance-at", type=float, default=20.0)
    parser.add_argument("--feed-composition", type=float, default=0.58)
    parser.add_argument("--sensor-bias", type=float, default=0.0)
    parser.add_argument("--output", type=Path, default=Path("artifacts/scenario.csv"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    frame = ScenarioRunner().run(
        Scenario(
            duration=args.duration,
            disturbance_at=args.disturbance_at,
            feed_composition_after=args.feed_composition,
            top_sensor_bias_after=args.sensor_bias,
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    print(f"wrote {len(frame)} samples to {args.output}")


if __name__ == "__main__":
    main()

