# Working with SQL Alchemy and Alembic

## Creating migrations

Upstream documentation: http://alembic.zzzcomputing.com/en/latest/tutorial.html#create-a-migration-script

To create a migration:
* do the actual model change
* run `hack/generate-db-migrations.sh revision --autogenerate -m 'name of the change'` (if this fails with message saying that PostgreSQL isn't available, try increasing amount of seconds to sleep in the script and rerun)
* find the generated file in `alembic/versions/` and fix its ownership (it will have root permissions when generated and there's no easy way around that)
