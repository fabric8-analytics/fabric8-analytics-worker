"""Tests for abstract data normalizer."""

import pytest
from f8a_worker.data_normalizer import AbstractDataNormalizer


@pytest.mark.parametrize('args, expected', [
    ({'keywords': None},
     []),
    ({'keywords': []},
     []),
    ({'keywords': ['x', 'y']},
     ['x', 'y']),
    ({'keywords': ''},
     ['']),
    ({'keywords': 'one'},
     ['one']),
    ({'keywords': 'one, two'},
     ['one', 'two']),
    ({'keywords': 'one two'},
     ['one', 'two']),
    ({'keywords': 'one two', 'separator': ' '},
     ['one', 'two']),
    ({'keywords': 'one, two', 'separator': ','},
     ['one', 'two']),
])
def test__split_keywords(args, expected):
    """Test AbstractDataNormalizer._split_keywords()."""
    assert AbstractDataNormalizer._split_keywords(**args) == expected


@pytest.mark.parametrize('args, expected', [
    # pick one key which IS there
    ({'data': {'author': 'me', 'version': '0.1.2'}, 'keymap': (('author',),)},
     {'author': 'me'}),
    # pick one key which IS NOT there
    ({'data': {'author-name': 'me', 'version': '0.1.2'}, 'keymap': (('author',),)},
     {'author': None}),
    # pick & and rename one key which IS there
    ({'data': {'author-name': 'me'}, 'keymap': (('author-name', 'author',),)},
     {'author': 'me'}),
    # pick & and rename one key which IS NOT there
    ({'data': {'authors': 'they'}, 'keymap': (('author-name', 'author',),)},
     {'author': None}),
    # pick one of keys
    ({'data': {'license': 'MIT'}, 'keymap': ((('license', 'licenses',), ),)},
     {'license': 'MIT'}),
    # pick one of keys
    ({'data': {'licenses': ['MIT', 'BSD']}, 'keymap': ((('license', 'licenses',),),)},
     {'licenses': ['MIT', 'BSD']}),
    # pick one of keys and rename it
    ({'data': {'license': 'MIT'}, 'keymap': ((('license', 'licenses',), 'declared_licenses'),)},
     {'declared_licenses': 'MIT'}),
])
def test__transform_keys(args, expected):
    """Test AbstractDataNormalizer.transform_keys()."""
    assert AbstractDataNormalizer._transform_keys(**args) == expected


@pytest.mark.parametrize('args, expected', [
    ({'name_email_dict': {'name': 'A', 'email': 'B@C.com'}},
     "A <B@C.com>"),
    ({'name_email_dict': {'name': 'A'}},
     "A"),
    ({'name_email_dict': {'email': 'B@C.com'}},
     "<B@C.com>"),
    ({'name_email_dict': {'author': 'A', 'author-email': 'B@C.com'},
      'name_key': 'author', 'email_key': 'author-email'},
     "A <B@C.com>"),
    ({'name_email_dict': {'url': 'https://github.com/o/p/issues', 'email': 'project@name.com'},
      'name_key': 'url'},
     "https://github.com/o/p/issues <project@name.com>"),
])
def test__join_name_email(args, expected):
    """Test AbstractDataNormalizer._join_name_email()."""
    assert AbstractDataNormalizer._join_name_email(**args) == expected
