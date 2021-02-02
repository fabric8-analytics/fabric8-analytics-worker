"""Bookkeeper Task."""

import json
from selinon import StoragePool
from f8a_worker.base import BaseTask
from f8a_worker.graphutils import GREMLIN_SERVER_URL_REST
from f8a_worker.utils import get_session_retry


class BookkeeperTask(BaseTask):
    """Keep bookkeeping data on RDS."""

    # we don't want to add `_audit` etc into the manifest submitted
    add_audit_info = False

    def store_user_node(self, arguments, aggregated):
        """Store GraphAggregatorTask's result to graph."""
        for result in aggregated['result']:
            resolved = result['details'][0]['_resolved']
            ecosystem = result['details'][0]['ecosystem']
            email = arguments.get('data').get('user_profile').get('email')
            company = arguments.get('data').get('user_profile').get('company', 'Not Provided')

            # Create User Node if it does not exist
            qstring = "user = g.V().has('userid','" + email + \
                      "').tryNext().orElseGet{graph.addVertex(" \
                      "'vertex_label','User','userid','" + email + "', 'company','" + company + \
                      "')}; g.V(user).as('u')"

            for epvs in resolved:
                if epvs['package'] is None or epvs['version'] is None:
                    self.log.warning("Either component name or component version is missing.")
                    continue

                # Create Version Node if it does not exist
                qstring += ".coalesce(g.V().has('pecosystem','" + ecosystem + "')." + \
                           "has('pname','" + epvs['package'] + "')." + \
                           "has('version','" + epvs['version'] + \
                           "'), addV().property('vertex_label','Version', " + \
                           "'pecosystem','" + ecosystem + "','pname', '" + epvs['package'] + \
                           "', " \
                           "'version', '" + epvs['version'] + "')).as('ver_" + epvs['package'] + \
                           "')"
                # Check if "user -> uses -> version" edge exists else create one
                qstring += ".coalesce(inE('uses').where(outV().as('u')), " \
                           "addE('uses').from('u').to('ver_" + epvs['package'] + "')" \
                           ".coalesce(inV().has('osio_usage_count').sack(assign)." \
                           "by('osio_usage_count')." \
                           "sack(sum).by(constant(1))." \
                           "property('osio_usage_count', sack()), inV()." \
                           "property('osio_usage_count', 1)))"

            payload = {'gremlin': qstring}
            try:
                graph_req = get_session_retry().post(GREMLIN_SERVER_URL_REST,
                                                     data=json.dumps(payload))
                if graph_req.status_code != 200:
                    self.log.error("Failed creating book-keeping record in graph")
                    continue
            except Exception:
                self.log.exception("Failed to communicate to Graph Server.")
                continue

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self._strict_assert(arguments.get('external_request_id'))
        self._strict_assert(arguments.get('data'))

        aggregated = ''
        if arguments.get('api_name') == 'stack_analyses' and \
           'email' in arguments['data'].get('user_profile', {}):
            aggregated = self.parent_task_result('GraphAggregatorTask')
            self.store_user_node(arguments, aggregated)

        postgres = StoragePool.get_connected_storage('BayesianPostgres')
        if arguments.get('api_name') == 'component_analyses_post':
            postgres.store_api_requests_post(arguments)
        else:
            postgres.store_api_requests(arguments.get('external_request_id'),
                                        arguments.get('data'), aggregated)
