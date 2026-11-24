"""Ask the analyst agent a question from the command line.

    python -m atelier.agent "What was comp store sales growth in FY2026?"
"""

from __future__ import annotations

import argparse
import sys

from atelier.agent.agent import AnalystAgent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question", nargs="+")
    ap.add_argument("--show-sql", action="store_true", help="print the SQL each tool ran")
    args = ap.parse_args(argv)

    result = AnalystAgent().ask(" ".join(args.question))
    if result.answer is None:
        print(f"No answer: {result.error}", file=sys.stderr)
        return 1
    print(result.answer.answer)
    if result.answer.caveats:
        print("\nCaveats:\n- " + "\n- ".join(result.answer.caveats))
    print(f"\nMetrics: {', '.join(result.answer.metrics_used) or 'none'} | path: {', '.join(result.paths) or 'none'}"
          f" | {result.turns} turns, {result.latency_seconds}s | run {result.run_id}")
    if args.show_sql:
        for c in result.tool_calls:
            if c.sql:
                print(f"\n-- {c.tool} ({c.path})\n{c.sql}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
