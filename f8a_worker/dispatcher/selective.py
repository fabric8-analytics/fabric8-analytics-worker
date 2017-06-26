import logging


def selective_run_function(flow_name, node_name, node_args, task_names, storage_pool):
    """ A function that is called on selective run by dispatcher

    This function determines whether we need to run a task or we can reuse already existing results

    :param flow_name: name of the flow in which this function is called
    :param node_args: flow arguments
    :param task_names: a list of tasks that should be run in the selective run
    :param storage_pool: storage pool with parent tasks
    :return: ID of task that should be reused, None if task should be run again
    """
    try:
        task_result = storage_pool.get_connected_storage('BayesianPostgres').get_latest_task_result(
            node_args['ecosystem'],
            node_args['name'],
            node_args['version'],
            node_name,
            error=False
        )
        if task_result:
            return task_result.worker_id
    except:
        logging.error("Failed to get results in selective run function")

    return None
