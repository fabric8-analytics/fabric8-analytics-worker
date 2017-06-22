import datetime
from selinon import FatalTaskError
from sqlalchemy.orm.exc import NoResultFound
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
            url = metadata_result.get('details', [{}])[0].get('code_repository', {}).get('url')
            if url is None:
                self.log.info('No upstream URL from metadata task provided')

            return url
        else:
            return arguments['url']

    def get_upstream_entry(self, db, package, url):
        """Update metadata in upstream entry tracking.
        
        :param db: database session to be used
        :param package: package entry
        :param url: provided URL
        :return: updated database entry corresponding the current package-level analysis
        """
        now = datetime.datetime.now()

        upstreams = db.query(Upstream)\
            .filter(Upstream.package_id == package.id) \
            .filter(Upstream.deactivated_at.is_(None))\
            .order_by(desc(Upstream.updated_at))\
            .all()

        # deactivate entries that have different upstream URL
        ret = None
        for entry in upstreams:
            if url is not None and entry.url != url:
                self.log.info("Marking upstream entry with id '%s' and URL '%s' for deactivation, "
                              "substituting with upstream URL '%s'", entry.id, entry.url, url)
                entry.deactivated_at = now
            else:
                self.log.info("Reusing already existing and active upstream record with id '%d' and upstream URL '%s'",
                              entry.id, entry.url)
                ret = entry

        if ret is None:
            if url is None:
                raise ValueError("No upstream URL provided and no previous active upstream records for %s/%s found"
                                 % (package.ecosystem.name, package.name))
            self.log.info("Creating new upstream record entry for package %s/%s and upstream URL '%s'",
                          package.ecosystem.name, package.name, url)
            ret = Upstream(
                package_id=package.id,
                url=url,
                updated_at=None,
                deactivated_at=None,
                added_at=now,
                active=True
            )
            db.add(ret)

        return ret

    def execute(self, arguments):
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('ecosystem'))

        # get rid of version if scheduled from the core analyses
        arguments.pop('version', None)

        db = self.storage.session
        ecosystem = Ecosystem.by_name(db, arguments['ecosystem'])
        package = Package.get_or_create(db, ecosystem_id=ecosystem.id, name=arguments['name'])
        upstream = self.get_upstream_entry(db, package, self.get_upstream_url(arguments))
        arguments['url'] = upstream.url

        if not arguments.get('force'):
            # can potentially schedule two flows of a same type at the same time as there is no lock,
            # but let's say it's OK
            if upstream.updated_at is not None \
                    and upstream.updated_at - datetime.datetime.now() < self._UPDATE_INTERVAL:
                self.log.info('Skipping upstream package check as data are considered as recent - last update %s.',
                              upstream.updated_at)
                # keep track of start, but do not schedule nothing more
                # discard changes like updates
                db.rollback()
                return arguments

        # if this fails, it's actually OK, as there could be concurrency
        package_analysis = PackageAnalysis(
            package_id=package.id,
            started_at=datetime.datetime.now(),
            finished_at=None
        )
        db.add(package_analysis)

        # keep track of updates
        upstream.updated_at = datetime.datetime.now()

        db.commit()
        arguments['document_id'] = package_analysis.id
        return arguments
