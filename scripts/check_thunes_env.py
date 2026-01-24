import os
import sys


def main() -> int:
    required = [
        "THUNES_SANDBOX_API_ENDPOINT",
        "THUNES_SANDBOX_API_KEY",
        "THUNES_SANDBOX_API_SECRET",
    ]
    missing = [name for name in required if not (os.getenv(name) or "").strip()]
    if not missing:
        print("All required THUNES sandbox env vars are set.")
        return 0
    print("Missing THUNES sandbox env vars: %s" % ", ".join(missing))
    return 2


if __name__ == "__main__":
    sys.exit(main())
