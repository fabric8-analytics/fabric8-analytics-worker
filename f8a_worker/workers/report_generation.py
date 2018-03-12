"""Output: TBD."""

from f8a_worker.base import BaseTask


class ReportGenerationTask(BaseTask):

    def execute(self, arguments=None):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self.log.info("Arguments passed from flow: {}".format(arguments))
        return {"result": True}
