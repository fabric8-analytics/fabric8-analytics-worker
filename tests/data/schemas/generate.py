#!/usr/bin/env python3

"""Script to generate all new schemas for workers."""

from collections import OrderedDict
import json
from pathlib import Path
import sys

from f8a_worker.schemas import load_all_worker_schemas

if sys.version_info[0] < 3:
    print('Must be run under Python 3, since Python 2 adds trailing whitespaces to JSON')
    sys.exit(1)


here = Path(__file__).parent

for ref, schema in load_all_worker_schemas().items():
    # we don't want to overwrite previously generated schemas
    fname = here / '{}-v{}.schema.json'.format(*ref)
    if fname.exists():
        print('{} already exists, skipping'.format(fname))
        continue
    if 'definitions' in schema:
        definitions = schema['definitions'].items()
        schema['definitions'] = OrderedDict(sorted(definitions))
    # write schema
    with fname.open('w') as f:
        json.dump(schema, f, indent=4)
