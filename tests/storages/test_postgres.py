import datetime

import flexmock
import pytest
import selinon
from sqlalchemy.exc import IntegrityError

from f8a_worker.defaults import configuration
from f8a_worker.enums import EcosystemBackend
from f8a_worker.models import (Ecosystem, Package, Version, Analysis, WorkerResult,
                               create_db_scoped_session)
from f8a_worker.storages.postgres import BayesianPostgres

from ..conftest import rdb


class TestBayesianPostgres:
    def setup_method(self, method):
        rdb()
        self.s = create_db_scoped_session()
        self.en = 'foo'
        self.pn = 'bar'
        self.vi = '1.1.1'
        self.e = Ecosystem(name=self.en, backend=EcosystemBackend.maven)
        self.p = Package(ecosystem=self.e, name=self.pn)
        self.v = Version(package=self.p, identifier=self.vi)
        self.a = Analysis(version=self.v, finished_at=datetime.datetime.now())
        self.a2 = Analysis(version=self.v,
                           finished_at=datetime.datetime.now() + datetime.timedelta(seconds=10))
        self.s.add(self.a)
        self.s.add(self.a2)
        self.s.commit()

        self.bp = BayesianPostgres(connection_string=configuration.POSTGRES_CONNECTION)

    def test_retrieve_normal(self):
        wid = 'x'
        w = 'y'
        tr = {'1': '2'}
        wr = WorkerResult(analysis=self.a, worker_id=wid, worker=w, task_result=tr)
        self.s.add(wr)
        self.s.commit()

        assert self.bp.retrieve('whatever', w, wid) == tr

    def test_retrieve_s3(self):
        wid = 'x'
        w = 'y'
        tr = {'version_id': 123}
        res = {'real': 'result'}
        wr = WorkerResult(analysis=self.a, worker_id=wid, worker=w, task_result=tr)
        self.s.add(wr)
        self.s.commit()

        s3_storage = flexmock()
        s3_storage.\
            should_receive('retrieve_task_result').\
            with_args(self.en, self.pn, self.vi, w).\
            and_return(res)

        flexmock(selinon.StoragePool).\
            should_receive('get_connected_storage').\
            with_args('S3Data').\
            and_return(s3_storage)

        assert self.bp.retrieve('blahblah', w, wid) == res

    def test_store_normal(self):
        tn = 'asd'
        tid = 'sdf'
        res = {'some': 'thing'}
        self.bp.store(node_args={}, flow_name='blah', task_name=tn, task_id=tid, result=res)
        assert self.bp.retrieve('doesntmatter', tn, tid) == res

    def test_store_already_exists(self):
        tn = 'asd'
        tid = 'sdf'
        res = {'some': 'thing'}
        self.bp.store(node_args={}, flow_name='blah', task_name=tn, task_id=tid, result=res)
        with pytest.raises(IntegrityError):
            self.bp.store(node_args={}, flow_name='blah', task_name=tn, task_id=tid, result=res)

    def test_get_latest_task_result(self):
        tn = 'asd'
        tid = 'sdf'
        res = {'some': 'thing'}
        self.bp.store(node_args={'document_id': self.a.id},
                      flow_name='blah', task_name=tn, task_id=tid, result=res)
        res['later'] = 'aligator'
        self.bp.store(node_args={'document_id': self.a2.id},
                      flow_name='blah', task_name=tn, task_id=tid + '2', result=res)
        assert self.bp.get_latest_task_result(self.en, self.pn, self.vi, tn) == res

    # TODO: This needs to be run against PackagePostgres, not BayesianPostgres
    # def test_get_latest_task_entry(self):
    #     tn = 'asd'
    #     tid = 'sdf'
    #     res = {'some': 'thing'}
    #     self.bp.store(node_args={'document_id': self.a.id},
    #                   flow_name='blah', task_name=tn, task_id=tid, result=res)
    #     res['later'] = 'aligator'
    #     self.bp.store(node_args={'document_id': self.a2.id},
    #                   flow_name='blah', task_name=tn, task_id=tid + '2', result=res)
    #     assert self.bp.get_latest_task_entry(self.en, self.pn, tn).task_result == res
    #     assert self.bp.get_latest_task_entry(self.en, self.pn, tn).worker_id == tid
    #     assert self.bp.get_latest_task_entry(self.en, self.pn, tn).worker == tn

    def test_get_latest_task_result_no_results(self):
        assert self.bp.get_latest_task_result(self.en, self.pn, self.vi, 'asd') is None
