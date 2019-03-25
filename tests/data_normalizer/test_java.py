"""Tests for Java data normalizers."""

import pytest
from f8a_worker.data_normalizer import MavenDataNormalizer


@pytest.mark.parametrize('data, expected', [
    ({'pom.xml': {'dependencies': {'compile': {'g:a::': '1.0'}}}},
     {'dependencies': ['g:a 1.0']}),
    ({'pom.xml': {'dependencies': {'runtime': {'g:a::': '1.0'}}}},
     {'dependencies': ['g:a 1.0']}),
    ({'pom.xml': {'dependencies': {'provided': {'g:a::': '1.0'}}}},
     {'dependencies': ['g:a 1.0']}),
    ({'pom.xml': {'dependencies': {'test': {'g:a::': '1.0'}}}},
     {'devel_dependencies': ['g:a 1.0']}),
    ({'pom.xml': {'dependencies': {'compile': {'g:a::': '1.0', 'g2:a2::': '1.0.3-SNAPSHOT'},
                                   'test': {'t:t::': '0'},
                                   'runtime': {'r:r::': 'version'},
                                   'provided': {'p:p::': '1000'}}}},
     {'dependencies': sorted(['g:a 1.0', 'g2:a2 1.0.3-SNAPSHOT', 'r:r version', 'p:p 1000']),
      'devel_dependencies': sorted(['t:t 0'])}),
    ({'pom.xml': {'scm_url': 'git@github.com:fabric8-analytics/fabric8-analytics-worker.git'}},
     {'code_repository': {'url':
                          'git@github.com:fabric8-analytics/fabric8-analytics-worker.git',
                          'type': 'git'}}),
    ({'pom.xml': {'licenses': ['ASL 2.0', 'MIT']}},
     {'declared_licenses': ['ASL 2.0', 'MIT']}),
    ({'pom.xml': {'description': 'Ich bin ein Bayesianer'}},
     {'description': 'Ich bin ein Bayesianer'}),
    ({'pom.xml': {'url': 'https://github.com/fabric8-analytics/fabric8-analytics-worker'}},
     {'homepage': 'https://github.com/fabric8-analytics/fabric8-analytics-worker'}),
])
def test_transforming_java_data(data, expected):
    """Test normalizing of pom.xml data."""
    transformed_data = MavenDataNormalizer(data).normalize()
    for key, value in expected.items():
        assert key in transformed_data
        transformed_value = sorted(transformed_data[key]) \
            if isinstance(transformed_data[key], list) else transformed_data[key]
        assert transformed_value == value, transformed_data


def test_constructor_error_input():
    """Test MavenDataNormalizer constructor for error input."""
    dn = MavenDataNormalizer({})
    assert dn is not None


def test_normalize_error_input():
    """Test MavenDataNormalizer constructor for error input."""
    dn = MavenDataNormalizer({})
    assert dn is not None
    n = dn.normalize()
    assert n == {}
