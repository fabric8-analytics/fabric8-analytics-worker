"""Computes various digests of all files found in target cache path.

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
from f8a_worker.base import BaseTask
from f8a_worker.object_cache import ObjectCache
from f8a_worker.utils import TimedCommand, compute_digest
from f8a_worker.schemas import SchemaRef


class DigesterTask(BaseTask):
    """Computes various digests of all files found in target cache path."""

    _analysis_name = 'digests'
    schema_ref = SchemaRef(_analysis_name, '1-0-0')

    def compute_ssdeep(self, target):
        """Compute SSdeep piece-wise linear hash of target."""
        # 0 : ssdeep header
        # 1 : hash,filename
        data = TimedCommand.get_command_output(['ssdeep', '-c', '-s', target])
        try:
            return data[1].split(',')[0].strip()
        except IndexError as exc:
            self.log.error("unable to compute ssdeep of %r", target)
            raise RuntimeError("can't compute digest of %r" % target) from exc

    def compute_digests(self, cache_path, f, artifact=False):
        """Compute digests of tarball f."""
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
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))

        epv_cache = ObjectCache.get_from_dict(arguments)
        # cache_path = epv_cache.get_extracted_source_tarball()

        results = []
        # We don't compute digests of files in extracted tarball, only the tarball itself
        # for f in get_all_files_from(cache_path, path_filter=skip_git_files):
        #    results.append(self.compute_digests(cache_path, f))

        source_tarball_path = epv_cache.get_source_tarball()
        # Compute digests of tarball and mark it as such
        results.append(self.compute_digests(None, source_tarball_path, artifact=True))

        return {'summary': [], 'status': 'success', 'details': results}
