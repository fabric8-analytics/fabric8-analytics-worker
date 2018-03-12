"""Import all tasks."""

from f8a_worker.workers.CVEchecker import CVEcheckerTask
from f8a_worker.workers.bigquery_gh import BigQueryTask
from f8a_worker.workers.binwalk import BinwalkTask
from f8a_worker.workers.bookkeeper import BookkeeperTask
from f8a_worker.workers.code_metrics import CodeMetricsTask
from f8a_worker.workers.csmock_worker import CsmockTask
from f8a_worker.workers.cvedbsync import CVEDBSyncTask
from f8a_worker.workers.dependency_parser import GithubDependencyTreeTask
from f8a_worker.workers.dependency_snapshot import DependencySnapshotTask
from f8a_worker.workers.digester import DigesterTask
from f8a_worker.workers.finalize import FinalizeTask, PackageFinalizeTask
from f8a_worker.workers.gh_metadata_init import InitGitHubManifestMetadata
from f8a_worker.workers.gh_metadata_result_collector import GitHubManifestMetadataResultCollector
from f8a_worker.workers.git_stats import GitStats
from f8a_worker.workers.githuber import GithubTask, GitReadmeCollectorTask
from f8a_worker.workers.graph_importer import GraphImporterTask
from f8a_worker.workers.graph_sync import GraphSyncTask
from f8a_worker.workers.graphaggregator import GraphAggregatorTask
from f8a_worker.workers.init_analysis_flow import InitAnalysisFlow
from f8a_worker.workers.init_package_flow import InitPackageFlow
from f8a_worker.workers.keywords_summary import KeywordsSummaryTask
from f8a_worker.workers.keywords_tagging import KeywordsTaggingTask
from f8a_worker.workers.keywords_tagging import PackageKeywordsTaggingTask
from f8a_worker.workers.libraries_io import LibrariesIoTask
from f8a_worker.workers.license import LicenseCheckTask
from f8a_worker.workers.linguist import LinguistTask
from f8a_worker.workers.manifest_keeper import ManifestKeeperTask
from f8a_worker.workers.mercator import MercatorTask
from f8a_worker.workers.oscryptocatcher import OSCryptoCatcherTask
from f8a_worker.workers.recommender import RecommendationTask, RecommendationV2Task
from f8a_worker.workers.report_generation import ReportGenerationTask
from f8a_worker.workers.repository_description import RepositoryDescCollectorTask
from f8a_worker.workers.result_collector import ResultCollector, PackageResultCollector
from f8a_worker.workers.stackaggregator import StackAggregatorTask
from f8a_worker.workers.stackaggregator_v2 import StackAggregatorV2Task
from f8a_worker.workers.unknown_dep_fetcher import UnknownDependencyFetcherTask
