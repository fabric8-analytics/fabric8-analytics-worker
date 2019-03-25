"""Tests for Java data normalizers."""

import pytest
from f8a_worker.data_normalizer import PythonDataNormalizer


@pytest.mark.parametrize('data,keymap,expected', [
    # pick one key which IS there
    ({'author': 'me', 'version': '0.1.2'}, (('author',),), {'author': 'me'}),
    # pick one key which IS NOT there
    ({'author-name': 'me', 'version': '0.1.2'}, (('author',),),
     {'author': None}),
    # pick & and rename one key which IS there
    ({'author-name': 'me'}, (('author-name', 'author',),),
     {'author': 'me'}),
    # pick & and rename one key which IS NOT there
    ({'authors': 'they'}, (('author-name', 'author',),),
     {'author': None}),
    # pick one of keys
    ({'license': 'MIT'}, ((('license', 'licenses',), ),),
     {'license': 'MIT'}),
    # pick one of keys
    ({'licenses': ['MIT', 'BSD']}, ((('license', 'licenses',),),),
     {'licenses': ['MIT', 'BSD']}),
    # pick one of keys and rename it
    ({'license': 'MIT'}, ((('license', 'licenses',), 'declared_licenses'),),
     {'declared_licenses': 'MIT'}),
])
def test_constructor(data, keymap, expected):
    """Test AbstractDataNormalizer constructor."""
    dn = PythonDataNormalizer(data)
    assert dn is not None
    assert keymap
    assert expected


def test_constructor_error_input():
    """Test AbstractDataNormalizer constructor for error input."""
    dn = PythonDataNormalizer("error")
    assert dn is not None
