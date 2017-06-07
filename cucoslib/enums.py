from enum import IntEnum


class EcosystemBackend(IntEnum):
    # range will increase in case of adding new backend
    # none, nodejs, java, python, ruby, go, crates
    # NOTE: when altering this, you'll manually need to create a migration that alters
    #    cucoslib.models.Ecosystem by adding it to DB enum - see:
    #    http://stackoverflow.com/questions/14845203/altering-an-enum-field-using-alembic
    (none, npm, maven, pypi, rubygems, scm, crates) = range(7)


class SortOrder(IntEnum):
    ascending = 0
    descending = 1
