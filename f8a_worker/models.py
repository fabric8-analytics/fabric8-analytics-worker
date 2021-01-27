"""SQLAlchemy domain models."""

from sqlalchemy import (Column, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint,
                        create_engine, Boolean, Text)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, scoped_session, sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.session import Session
from sqlalchemy.pool import NullPool

from f8a_worker.defaults import configuration
from f8a_worker.enums import EcosystemBackend


def create_db_scoped_session(connection_string=None):
    """Create scoped session."""
    # we use NullPool, so that SQLAlchemy doesn't pool local connections
    #  and only really uses connections while writing results
    return scoped_session(
        sessionmaker(bind=create_engine(
            connection_string or configuration.POSTGRES_CONNECTION,
            poolclass=NullPool)))


class BayesianModelMixin(object):
    """Subclasses of this class will gain some `by_*` class methods.

    Note, that these should only be used to obtain objects by unique attribute
    (or combination of attributes that make the object unique), since under the
    hood they use SQLAlchemy's `.one()`.

    Also note, that these class methods will raise sqlalchemy.rom.exc.NoResultFound if the object
    is not found.
    """

    def to_dict(self):
        """Convert table to dictionary."""
        d = {}
        for column in self.__table__.columns:
            d[column.name] = getattr(self, column.name)

        return d

    @classmethod
    def _by_attrs(cls, session, **attrs):
        """Get one row with attrs."""
        try:
            return session.query(cls).filter_by(**attrs).one()
        except NoResultFound:
            raise
        except SQLAlchemyError:
            session.rollback()
            raise

    @classmethod
    def by_id(cls, session, id):
        """Get a row with id."""
        try:
            return cls._by_attrs(session, id=id)
        except NoResultFound:
            # What to do here ?
            raise

    @classmethod
    def get_or_create(cls, session, **attrs):
        """Try to get by attrs or create new record if no result found."""
        try:
            return cls._by_attrs(session, **attrs)
        except NoResultFound:
            try:
                o = cls(**attrs)
                try:
                    session.add(o)
                    session.commit()
                except SQLAlchemyError:
                    session.rollback()
                    raise
                return o
            except IntegrityError:  # object was created in the meanwhile by someone else
                return cls._by_attrs(**attrs)


Base = declarative_base(cls=BayesianModelMixin)


class Ecosystem(Base):
    """Table for Ecosystem."""

    __tablename__ = 'ecosystems'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True)
    url = Column(String(255))
    fetch_url = Column(String(255))
    _backend = Column(
        Enum(*[b.name for b in EcosystemBackend], name='ecosystem_backend_enum'))

    packages = relationship('Package', back_populates='ecosystem')
    feedback = relationship('RecommendationFeedback',
                            back_populates='ecosystem')

    @property
    def backend(self):
        """Get backend property."""
        return EcosystemBackend[self._backend]

    @backend.setter
    def backend(self, backend):
        """Set backend property."""
        self._backend = EcosystemBackend(backend).name

    def is_backed_by(self, backend):
        """Is this ecosystem backed by specified backend?."""
        return self.backend == backend

    @classmethod
    def by_name(cls, session, name):
        """Get a row with specified name."""
        try:
            return cls._by_attrs(session, name=name)
        except NoResultFound:
            # What to do here ?
            raise


class Package(Base):
    """Table for Package."""

    __tablename__ = 'packages'
    # ecosystem_id together with name must be unique
    __table_args__ = (UniqueConstraint(
        'ecosystem_id', 'name', name='ep_unique'),)

    id = Column(Integer, primary_key=True)
    ecosystem_id = Column(Integer, ForeignKey(Ecosystem.id))
    name = Column(String(2048), index=True)

    ecosystem = relationship(
        Ecosystem, back_populates='packages', lazy='joined')
    versions = relationship('Version', back_populates='package')

    @classmethod
    def by_name(cls, session, name):
        """Get a row with specified name."""
        # TODO: this is dangerous at is does not consider Ecosystem
        try:
            return cls._by_attrs(session, name=name)
        except NoResultFound:
            # What to do here ?
            raise


