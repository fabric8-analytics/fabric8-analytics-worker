"""Determine whether we need to run a task or we can reuse already existing results."""

import logging

_logger = logging.getLogger(__name__)


def selective_run_function(flow_name, node_name, node_args, task_names, storage_pool):
    """Determine whether we need to run a task or we can reuse already existing results.

    This function that is called on selective run by dispatcher.

    :param flow_name: name of the flow in which this function is called
    :param node_args: flow arguments
    :param task_names: a list of tasks that should be run in the selective run
    :param storage_pool: storage pool with parent tasks
    :return: ID of task that should be reused, None if task should be run again
    """
    try:
        if flow_name in ('bayesianPackageFlow', 'bayesianPackageAnalysisFlow', 'newPackageFlow'):
            task_result = storage_pool.get_connected_storage('PackagePostgres').\
                get_latest_task_entry(
                    node_args['ecosystem'],
                    node_args['name'],
                    node_name,
                    error=False
            )
        else:
            task_result = storage_pool.get_connected_storage('BayesianPostgres').\
                get_latest_task_entry(
                    node_args['ecosystem'],
                    node_args['name'],
                    node_args['version'],
                    node_name,
                    error=False
            )
        if task_result:
            return task_result.worker_id
    except Exception:
        _logger.exception("Failed to get results in selective run function")

    return None
