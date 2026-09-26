"""Render paid-plan pre-deploy gate: config -> migrations -> live dependencies."""

from scripts.check_production_config import main as check_config
from scripts.check_production_dependencies import main as check_dependencies
from scripts.run_production_migrations import main as run_migrations


def main() -> None:
    check_config()
    run_migrations()
    check_dependencies()
    print("Render pre-deploy gate: PASS")


if __name__ == "__main__":
    main()
