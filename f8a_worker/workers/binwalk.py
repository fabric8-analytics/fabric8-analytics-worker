"""
Find and extract interesting files / data from binary images.

Uses http://binwalk.org/

Output: list of files in directory along with output of binwalk tool

TODO: What is interesting mean? What is done with the data?

## sample output from binwalk

$ binwalk -B /usr/bin/gcc

DECIMAL       HEXADECIMAL     DESCRIPTION
--------------------------------------------------------------------------------
0             0x0             ELF 64-bit LSB executable, AMD x86-64, version 1 (SYSV)
496456        0x79348         Copyright string: " %s 2015 Free Software Foundation, Inc.on, Inc."
635119        0x9B0EF         mcrypt 2.2 encrypted data, algorithm: blowfish-448, mode: CBC, keymode: 8bit
913704        0xDF128         LZMA compressed data, properties: 0xB8, dictionary size: 16777216 bytes, uncompressed size: 33554432 bytes
914664        0xDF4E8         LZMA compressed data, properties: 0x51, dictionary size: 16777216 bytes, uncompressed size: 33554432 bytes
915112        0xDF6A8         LZMA compressed data, properties: 0xCF, dictionary size: 16777216 bytes, uncompressed size: 50331648 bytes
915176        0xDF6E8         LZMA compressed data, properties: 0xAB, dictionary size: 16777216 bytes, uncompressed size: 50331648 bytes

sample output of this task:
"binary_data": {
  "details": [
    {
      "path": "/tmp/tmpVEA6E_/package_data/six-1_10_0-py2_py3-none-any_whl",
      "output": [
        "Zip archive data, at least v2.0 to extract, compressed size: 7496,  uncompressed size: 30098, name: \"six.py\"",
        "Zip archive data, at least v2.0 to extract, compressed size: 424,  uncompressed size: 774, name: \"six-1.10.0.dist-info/DESCRIPTION.rst\"",
        ...
        "End of Zip archive"
      ]
    },
    {
      "path": "/tmp/tmpVEA6E_/package_data/six_py",
      "output": [
        "Copyright string: \" (c) 2010-2015 Benjamin Petersonn\""
      ]
    }
  ]
}
"""

import os
from f8a_worker.object_cache import ObjectCache
from f8a_worker.utils import TimedCommand, get_all_files_from, skip_git_files
from f8a_worker.base import BaseTask
from f8a_worker.schemas import SchemaRef


class BinwalkTask(BaseTask):
    _analysis_name = 'binary_data'
    schema_ref = SchemaRef(_analysis_name, '1-0-0')
    description = "Find and extract interesting files / data from binary images"

    def parse_binwalk(self, output):
        if not output:
            return None
        import re
        matcher = re.compile('^\d{,8}\s*0x[A-Fa-f0-9]{,8}\s*(.*)$')
        matched = []
        for line in output:
            match = matcher.match(line)
            if match:
                matched.append(match.groups(1)[0])
        return matched

    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))

        cache_path = ObjectCache.get_from_dict(arguments).get_source_tarball()

        results = []
        for path in get_all_files_from(cache_path, path_filter=skip_git_files):
            self.log.debug("path = %s", path)

            bw = TimedCommand(['binwalk', '-B', path])
            status, output, error = bw.run(timeout=60)
            self.log.debug("status = %s, error = %s", status, error)
            self.log.debug("output = %s", output)

            parsed_binwalk = self.parse_binwalk(output)
            results.append({
                "path": os.path.relpath(path, cache_path),
                "output": parsed_binwalk,
            })
        return {'summary': [], 'status': 'success', 'details': results}
