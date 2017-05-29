from sqlalchemy import (Column, DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint,
                        create_engine, func, Text, Boolean, Float)
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, scoped_session, sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.session import Session
from sqlalchemy.pool import NullPool

from cucoslib.conf import get_configuration
from cucoslib.enums import EcosystemBackend

configuration = get_configuration()


def create_db_scoped_session(connection_string=None):
    # we use NullPool, so that SQLAlchemy doesn't pool local connections
    #  and only really uses connections while writing results
    return scoped_session(
        sessionmaker(bind=create_engine(
            connection_string or configuration.postgres_connection,
            poolclass=NullPool)))


class BayesianModelMixin(object):
    """Subclasses of this class will gain some `by_*` class methods. Note, that these should
    only be used to obtain objects by unique attribute (or combination of attributes that
    make the object unique), since under the hood they use SQLAlchemy's `.one()`.

    Also note, that these class methods will raise sqlalchemy.rom.exc.NoResultFound if the object
    is not found.
    """
    def to_dict(self):
        d = {}
        for column in self.__table__.columns:
            d[column.name] = getattr(self, column.name)

        return d

    @classmethod
    def _by_attrs(cls, session, **attrs):
        return session.query(cls).filter_by(**attrs).one()

    @classmethod
    def by_id(cls, session, id):
        return cls._by_attrs(session, id=id)

    @classmethod
    def get_or_create(cls, session, **attrs):
        try:
            return cls._by_attrs(session, **attrs)
        except NoResultFound:
            try:
                o = cls(**attrs)
                session.add(o)
                session.commit()
                return o
            except IntegrityError:  # object was created in the meanwhile by someone else
                return cls._by_attrs(**attrs)


Base = declarative_base(cls=BayesianModelMixin)


class Ecosystem(Base):
    __tablename__ = 'ecosystems'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True)
    url = Column(String(255))
    fetch_url = Column(String(255))
    _backend = Column(Enum(*[b.name for b in EcosystemBackend], name='ecosystem_backend_enum'))

    packages = relationship('Package', back_populates='ecosystem')

    @property
    def backend(self):
        return EcosystemBackend[self._backend]

    @backend.setter
    def backend(self, backend):
        self._backend = EcosystemBackend(backend).name

    def is_backed_by(self, backend):
        return self.backend == backend

    @classmethod
    def by_name(cls, session, name):
        return cls._by_attrs(session, name=name)


class Package(Base):
    __tablename__ = 'packages'
    # ecosystem_id together with name must be unique
    __table_args__ = (UniqueConstraint('ecosystem_id', 'name', name='ep_unique'),)

    id = Column(Integer, primary_key=True)
    ecosystem_id = Column(Integer, ForeignKey(Ecosystem.id))
    name = Column(String(255), index=True)

    ecosystem = relationship(Ecosystem, back_populates='packages', lazy='joined')
    versions = relationship('Version', back_populates='package')

    @classmethod
    def by_name(cls, session, name):
        # TODO: this is dangerous at is does not consider Ecosystem
        return cls._by_attrs(session, name=name)


class Version(Base):
    __tablename__ = 'versions'
    # package_id together with version identifier must be unique
    __table_args__ = (UniqueConstraint('package_id', 'identifier', name='pv_unique'),)

    id = Column(Integer, primary_key=True)
    package_id = Column(Integer, ForeignKey(Package.id))
    identifier = Column(String(255), index=True)

    package = relationship(Package, back_populates='versions', lazy='joined')
    analyses = relationship('Analysis', back_populates='version')

    @classmethod
    def by_identifier(cls, session, identifier):
        return cls._by_attrs(session, identifier=identifier)


class Analysis(Base):
    __tablename__ = 'analyses'

    id = Column(Integer, primary_key=True)
    version_id = Column(Integer, ForeignKey(Version.id), index=True)
    access_count = Column(Integer, default=0)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    # debugging and stuff
    subtasks = Column(JSONB)
    release = Column(String(255))  # TODO: is length 255 enough for release?
    audit = Column(JSONB)

    version = relationship(Version, back_populates='analyses', lazy='joined')

    @property
    def analyses(self):
        s = Session.object_session(self)
        if s:
            worker_results = s.query(WorkerResult).filter(WorkerResult.analysis_id == self.id)
            return {wr.worker: wr.task_result for wr in worker_results}
        return {}

    @property
    def raw_analyses(self):
        s = Session.object_session(self)
        if s:
            return s.query(WorkerResult).filter(WorkerResult.analysis_id == self.id)
        return []

    @property
    def latest_version(self):
        # prevent import loop
        from cucoslib.utils import safe_get_latest_version
        return safe_get_latest_version(self.version.package.ecosystem.name,
                                       self.version.package.name)

    @property
    def package_info(self):
        s = Session.object_session(self)
        if s:
            # to avoid cyclic import
            from cucoslib.utils import get_package_dependents_count, get_component_percentile_rank, usage_rank2str

            count = get_package_dependents_count(self.version.package.ecosystem._backend, self.version.package.name, s)
            # TODO: This obviously doesn't belong here. It's getting crowded and unorganized at the top-level,
            # refactoring is needed.
            rank = get_component_percentile_rank(self.version.package.ecosystem._backend,
                                                 self.version.package.name,
                                                 self.version.identifier,
                                                 s)
            return {'dependents_count': count,
                    'relative_usage': usage_rank2str(rank)}
        return {}

    @property
    def dependents_count(self):
        count = -1  # we don't know the count
        s = Session.object_session(self)
        if s:
            # to avoid cyclic import
            from cucoslib.utils import get_dependents_count

            count = get_dependents_count(self.version.package.ecosystem._backend,
                                         self.version.package.name,
                                         self.version.identifier,
                                         s)
        return count

    def to_dict(self, omit_analyses=False):
        res = Base.to_dict(self)
        res['analyses'] = {} if omit_analyses else self.analyses
        res['latest_version'] = self.latest_version
        res.pop('version_id')
        res['version'] = self.version.identifier
        res['package'] = self.version.package.name
        res['ecosystem'] = self.version.package.ecosystem.name
        res['package_info'] = self.package_info
        res['dependents_count'] = self.dependents_count
        return res


