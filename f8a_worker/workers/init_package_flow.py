import datetime
from sqlalchemy import desc
from f8a_worker.base import BaseTask
from f8a_worker.models import Ecosystem, Package, Upstream, PackageAnalysis


class InitPackageFlow(BaseTask):
    _UPDATE_INTERVAL = datetime.timedelta(days=5)

    def get_upstream_url(self, arguments):
        if 'url' not in arguments:
            if 'metadata' not in self.parent.keys():
                self.log.info('No upstream URL provided, will reuse URL from previous runs')
                return None

            metadata_result = self.parent_task_result('metadata')
            code_repository = metadata_result.get('details', [{}])[0].get('code_repository', {})
            url = code_repository.get('url') if code_repository else None
            if url is None:
                self.log.info('No upstream URL from metadata task provided')

            return url
        else:
            return arguments['url']

    def get_upstream_entry(self, package, url):
        """Update metadata in upstream entry tracking.

        :param package: package entry
        :param url: provided URL
        :return: updated database entry corresponding the current package-level analysis
        """
        db = self.storage.session
        now = datetime.datetime.utcnow()

        upstreams = db.query(Upstream)\
            .filter(Upstream.package_id == package.id) \
            .filter(Upstream.deactivated_at.is_(None))\
            .order_by(Upstream.updated_at)\
            .all()

        ret = None
        for entry in upstreams:
            if url is not None and entry.url != url:
                self.log.info("Marking upstream entry with id '%s' and URL '%s' for deactivation, "
                              "substituting with upstream URL '%s'", entry.id, entry.url, url)
                # deactivate entries that have different upstream URL
                entry.deactivated_at = now
            else:
                self.log.info("Reusing already existing and active upstream record with id '%d' "
                              "and upstream URL '%s'", entry.id, entry.url)
                ret = entry
        return ret

    def add_or_update_upstream(self, package, url):
        """Add/update package & url in monitored_upstreams table.

        :param package: package entry
        :param url: provided URL
        :return: added or updated database entry
        """
        db = self.storage.session
        now = datetime.datetime.utcnow()

        older_upstream = db.query(Upstream) \
            .filter(Upstream.package_id == package.id) \
            .filter(Upstream.deactivated_at.isnot(None)) \
            .filter(Upstream.url == url) \
            .order_by(desc(Upstream.updated_at)) \
            .first()
        if older_upstream:
            self.log.info("Activating older upstream record entry for package %s/%s and "
                          "upstream URL '%s'", package.ecosystem.name, package.name, url)
            # The updated_at field will be updated in execute()
            older_upstream.deactivated_at = None
            entry = older_upstream
        else:
            self.log.info("Creating new upstream record entry for package %s/%s and "
                          "upstream URL '%s'", package.ecosystem.name, package.name, url)
            new_upstream = Upstream(
                package_id=package.id,
                url=url,
                updated_at=None,
                deactivated_at=None,
                added_at=now
            )
            db.add(new_upstream)
            entry = new_upstream

        return entry

    def execute(self, arguments):
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('ecosystem'))

        # get rid of version if scheduled from the core analyses
        arguments.pop('version', None)

        db = self.storage.session
        ecosystem = Ecosystem.by_name(db, arguments['ecosystem'])
        package = Package.get_or_create(db, ecosystem_id=ecosystem.id, name=arguments['name'])
        url = self.get_upstream_url(arguments)
        upstream = self.get_upstream_entry(package, url)
        if upstream is None:
            upstream = self.add_or_update_upstream(package, url)
        arguments['url'] = upstream.url

        if not arguments.get('force'):
            # can potentially schedule two flows of a same type at the same
            # time as there is no lock, but let's say it's OK
            if upstream.updated_at is not None \
                    and upstream.updated_at - datetime.datetime.utcnow() < self._UPDATE_INTERVAL:
                self.log.info('Skipping upstream package check as data are considered as recent - '
                              'last update %s.',
                              upstream.updated_at)
                # keep track of start, but do not schedule nothing more
                # discard changes like updates
                db.rollback()
                return arguments

        # if this fails, it's actually OK, as there could be concurrency
        package_analysis = PackageAnalysis(
            package_id=package.id,
            started_at=datetime.datetime.utcnow(),
            finished_at=None
        )
        db.add(package_analysis)

        # keep track of updates
        upstream.updated_at = datetime.datetime.utcnow()

        db.commit()
        arguments['document_id'] = package_analysis.id
        return arguments
