"""
CCPM Project Management
======================

A Critical Chain Project Management implementation in Python.
"""

import argparse
import sys
from datetime import datetime
from .examples.simple_project import create_sample_project


def main():
    parser = argparse.ArgumentParser(description="Critical Chain Project Management")
    parser.add_argument(
        "--example", action="store_true", help="Run the example project"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="ccpm_output.png",
        help="Output filename for visualization",
    )

    args = parser.parse_args()

    if args.example:
        print("Running example project...")
        scheduler = create_sample_project()
        print(f"Visualization saved to {args.output}")
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
