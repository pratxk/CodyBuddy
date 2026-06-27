import json
import sys
from agent.graph import run_build


def main() -> None:
    prompt = " ".join(sys.argv[1:]) or input("What should CodyBuddy build? ").strip()
    if not prompt:
        print("No prompt given."); return
    out = run_build(prompt)
    print(json.dumps({"name": out["plan"].name, "files": list(out["files"].keys())}, indent=2))


if __name__ == "__main__":
    main()
