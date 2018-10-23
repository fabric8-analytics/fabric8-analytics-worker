"""Common enumerations used across the project."""

from enum import IntEnum


class EcosystemBackend(IntEnum):
    """Backends for all supported ecosystems."""

    # range will increase in case of adding new backend
    # none, nodejs, java, python, ruby, go, crates
    # NOTE: when altering this, you'll manually need to create a migration that alters
    #    f8a_worker.models.Ecosystem by adding it to DB enum - see:
    #    http://stackoverflow.com/questions/14845203/altering-an-enum-field-using-alembic
    (none, npm, maven, pypi, rubygems, scm, crates, nuget, go) = range(9)


class SortOrder(IntEnum):
    """Sort orders."""

    ascending = 0
    descending = 1
