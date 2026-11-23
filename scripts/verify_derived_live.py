"""Prevent automatic coverage writers from changing Live editorial material."""
import argparse
from pathlib import Path
import sys

from today_first_live import canonical, strict_json


def validate(before, after):
    if not isinstance(before,dict) or not isinstance(after,dict):
        raise ValueError("LIVE_WRITE_AUTHORITY_HOLD: Live snapshots must be JSON objects")
    # Coverage is the only projection owned by Rolling Desk, not the publisher.
    def editorial(data):
        return canonical({key:value for key,value in data.items() if key!="coverage"})

    if editorial(before)!=editorial(after):
        raise ValueError("SCHEDULED_LIVE_WRITE_AUTHORITY_HOLD: only derived coverage may change")


def validate_bytes(before, after):
    validate(strict_json(before),strict_json(after))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("proposed",type=Path)
    args=p.parse_args()
    try:
        validate_bytes(sys.stdin.buffer.read(),args.proposed.read_bytes())
    except (ValueError,TypeError,AttributeError) as error:
        print(str(error),file=sys.stderr)
        return 1
    print("DERIVED_LIVE_WRITE_BOUNDARY_OK")
    return 0


if __name__=="__main__":
    sys.exit(main())
