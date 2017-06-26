import os

from f8a_worker import defaultconf
from f8a_worker.conf import get_configuration, F8aConfiguration, merge_dicts, ObjectBackend, \
    FileBackend


def test_get_value_with_override():
    c = F8aConfiguration(configuration_override={"asd": "qwe"})
    assert c.get(["asd"]) == "qwe"


def test_dict_merge():
    d = {"asd": "qwe", "a": {"a": "b"}}
    d2 = {"asd": "asd", "qwe": 123, "a": {"a": "c"}}
    merge_dicts(d, d2)
    assert d["asd"] == "asd"
    assert d["qwe"] == 123
    assert d["a"]["a"] == "c"


def test_configuration_is_a_singleton():
    assert id(get_configuration()) == id(get_configuration())


def test_get_postgres_conn():
    c = F8aConfiguration(backends=[
        ObjectBackend(defaultconf.data),
        FileBackend(path="/etc/f8a.json", graceful=True),
    ])
    assert c.postgres_connection == "postgres://coreapi:coreapi@localhost:5432/coreapi"


def test_npm_changes_url():
    c = F8aConfiguration()
    assert c.npmjs_changes_url == \
        "https://skimdb.npmjs.com/registry/_changes?descending=true&include_docs=true&feed=continuous"


def test_get_postgres_conn_with_environ_override():
    backup = os.environ["F8A_POSTGRES"]
    os.environ["F8A_POSTGRES"] = "something"
    c = F8aConfiguration()
    assert c.postgres_connection == "something"
    os.environ["F8A_POSTGRES"] = backup


def test_worker_data_dir_is_unset():
    c = F8aConfiguration(backends=[
        ObjectBackend(defaultconf.data),
    ])
    assert c.worker_data_dir is None


def test_file_config():
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "config.yaml"))
    c = F8aConfiguration(backends=[
        ObjectBackend({"test": "value2"}),
        FileBackend(config_path),
        ObjectBackend(defaultconf.data),
    ])
    assert c.get(["test"]) == "value"
    assert c.get(["test2", "asd"]) == "qwe"
    assert c.get(["test2", "asd"]) == "qwe"
    assert c.postgres_connection == "postgres://coreapi:coreapi@localhost:5432/coreapi"
