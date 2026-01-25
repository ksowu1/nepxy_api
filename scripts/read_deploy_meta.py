import json
import sys


def main() -> int:
    path = "deploy_meta.json"
    if len(sys.argv) > 1:
        path = sys.argv[1]

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        print("", end="")
        return 1

    image_ref = ""
    if isinstance(data, dict):
        image_ref = data.get("image_ref") or ""

    print(image_ref)
    return 0 if image_ref else 1


if __name__ == "__main__":
    raise SystemExit(main())