class Version(Base):
    """Table for Version."""

    __tablename__ = 'versions'
    # package_id together with version identifier must be unique
    __table_args__ = (UniqueConstraint(
        'package_id', 'identifier', name='pv_unique'),)

    id = Column(Integer, primary_key=True)
    package_id = Column(Integer, ForeignKey(Package.id))
    identifier = Column(String(255), index=True)
    synced2graph = Column(Boolean, nullable=False, default=False, index=True)

    package = relationship(Package, back_populates='versions', lazy='joined')
    analyses = relationship('Analysis', back_populates='version')

    @classmethod
    def by_identifier(cls, session, identifier):
        """Get a row with specified identifier."""
        try:
            return cls._by_attrs(session, identifier=identifier)
        except NoResultFound:
            # What to do here ?
            raise


class Analysis(Base):
    """Table for Analysis."""

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
        """Get all worker results for this analysis."""
        s = Session.object_session(self)
        if s:
            worker_results = s.query(WorkerResult).filter(
                WorkerResult.analysis_id == self.id)
            return {wr.worker: wr.task_result for wr in worker_results}
        return {}

    @property
    def raw_analyses(self):
        """Get all worker results for this analysis."""
        s = Session.object_session(self)
        if s:
            return s.query(WorkerResult).filter(WorkerResult.analysis_id == self.id)
        return []

    @property
    def package_info(self):
        """Get dependents_count and relative_usage.

        This property is DEPRECATED, it will be removed in future.
        """
        return {'dependents_count': -1, 'relative_usage': 'not used'}

    @property
    def dependents_count(self):
        """Get dependents_count.

        This property is DEPRECATED, it will be removed in future.
        """
        return -1

    def to_dict(self, omit_analyses=False):
        """Convert to dictionary."""
        res = Base.to_dict(self)
        res['analyses'] = {} if omit_analyses else self.analyses
        res.pop('version_id')
        res['version'] = self.version.identifier
        res['package'] = self.version.package.name
        res['ecosystem'] = self.version.package.ecosystem.name
        res['package_info'] = self.package_info
        res['dependents_count'] = self.dependents_count
        return res


class WorkerResult(Base):
    """Table for package-version level worker result."""

    __tablename__ = 'worker_results'

    id = Column(Integer, primary_key=True)
    worker = Column(String(255), index=True)
    worker_id = Column(String(64), unique=True)
    started_at = Column(DateTime, index=True)
    ended_at = Column(DateTime, index=True)
    # `external_request_id` provides mapping of particular `worker_result`
    # to externally defined identifier, when `external_request_id` is provided
    # the value of `analysis_id` should be `NULL`
    external_request_id = Column(String(64), index=True)
    analysis_id = Column(ForeignKey(Analysis.id), index=True)
    task_result = Column(JSONB)
    error = Column(Boolean, nullable=False, default=False)

    analysis = relationship(Analysis)

    @property
    def ecosystem(self):
        """Get ecosystem."""
        return self.analysis.version.package.ecosystem

    @property
    def package(self):
        """Get package."""
        return self.analysis.version.package

    @property
    def version(self):
        """Get version."""
        return self.analysis.version


class Upstream(Base):
    """Table for upstream."""

    __tablename__ = "monitored_upstreams"

    id = Column(Integer, primary_key=True)
    package_id = Column(Integer, ForeignKey(Package.id), index=True)
    url = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=None)
    added_at = Column(DateTime, nullable=False)
    deactivated_at = Column(DateTime, nullable=True)

    package = relationship(Package)

    @property
    def ecosystem(self):
        """Get ecosystem."""
        return self.package.ecosystem


