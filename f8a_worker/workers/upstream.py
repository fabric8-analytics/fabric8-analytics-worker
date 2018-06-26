"""Upstream Task."""
from f8a_worker.base import BaseTask
from f8a_worker.models import Upstream
import datetime


class UpstreamUpdateTask(BaseTask):
    """Update Upstream URL in database."""

    def get_upstream_url(self, arguments):
        """Get upstream URL from metadata."""
        if 'url' not in arguments:
            if 'metadata' not in arguments:
                self.log.info('No upstream URL provided, will reuse URL from previous runs')
                return None

            metadata_result = arguments.get('metadata')
            code_repository = metadata_result.get('details', [{}])[0].get('code_repository', {})
            url = code_repository.get('url') if code_repository else None
            if url is None:
                self.log.info('No upstream URL from metadata task provided')
            return url
        return arguments['url']

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self._strict_assert(arguments.get('package_id'))

        url = self.get_upstream_url(arguments)
        db = self.storage.session

        upstreams = db.query(Upstream) \
            .filter(Upstream.package_id == arguments['package_id']) \
            .order_by(Upstream.updated_at) \
            .all()

        upstream = None

        # if given url is none we can either update existing entry or create new one
        if url is None:
            if upstreams:
                upstream = upstreams[0]
                self.log.info("No URL available, so returning latest upstream entry with id '%d'",
                              upstream.id)
                upstream.updated_at = datetime.datetime.utcnow()
            else:
                upstream = Upstream(
                    package_id=arguments['package_id'],
                    updated_at=datetime.datetime.utcnow()
                )
                db.add(upstream)
            return arguments

        # if there is no existing entry we will create new one
        if not upstreams and url:
            upstream = Upstream(
                package_id=arguments['package_id'],
                updated_at=datetime.datetime.utcnow(),
                url=url
            )
            db.add(upstream)
            return arguments

        # if there is existing entry we will get one with matching query and update
        ret = [entry for entry in upstreams if entry.url == url]
        if ret:
            upstream = ret[0]
            self.log.info("Using latest existing upstream record with id '%d'and upstream URL '%s'",
                          upstream.id, upstream.url)
            upstream.updated_at = datetime.datetime.utcnow()
            return arguments

        # if there is no matching url entry create new one with entry
        if upstream is None:
            self.log.info("Creating new upstream record entry for package %s/%s and "
                          "upstream URL '%s'", arguments['ecosystem'], arguments['name'], url)
            upstream = Upstream(
                package_id=arguments['package_id'],
                url=url
            )
            db.add(upstream)
            return arguments
