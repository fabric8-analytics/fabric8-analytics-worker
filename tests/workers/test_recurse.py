from cucoslib.dispatcher.foreach import _is_url_dependency


def test__is_url_dependency():
    data = [
        ({"name": "test2", "version": "1.0.0"}, False),
        ({"name": "test3", "version": "http://some.tar/ball.tgz"}, True),
        ({"name": "test4", "version": "git://some.git/repo.git"}, True),
        ({"name": "git+https://some.other/git/repo", "version": None}, True),
    ]

    for d, is_url_dep in data:
        assert _is_url_dependency(d) == is_url_dep