class WorkerResult(Base):
    __tablename__ = 'worker_results'

    id = Column(Integer, primary_key=True)
    worker = Column(String(255), index=True)
    worker_id = Column(String(64), unique=True)
    # `external_request_id` provides mapping of particular `worker_result`
    # to externally defined identifier, when `external_request_id` is provided
    # the value of `analysis_id` should be `NULL`
    external_request_id = Column(String(64))
    analysis_id = Column(ForeignKey(Analysis.id), index=True)
    task_result = Column(JSONB)
    error = Column(Boolean, nullable=False, default=False)

    analysis = relationship(Analysis)

    @property
    def ecosystem(self):
        return self.analysis.version.package.ecosystem

    @property
    def package(self):
        return self.analysis.version.package

    @property
    def version(self):
        return self.analysis.version


class Upstream(Base):
    __tablename__ = "monitored_upstreams"

    id = Column(Integer, primary_key=True)
    package_id = Column(Integer, ForeignKey(Package.id), index=True)
    url = Column(String(255), nullable=False)
    updated_at = Column(DateTime, default=None)
    added_at = Column(DateTime, nullable=False)
    deactivated_at = Column(DateTime, nullable=True)
    active = Column(Boolean, nullable=False, default=True)

    package = relationship(Package)

    @property
    def ecosystem(self):
        return self.package.ecosystem


class PackageAnalysis(Base):
    __tablename__ = "package_analyses"

    id = Column(Integer, primary_key=True)
    package_id = Column(Integer, ForeignKey(Package.id), index=True)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)

    package = relationship(Package)

    @property
    def ecosystem(self):
        return self.package.ecosystem

    @property
    def raw_analyses(self):
        s = Session.object_session(self)
        if s:
            return s.query(PackageWorkerResult).filter(PackageWorkerResult.package_analysis_id == self.id)
        return []


class PackageWorkerResult(Base):
    __tablename__ = "package_worker_results"

    id = Column(Integer, primary_key=True)
    package_analysis_id = Column(Integer, ForeignKey(PackageAnalysis.id), index=True)
    # Semantics are same as for WorkerResult
    worker = Column(String(255), index=True)
    worker_id = Column(String(64), unique=True)
    external_request_id = Column(String(64))
    task_result = Column(JSONB)
    error = Column(Boolean, nullable=False, default=False)

    package_analysis = relationship(PackageAnalysis)

    @property
    def ecosystem(self):
        return self.diagnosis.package.ecosystem

    @property
    def package(self):
        return self.diagnosis.package


class StackAnalysisRequest(Base):
    __tablename__ = "stack_analyses_request"
    id = Column(String(64), primary_key=True)
    submitTime = Column(DateTime, nullable=False)
    requestJson = Column(JSON, nullable=False)
    origin = Column(String(64), nullable=True)
    result = Column(JSON, nullable=True)
    team = Column(String(64), nullable=True)


class PackageGHUsage(Base):
    """Table for storing package results from BigQuery."""
    __tablename__ = 'package_gh_usage'

    id = Column(Integer, primary_key=True)
    # dependency name as extracted from package.json found somewhere on GitHub
    name = Column(String(255), nullable=False)
    # number of dependent projects found on GitHub
    count = Column(Integer, nullable=False)
    ecosystem_backend = Column(ENUM(*[b.name for b in EcosystemBackend], name='ecosystem_backend_enum', create_type=False))
    timestamp = Column(DateTime, nullable=False, server_default=func.localtimestamp())


class ComponentGHUsage(Base):
    """Table for storing component results from BigQuery."""
    __tablename__ = 'component_gh_usage'

    id = Column(Integer, primary_key=True)
    # dependency name as extracted from npm-shrinkwrap.json found somewhere on GitHub
    name = Column(String(255), nullable=False)
    # dependency version
    version = Column(String(255), nullable=False)
    # number of references to the (name, version) from shrinkwrap files
    count = Column(Integer, nullable=False)
    # percentage of components that are used less or equally often as (name, version)
    percentile_rank = Column(Integer, nullable=False)
    ecosystem_backend = Column(ENUM(*[b.name for b in EcosystemBackend], name='ecosystem_backend_enum', create_type=False))
    timestamp = Column(DateTime, nullable=False, server_default=func.localtimestamp())


class DownstreamMap(Base):
    __tablename__ = 'downstream_map'

    key = Column(String(255), primary_key=True)
    value = Column(String(512))
