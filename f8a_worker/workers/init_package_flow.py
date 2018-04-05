"""Initialize package level analysis."""

import datetime
from selinon import FatalTaskError
from sqlalchemy.orm.exc import NoResultFound

from f8a_worker.base import BaseTask
from f8a_worker.models import Ecosystem, Package, Upstream, PackageAnalysis


class InitPackageFlow(BaseTask):
    """Initialize package-level analysis."""

    _UPDATE_INTERVAL = datetime.timedelta(days=5)

    @staticmethod
    def inject_arguments(arguments, document_id, package_id):
        """Injects arguments into given dictionary."""
        arguments['document_id'] = document_id
        arguments['package_id'] = package_id
        return arguments

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('ecosystem'))

        # get rid of version if scheduled from the core analyses
        arguments.pop('version', None)

        db = self.storage.session
        try:
            ecosystem = Ecosystem.by_name(db, arguments['ecosystem'])
        except NoResultFound:
            raise FatalTaskError('Unknown ecosystem: %r' % arguments['ecosystem'])
        package = Package.get_or_create(db, ecosystem_id=ecosystem.id, name=arguments['name'])
        package_analysis = db.query(PackageAnalysis) \
            .filter(PackageAnalysis.package_id == package.id) \
            .order_by(PackageAnalysis.started_at) \
            .first()

        if not arguments.get('force') and package_analysis is not None:
            if datetime.datetime.utcnow() - package_analysis.started_at < self._UPDATE_INTERVAL:
                InitPackageFlow.inject_arguments(arguments, package_analysis.id, package.id)
                return arguments
        package_analysis = PackageAnalysis(
            package_id=package.id,
            started_at=datetime.datetime.utcnow(),
            finished_at=None
        )
        db.add(package_analysis)
        db.commit()
        InitPackageFlow.inject_arguments(arguments, package_analysis.id, package.id)
        return arguments
