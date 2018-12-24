"""Data normalizer API.

The purpose of data normalizers is to process output
from `mercator-go` command line tool and normalize it.

Ecosystem-specific implementations live in their respective modules,
e.g.: NPM data normalizer can be found in `javascript` module.

All normalizers inherit from `f8a_worker.data_normalizer.AbstractDataNormalizer` class.
"""

import argparse
import json
import sys

from f8a_worker.data_normalizer.abstract import AbstractDataNormalizer
from f8a_worker.data_normalizer.csharp import NugetDataNormalizer
from f8a_worker.data_normalizer.go import (
    GoGlideDataNormalizer, GoFedlibDataNormalizer, GodepsDataNormalizer
)
from f8a_worker.data_normalizer.java import MavenDataNormalizer, GradleDataNormalizer
from f8a_worker.data_normalizer.javascript import NpmDataNormalizer
from f8a_worker.data_normalizer.python import (
    PythonDistDataNormalizer, PythonDataNormalizer, PythonRequirementsTxtDataNormalizer
)


def normalize(mercator_output):
    """Normalize mercator output.

    :param mercator_output: dict, output from mercator-go
    """
    normalizers = {
        'python': PythonDataNormalizer,
        'python-dist': PythonDistDataNormalizer,
        'python-requirementstxt': PythonRequirementsTxtDataNormalizer,
        'npm': NpmDataNormalizer,
        'java-pom': MavenDataNormalizer,
        'dotnetsolution': NugetDataNormalizer,
        'gofedlib': GoFedlibDataNormalizer,
        'go-glide': GoGlideDataNormalizer,
        'go-godeps': GodepsDataNormalizer,
        'gradlebuild': GradleDataNormalizer
    }

    ecosystem = mercator_output.get('ecosystem', '').lower()
    normalizer = normalizers.get(ecosystem)
    if not normalizer:
        raise ValueError('Unsupported ecosystem: {e}'.format(e=ecosystem))

    result = normalizer(mercator_output.get('result', {})).normalize() or {}
    result['ecosystem'] = ecosystem
    return result


def _dict2json(o, pretty=True):
    """Serialize dictionary to json."""
    kwargs = {}
    if pretty:
        kwargs['sort_keys'] = True,
        kwargs['separators'] = (',', ': ')
        kwargs['indent'] = 4

    return json.dumps(o, **kwargs)


def _main():
    """Read Mercator produced data from stdin and process."""
    parser = argparse.ArgumentParser(sys.argv[0],
                                     description='Data normalizer for mercator')
    parser.add_argument('--no-pretty', dest='no_pretty', action='store_true',
                        help='do not print nicely formatted JSON')
    args = parser.parse_args()

    content = json.load(sys.stdin)

    if content:
        items = content.get('items') or []
        for item in items:
            item['result'] = normalize(item)

    print(_dict2json(content, pretty=not args.no_pretty))

    return 0


if __name__ == "__main__":
    sys.exit(_main())
