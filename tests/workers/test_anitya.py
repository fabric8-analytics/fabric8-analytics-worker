# -*- coding: utf-8 -*-
import flexmock
import pytest
from requests import Response

from f8a_worker.enums import EcosystemBackend
from f8a_worker.models import Ecosystem, create_db_scoped_session
from f8a_worker.utils import DownstreamMapCache
from f8a_worker.workers import AnityaTask

from ..conftest import rdb

example_projects = [
        ('npm', 'underscore', '563b1d9f13887d4bdcb6b06270a54825', 'rh-dist-git filenam nodejs-underscore'),
]


@pytest.mark.usefixtures("dispatcher_setup")
class TestAnitya(object):
    """
    There's not much to test here since the task returns None and Anitya access has to be mocked
    """
    @pytest.mark.parametrize(('ecosystem', 'project', 'md5sum', 'dist_git'), example_projects)
    def test_execute_with_mock_anitya(self, ecosystem, project, md5sum, dist_git):
        rdb()
        s = create_db_scoped_session()
        dummy_homepage = "http://project-homepage.com"

        dummy_response = Response()
        dummy_response.status_code = 200
        s.add(Ecosystem(name='npm', backend=EcosystemBackend.npm))
        s.commit()
        DownstreamMapCache()[md5sum] = dist_git  # fill in key-value mapping in cache

        task = AnityaTask.create_test_instance(task_name='anitya')
        args = {'ecosystem': ecosystem, 'name': project}
        flexmock(task).should_receive("_get_project_homepage").once().and_return(dummy_homepage)
        flexmock(task).should_receive("_get_artifact_hash").once().and_return(md5sum)
        flexmock(task).should_receive("_create_anitya_project").once().and_return(dummy_response)
        flexmock(task).should_receive("_add_downstream_mapping").once().and_return(dummy_response)

        results = task.execute(arguments=args)
        assert results is None
