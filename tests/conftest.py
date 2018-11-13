"""Configuration for unit tests."""

import pytest
from flexmock import flexmock

from f8a_worker.enums import EcosystemBackend
from f8a_worker.models import Base, Ecosystem, create_db_scoped_session
from f8a_worker.setup_celery import get_dispatcher_config_files
from f8a_worker.storages import AmazonS3
from selinon import Config

# To use fixtures from this file, either name them as an input argument or use 'usefixtures' marker
# https://docs.pytest.org/en/latest/fixture.html#using-fixtures-from-classes-modules-or-projects


@pytest.fixture
def rdb():
    """Provide connection to a database."""
    session = create_db_scoped_session()
    # TODO: we may need to run actual migrations here
    # make sure all session objects from scoped_session get closed here
    #  otherwise drop_all() would hang indefinitely
    session.close_all()
    # NOTE: this also drops any data created by fixtures (e.g. builtin ecosystems),
    #   so if you want to use these, create them by hand before running your tests
    # We can't use Base.metadata.drop_all(bind=session.bind), since they may be tables from
    #   e.g. bayesian server, that reference f8a_worker tables and will prevent dropping them
    tables = session.bind.table_names()
    for t in tables:
        session.execute('drop table if exists "{t}" cascade'.format(t=t))
        session.commit()
    Base.metadata.create_all(bind=session.bind)
    return session


@pytest.fixture
def maven(rdb):
    """Prepare database with Maven ecosystem."""
    maven = Ecosystem(name='maven', backend=EcosystemBackend.maven,
                      fetch_url='https://repo.maven.apache.org/maven2/')
    rdb.add(maven)
    rdb.commit()
    return maven


@pytest.fixture
def npm(rdb):
    """Prepare database with NPM ecosystem."""
    npm = Ecosystem(name='npm', backend=EcosystemBackend.npm,
                    fetch_url='https://registry.npmjs.org/')
    rdb.add(npm)
    rdb.commit()
    return npm


@pytest.fixture
def pypi(rdb):
    """Prepare database with Pypi ecosystem."""
    pypi = Ecosystem(name='pypi', backend=EcosystemBackend.pypi,
                     fetch_url='https://pypi.org/pypi/')
    rdb.add(pypi)
    rdb.commit()
    return pypi


@pytest.fixture
def rubygems(rdb):
    """Prepare database with Ruby gems ecosystem."""
    rubygems = Ecosystem(name='rubygems', backend=EcosystemBackend.rubygems,
                         fetch_url='https://rubygems.org/api/v1')
    rdb.add(rubygems)
    rdb.commit()
    return rubygems


@pytest.fixture
def nuget(rdb):
    """Prepare database with Nuget ecosystem."""
    nuget = Ecosystem(name='nuget', backend=EcosystemBackend.nuget,
                      fetch_url='https://api.nuget.org/packages/')
    rdb.add(nuget)
    rdb.commit()
    return nuget


@pytest.fixture
def go(rdb):
    """Prepare database with Go ecosystem."""
    e = Ecosystem(name='go', backend=EcosystemBackend.go, fetch_url='')
    rdb.add(e)
    rdb.commit()
    return e


@pytest.fixture()
def dispatcher_setup():
    """Perform environment setup for Dispatcher if needed."""
    nodes_yaml, flows_yaml = get_dispatcher_config_files()
    Config.set_config_yaml(nodes_yaml, flows_yaml)


@pytest.fixture()
def no_s3_connection():
    """Mock the connection to S3."""
    flexmock(AmazonS3).should_receive('is_connected').and_return(True)
