"""Initialize package-version level analysis for metadata collection."""
from f8a_worker.base import BaseTask
from f8a_utils.golang_utils import GolangUtils
from selinon import StoragePool
from f8a_worker.utils import store_data_to_s3
import logging

logger = logging.getLogger(__name__)


class NewMetaDataTask(BaseTask):
    """Initialize package-version-level analysis for metadata."""

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        result_data = {'status': 'success',
                       'details': []}

        metadata_dict = {
            'description': '',
            'name': arguments.get('name'),
            'version': arguments.get('version'),
            'ecosystem': arguments.get('ecosystem')
        }

        result_data['details'].append(metadata_dict)

        # Store base file required by Data importer
        store_data_to_s3(arguments,
                         StoragePool.get_connected_storage('S3InItData'),
                         result_data)

        # Get the license for package
        golang_util = GolangUtils(arguments.get('name'))
        license = golang_util.get_license()

        if license is not None:
            metadata_dict['declared_licenses'] = license
        else:
            metadata_dict['declared_licenses'] = []

        # Store metadata file for being used in Data-Importer
        store_data_to_s3(arguments,
                         StoragePool.get_connected_storage('S3MetaData'),
                         result_data)

        return arguments
