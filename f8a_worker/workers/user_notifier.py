"""Output: TBD."""

from f8a_worker.base import BaseTask
from time import strftime, gmtime
from uuid import uuid4
import os
import requests


class UserNotificationTask(BaseTask):
    """Generates report containing descriptive data for dependencies."""

    def send_notification(self, notification, token):
        """Send notification to the OSIO notification service."""
        url = 'f8notification'
        # stop gap measure to identify the correct notification service
        # this will be replaced when we get a ConfigMap to identify the
        # appropriate notification service.
        auth_host = os.getenv('F8A_AUTH_SERVICE_HOST', '')
        if auth_host.strip() == 'https://auth.openshift.io':
            url = 'https://f8notification.dsaas-production.svc'
        elif auth_host.strip() == 'https://auth.prod-preview.openshift.io':
            url = 'https://f8notification.dsaas-preview.svc'
        else:
            url = 'http://f8notification-auth-analytics.dev.rdu2c.fabric8.io'

        endpoint = '{url}/api/notify'.format(url=url)
        auth = 'Bearer {token}'.format(token=token)
        resp = requests.post(endpoint, json=notification, headers={'Authorization': auth})
        if resp.status_code == 202:
            self.log.info('Notification service called successfully.')
            return {'status': 'success'}
        else:
            self.log.error('Unexpected response received {code}'.format(code=resp.status_code))
        return {'status': 'failure'}

    def generate_notification(self, report, scanned_at):
        """Generate notification structure from the cve report."""
        result = {
            "data": {
                "attributes": {
                    "custom": report,
                    "id": report.get('repo_url', ""),
                    "type": "analytics.notify.cve"
                },
                "id": str(uuid4()),
                "type": "notifications"
            }
        }
        result["data"]["attributes"]["custom"]["scanned_at"] = scanned_at
        vulnerable_deps = result["data"]["attributes"]["custom"]["vulnerable_deps"]
        total_cve_count = 0

        for deps in vulnerable_deps:
            total_cve_count += int(deps['cve_count'])
        result["data"]["attributes"]["custom"]["cve_count"] = total_cve_count
        self.log.info('Notification to be sent to the users: %r' % result)

        return result

    def execute(self, arguments=None):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self.log.debug("Arguments passed from flow: {}".format(arguments))

        # self._strict_assert(arguments.get('report'))
        self._strict_assert(arguments.get('service_token'))

        report = arguments.get('report')
        service_token = arguments.get('service_token')
        scanned_at = strftime("%a, %d %B %Y %T GMT", gmtime())

        result_list = []
        # send notification for each reported repositories
        for r in report:
            notification = self.generate_notification(r, scanned_at)
            result = self.send_notification(notification, service_token)
            result_list.append(result)

        return {'results': result_list}
