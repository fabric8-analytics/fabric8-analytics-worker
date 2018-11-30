"""Import all tasks."""

from f8a_worker.workers.bookkeeper import BookkeeperTask
from f8a_worker.workers.dependency_parser import GithubDependencyTreeTask
from f8a_worker.workers.dependency_snapshot import DependencySnapshotTask
from f8a_worker.workers.digester import DigesterTask
from f8a_worker.workers.finalize import FinalizeTask, PackageFinalizeTask
from f8a_worker.workers.githuber import GithubTask, GitReadmeCollectorTask
from f8a_worker.workers.graph_importer import GraphImporterTask
from f8a_worker.workers.graph_sync import GraphSyncTask
from f8a_worker.workers.graphaggregator import GraphAggregatorTask
from f8a_worker.workers.init_analysis_flow import InitAnalysisFlow
from f8a_worker.workers.init_package_flow import InitPackageFlow
from f8a_worker.workers.libraries_io import LibrariesIoTask
from f8a_worker.workers.license import LicenseCheckTask
from f8a_worker.workers.mercator import MercatorTask
from f8a_worker.workers.report_generation import ReportGenerationTask
from f8a_worker.workers.repository_description import RepositoryDescCollectorTask
from f8a_worker.workers.result_collector import ResultCollector, PackageResultCollector
from f8a_worker.workers.unknown_dep_fetcher import UnknownDependencyFetcherTask
from f8a_worker.workers.user_notifier import UserNotificationTask
from f8a_worker.workers.repo_dependency_finder import RepoDependencyFinderTask
from f8a_worker.workers.git_operations import GitOperationTask

# avoid Vulture and Pyflakes warnings
assert BookkeeperTask is not None
assert GithubDependencyTreeTask is not None
assert DependencySnapshotTask is not None
assert DigesterTask is not None
assert FinalizeTask, PackageFinalizeTask is not None
assert GithubTask, GitReadmeCollectorTask is not None
assert GraphImporterTask is not None
assert GraphSyncTask is not None
assert GraphAggregatorTask is not None
assert InitAnalysisFlow is not None
assert InitPackageFlow is not None
assert LibrariesIoTask is not None
assert LicenseCheckTask is not None
assert MercatorTask is not None
assert ReportGenerationTask is not None
assert RepositoryDescCollectorTask is not None
assert ResultCollector, PackageResultCollector is not None
assert UnknownDependencyFetcherTask is not None
assert UserNotificationTask is not None
assert RepoDependencyFinderTask is not None
assert GitOperationTask is not None
