# Running alembic for auto generation of scripts

You need to have your virtual environment setup and have alembic installed seperately via pip as it is not part of requirements.txt

You need to run the alembic command from the directory in which alembic.ini is located

1. You may need to add the following to alembic/env.py because some of the module imports are not in the system path.
    import sys
    sys.path = ['', '..'] + sys.path[1:]
2. Update [models.py](../f8a_worker/models.py) to add the required changes to the schema.
3. Enable port forwarding to the DB instance in your dev cluster. This is required because alembic needs to find the 
   difference between the schema in models.p and the database 
    while [ 1 ]; do oc port-forward `<your pgbouncer pod id`> 5432:5432; done
4. Run alembic revision --autogenerate -m "`<your message`>"

