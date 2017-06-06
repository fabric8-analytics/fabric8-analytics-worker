import datetime
from cucoslib.base import BaseTask
from cucoslib.models import Analysis


class InitGitHubManifestMetadata(BaseTask):
    def execute(self, arguments):
        self._strict_assert(arguments.get('url'))
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('repo_name'))

        db = self.storage.session

        a = Analysis(started_at=datetime.datetime.now())
        db.add(a)
        db.commit()

        arguments['document_id'] = a.id
        return arguments
