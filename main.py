"""CodyBuddy CLI — generate a small app from a natural-language prompt.

Usage:
    uv run main.py "Build a colourful calculator app in html css and js"
    uv run main.py            # prompts interactively
"""
import sys

from agent.graph import run


def main() -> None:
    if len(sys.argv) > 1:
        user_prompt = " ".join(sys.argv[1:])
    else:
        user_prompt = input("What should CodyBuddy build? ").strip()

    if not user_prompt:
        print("No prompt given. Exiting.")
        return

    run(user_prompt)
    print("\n✅ Build complete. See the ./generated_project directory.")


if __name__ == "__main__":
    main()
