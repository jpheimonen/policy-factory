"""Base store class for Policy Factory."""

from pathlib import Path

from .schema import init_db


class BaseStore:
    """Base store providing database connection initialization.

    This class serves as the root of the mixin composition hierarchy.
    It initializes the SQLite connection via init_db() and stores it
    as self.conn for use by all mixins.

    No domain-specific methods are defined here — those belong in mixins.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize the store with the given database path.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.conn = init_db(db_path)
