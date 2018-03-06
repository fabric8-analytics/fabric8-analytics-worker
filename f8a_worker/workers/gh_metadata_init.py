"""Class to initialize Analysis."""

import datetime
from f8a_worker.base import BaseTask
from f8a_worker.models import Analysis


class InitGitHubManifestMetadata(BaseTask):
    """Initialize Analysis."""

    def execute(self, arguments):
        """Execute task."""
        self._strict_assert(arguments.get('url'))
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('repo_name'))

        db = self.storage.session

        a = Analysis(started_at=datetime.datetime.utcnow())
        db.add(a)
        db.commit()

        arguments['document_id'] = a.id
        return arguments
