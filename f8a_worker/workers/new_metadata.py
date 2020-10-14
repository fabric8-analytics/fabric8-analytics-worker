"""Initialize package-version level analysis."""

import re
from f8a_worker.base import BaseTask

pattern = r'[\*Xx\-\>\=\<\~\^\|\/\:\+]'
pattern_ignore = re.compile(pattern)
import logging

logger = logging.getLogger(__name__)

import sys
def fun_name():
    file_details = "File::"+sys._getframe(1).f_code.co_filename+"_:_Function::_"+sys._getframe(1).f_code.co_name
    return file_details

def print_log(cls_name, arg1, arg2=""):
    msg = "Message from logger"+"__:__"+str(cls_name)+"__:__"+str(arg1)+"__:__"+str(arg2)
    logger.info(msg)
    print(cls_name, str(arg1), str(arg2) ,sep="__:__")


class NewMetadataTask(BaseTask):
    """Download source and start whole analysis."""

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self.log.debug("Input Arguments: {}".format(arguments))

        arguments['test2'] = 'new metadata.'
        print_log(fun_name(), "test2", arguments)

        return arguments
