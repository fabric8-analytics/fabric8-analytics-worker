from f8a_worker.blackduck_helpers import BlackDuckProject, BlackDuckRelease

from datetime import datetime

NOW = datetime.utcnow()

_RELEASE_DEF = {
    'version': '0.6.0',
    'versionId': 'abcdef123456',
    'releasedOn': NOW.isoformat() + 'Z',
}

_PROJECT_DEF = {
    'name': 'foobar',
    'id': 'aaaaa11111',
    'canonicalReleaseId': 'abcdef123456',
    'keyWithUrl': 'foo',
    'anotherKeyWithUrl': 'bar',
    'yetAnotherKeyWithUrl': 'baz',
}


def test_blackduck_project():
    project = BlackDuckProject(_PROJECT_DEF)
    assert project.name == 'foobar'
    assert project.id == 'aaaaa11111'
    assert project.canonical_release_id == 'abcdef123456'
    assert project.urls == {'keyWithUrl': 'foo',
                            'anotherKeyWithUrl': 'bar',
                            'yetAnotherKeyWithUrl': 'baz'}


def test_blackduck_release():
    release = BlackDuckRelease(_RELEASE_DEF, 'phonyId')
    assert release.id == 'abcdef123456'
    assert release.version == '0.6.0'
    assert release.released_at == NOW
