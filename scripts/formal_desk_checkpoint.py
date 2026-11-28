"""Rolling Desk workflow entry point for the shared immutable Live checkpoint."""
from publication_coverage import (
    bind_checkpoint as detach,
    effective_live,
    main,
    validate_editorial,
)


if __name__ == "__main__":
    raise SystemExit(main())
