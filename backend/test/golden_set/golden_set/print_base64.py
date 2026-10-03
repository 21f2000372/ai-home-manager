import argparse
import base64
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Print a file as base64."
    )
    parser.add_argument(
        "file_path",
        help="Path to the document/file",
    )

    args = parser.parse_args()

    path = Path(args.file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Not a file: {path}"
        )

    with path.open("rb") as f:
        data_base64 = base64.b64encode(
            f.read()
        ).decode("utf-8")

    print(data_base64)


if __name__ == "__main__":
    main()