class PackageAnalysis(Base):
    """Table for package level analysis."""

    __tablename__ = "package_analyses"

    id = Column(Integer, primary_key=True)
    package_id = Column(Integer, ForeignKey(Package.id), index=True)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)

    package = relationship(Package)

    @property
    def ecosystem(self):
        """Get ecosystem."""
        return self.package.ecosystem

    @property
    def raw_analyses(self):
        """Get all worker results for this analysis."""
        s = Session.object_session(self)
        if s:
            return s.query(PackageWorkerResult).filter(
                PackageWorkerResult.package_analysis_id == self.id)
        return []


class PackageWorkerResult(Base):
    """Table for package level worker result."""

    __tablename__ = "package_worker_results"

    id = Column(Integer, primary_key=True)
    package_analysis_id = Column(
        Integer, ForeignKey(PackageAnalysis.id), index=True)
    # Semantics are same as for WorkerResult
    worker = Column(String(255), index=True)
    worker_id = Column(String(64), unique=True)
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    external_request_id = Column(String(64))
    task_result = Column(JSONB)
    error = Column(Boolean, nullable=False, default=False)

    package_analysis = relationship(PackageAnalysis)

    @property
    def ecosystem(self):
        """Get ecosystem."""
        return self.diagnosis.package.ecosystem

    @property
    def package(self):
        """Get package."""
        return self.diagnosis.package


class StackAnalysisRequest(Base):
    """Table for stack analysis request."""

    __tablename__ = "stack_analyses_request"
    id = Column(String(64), primary_key=True)
    submitTime = Column(DateTime, nullable=False)
    requestJson = Column(JSON, nullable=False)
    origin = Column(String(64), nullable=True)
    result = Column(JSON, nullable=True)
    team = Column(String(64), nullable=True)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    dep_snapshot = Column(JSONB, nullable=True)
    feedback = relationship('RecommendationFeedback',
                            back_populates="stack_request")


class APIRequests(Base):
    """Table for API request."""

    __tablename__ = "api_requests"
    id = Column(String(64), primary_key=True)
    api_name = Column(String(256), nullable=False)
    submit_time = Column(DateTime, nullable=False)
    user_email = Column(String(256), nullable=True, index=True)
    user_profile_digest = Column(String(128), nullable=True)
    origin = Column(String(64), nullable=True)
    team = Column(String(64), nullable=True)
    recommendation = Column(JSON, nullable=True)
    request_digest = Column(String(128), nullable=True)
    user_id = Column(UUID(as_uuid=True), nullable=True)


class RecommendationFeedback(Base):
    """Table for recommendation feedback."""

    __tablename__ = "recommendation_feedback"

    id = Column(Integer, autoincrement=True, primary_key=True)
    package_name = Column(String(255), nullable=False)
    recommendation_type = Column(String(255), nullable=False)
    feedback_type = Column(Boolean, nullable=False, default=False)
    ecosystem_id = Column(Integer, ForeignKey(Ecosystem.id))
    ecosystem = relationship("Ecosystem", back_populates="feedback")
    stack_id = Column(String(64), ForeignKey(StackAnalysisRequest.id))
    stack_request = relationship("StackAnalysisRequest",
                                 back_populates="feedback")


class UserDetails(Base):
    """Table for user details."""

    __tablename__ = "user_details"

    user_id = Column(String(64), primary_key=True)
    snyk_api_token = Column(String(255))
    last_validated_date = Column(DateTime)
    status = Column(String(32))
    registered_date = Column(DateTime)
    created_date = Column(DateTime)
    updated_date = Column(DateTime)
    user_source = Column(String(32))


class OSIORegisteredRepos(Base):
    """Table for OSIO registered repos."""

    __tablename__ = "osio_registered_repos"

    git_url = Column(Text, nullable=False, primary_key=True)
    git_sha = Column(String(255), nullable=False)
    email_ids = Column(String(255), nullable=False)
    last_scanned_at = Column(DateTime)
