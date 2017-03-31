"""
https://github.com/github/linguist


Output: list of files along with languages they're written in

## sample output from linguist

$ linguist /usr/lib/python2.7/site-packages/celery/five.py
five.py: 394 lines (303 sloc)
  type:      Text
  mime type: application/x-python
  language:  Python


## how to test

$ celery -A cucoslib.workers worker -Q LinguistTask_v1 -l debug --autoreload

```python
from cucoslib.workers import LinguistTask
from cucoslib.worker import app
x = LinguistTask()
arguments = {'cache_path': "/usr/lib/python2.7/site-packages/enum/"}
x.call(arguments)
```

"""

import re
import os

from cucoslib.utils import (
    TimedCommand, get_all_files_from, skip_git_files, ThreadPool
)
from cucoslib.schemas import SchemaRef
from cucoslib.base import BaseTask
from cucoslib.object_cache import ObjectCache


class LinguistTask(BaseTask):
    _analysis_name = 'languages'
    description = "GitHub's tool to figure out what language is used in code"
    schema_ref = SchemaRef(_analysis_name, '1-0-0')

    def _parse_linguist(self, output):
        if not output:
            return None

        def extract_value(line):
            """ `language:   Python` -> `Python` """
            return line.split(':', 1)[1].strip()
        lines_matcher = re.compile('(\d+) lines \((\d+) sloc\)')
        m = lines_matcher.search(output[0])
        lines, sloc = 0, 0
        if m:
            lines, sloc = int(m.groups(1)[0]), int(m.groups(2)[0])
        tml = zip(['type', 'mime', 'language'],
                  [extract_value(l) for l in output[1:4]])
        data = dict(tml,
                    lines=lines,
                    sloc=sloc)
        return data

    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))

        results = []
        cache_path = ObjectCache.get_from_dict(arguments).get_extracted_source_tarball()

        def worker(path):
            mime = TimedCommand.get_command_output(['file', path, '-b', '-i']).pop()
            self.log.debug("%s mime = %s", path, mime)
            typ = TimedCommand.get_command_output(['file', path, '-b'])
            self.log.debug("%s filetype = %s", path, typ)

            linguist = None
            if 'charset=binary' not in mime:
                linguist = self._parse_linguist(
                    TimedCommand.get_command_output(['linguist', path])
                )
                self.log.debug("%s linguist output = %s", path, linguist)

            results.append({
                "type": typ,
                "output": linguist,
                "path": os.path.relpath(path, cache_path),
            })

        with ThreadPool(target=worker) as tp:
            for path in get_all_files_from(cache_path, path_filter=skip_git_files):
                tp.add_task(path)

        return {'summary': [], 'status': 'success', 'details': results}
