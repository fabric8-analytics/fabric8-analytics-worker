"""Tests for data normalizers."""

import json
from pathlib import Path
import pytest

from f8a_worker.data_normalizer import normalize


def compare_dictionaries(a, b):
    """Compare dictionaries a and b."""
    def mapper(item):
        if isinstance(item, list):
            return frozenset(map(mapper, item))
        if isinstance(item, dict):
            return frozenset({mapper(k): mapper(v) for k, v in item.items()}.items())
        return item

    return mapper(a) == mapper(b)


def _load_json(f):
    """Load json from f."""
    with (Path(__file__).parent / 'data/dataNormalizer' / f).open(encoding='utf-8') as fd:
        return json.load(fd)


def test_transforming_setup_py():
    """Test normalizing of data from setup.py."""
    data = _load_json('setup-py-from-mercator')
    expected = _load_json('setup-py-expected')
    assert normalize(data['items'][0]) == expected


def test_transforming_pkginfo():
    """Test normalizing of data from PKG-INFO."""
    data = _load_json('PKG-INFO-from-mercator')
    expected = _load_json('PKG-INFO-expected')
    assert normalize(data['items'][0]) == expected


def test_transforming_requirements_txt():
    """Test normalizing of data from requirements.txt."""
    data = _load_json('requirements-txt-from-mercator')
    expected = _load_json('requirements-txt-expected')
    assert normalize(data['items'][0]) == expected


def test_transforming_metadata_json():
    """Test normalizing of data from metadata.json."""
    data = _load_json('metadata-json-from-mercator')
    expected = _load_json('metadata-json-expected')
    assert normalize(data['items'][0]) == expected


def test_transforming_npm_shrinkwrap_data():
    """Test normalizing of npm's shrinkwrap.json data."""
    data = _load_json('npm-with-shrinkwrap-json-from-mercator')
    expected = _load_json('npm-with-shrinkwrap-json-expected')
    assert compare_dictionaries(normalize(data), expected)


def test_transforming_java():
    """Test normalizing of pom.xml data."""
    data = _load_json('pom-xml-from-mercator')
    expected = _load_json('pom-xml-expected')
    assert compare_dictionaries(normalize(data['items'][0]), expected)


def test_transforming_gradle():
    """Test normalizing of pom.xml data."""
    data = _load_json('gradle-from-mercator')
    expected = _load_json('gradle-expected')
    assert compare_dictionaries(normalize(data['items'][0]), expected)


def test_transforming_nuspec():
    """Test normalizing of nuspec data."""
    data = _load_json('nuspec-from-mercator')
    expected = _load_json('nuspec-expected')
    assert compare_dictionaries(normalize(data['items'][0]), expected)


def test_transforming_go_glide():
    """Test normalizing of go glide (with locked deps) data."""
    data = _load_json('go-glide-from-mercator')
    expected = _load_json('go-glide-expected')
    assert compare_dictionaries(normalize(data['items'][0]), expected)


@pytest.mark.parametrize('data, expected', [
    ({'ecosystem': 'gofedlib', 'result': {
        'deps-main': [],
        'deps-packages': ['https://github.com/gorilla/context']}},
     {'ecosystem': 'gofedlib', 'dependencies': ['github.com/gorilla/context']}),
    ({'ecosystem': 'gofedlib',
      'result': {'deps-main': ['https://github.com/gorilla/sessions',
                               'https://github.com/gorilla/context'],
                 'deps-packages': ['https://github.com/gorilla/context']}},
     {'ecosystem': 'gofedlib', 'dependencies': ['github.com/gorilla/context',
                                                'github.com/gorilla/sessions']}),
])
def test_transforming_gofedlib_data(data, expected):
    """Test normalizing of gofedlib data."""
    transformed_data = normalize(data)
    for key, value in expected.items():
        assert key in transformed_data
        actual_value = transformed_data[key]
        if isinstance(actual_value, list):
            actual_value.sort()
        assert actual_value == value
