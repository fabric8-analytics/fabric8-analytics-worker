"""
output: list of files in directory and along with their hashes (md5, sha1, sha256, ssdeep)

sample output:
{
  "summary": [],
  "details": [
    {
      "path": "/tmp/tmpZpKc0F/package_data/package/README_md",
      "sha1": "3e52a79b51274622b87b511a0706049186d40d2e",
      "ssdeep": "96:FXhLxwnIRX0Fcbf21gd+MHk/ZmVAFPPM61jTI:FHQHFUfcgd+j/O8O",
      "md5": "587a081bb5576be3c58acc948659386a",
      "sha256": "5ddc3e5ab3baebd6b3075955f45b8f90d099db9cb915c570038c14812301debf"
    }
  ]
}
"""

import os
from f8a_worker.utils import (
    get_all_files_from, TimedCommand, skip_git_files, compute_digest
)
from f8a_worker.schemas import SchemaRef
from f8a_worker.base import BaseTask
from f8a_worker.object_cache import ObjectCache


class DigesterTask(BaseTask):
    _analysis_name = 'digests'
    schema_ref = SchemaRef(_analysis_name, '1-0-0')
    description = 'Computes various digests of all files found in target cache path'

    def compute_ssdeep(self, target):
        """ Compute SSdeep piece-wise linear hash of target """
        # 0 : ssdeep header
        # 1 : hash,filename
        data = TimedCommand.get_command_output(['ssdeep', '-c', '-s', target])
        try:
            return data[1].split(',')[0].strip()
        except IndexError:
            self.log.error("unable to compute ssdeep of %r", target)
            raise RuntimeError("can't compute digest of %r" % target)

    def compute_digests(self, cache_path, f, artifact=False):
        f_digests = {
            'sha256': compute_digest(f, 'sha256'),
            'sha1': compute_digest(f, 'sha1'),
            'md5': compute_digest(f, 'md5'),
            'ssdeep': self.compute_ssdeep(f)
        }

        if artifact:
            f_digests['artifact'] = True
            f_digests['path'] = os.path.basename(f)
        else:
            f_digests['path'] = os.path.relpath(f, cache_path)

        return f_digests

    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))

        epv_cache = ObjectCache.get_from_dict(arguments)
        cache_path = epv_cache.get_extracted_source_tarball()

        results = []
        for f in get_all_files_from(cache_path, path_filter=skip_git_files):
            results.append(self.compute_digests(cache_path, f))

        # In case of nodejs, prior to npm-2.x.x (Fedora 24)
        # npm client was repackaging modules on download.
        # It modified file permissions inside package.tgz so they matched UID/GID
        # of a user running npm command. Therefore its digest was different
        # then of a tarball downloaded directly from registry.npmjs.org.
        source_tarball_path = epv_cache.get_source_tarball()
        results.append(self.compute_digests(source_tarball_path, source_tarball_path, artifact=True))

        return {'summary': [], 'status': 'success', 'details': results}
