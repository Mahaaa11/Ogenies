import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.lnc_agent.io import read_events, read_prospects


def main() -> None:
    prospects = read_prospects("data/prospects.csv")
    events = read_events("data/events.csv")

    print("Number of prospects:", len(prospects))
    print("Number of events:", len(events))
    print()

    print("First prospect as a Python object:")
    print(prospects[0])
    print()

    print("First event as a Python object:")
    print(events[0])


if __name__ == "__main__":
    main()
