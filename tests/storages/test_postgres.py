import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from f8a_worker.defaults import configuration
from f8a_worker.enums import EcosystemBackend
from f8a_worker.models import (Ecosystem, Package, Version, Analysis, WorkerResult,
                               create_db_scoped_session, PackageAnalysis)
from f8a_worker.storages import BayesianPostgres
from f8a_worker.storages import PackagePostgres
from f8a_worker.storages import StackPostgres


from ..conftest import rdb


class TestBayesianPostgres(object):
    def setup_method(self, method):
        rdb()
        self.s = create_db_scoped_session()
        self.en = 'foo'
        self.pn = 'bar'
        self.vi = '1.1.1'
        self.e = Ecosystem(name=self.en, backend=EcosystemBackend.maven)
        self.p = Package(ecosystem=self.e, name=self.pn)
        self.v = Version(package=self.p, identifier=self.vi)
        self.a = Analysis(version=self.v, finished_at=datetime.datetime.utcnow())
        self.a2 = Analysis(version=self.v,
                           finished_at=datetime.datetime.utcnow() + datetime.timedelta(seconds=10))
        self.s.add(self.a)
        self.s.add(self.a2)
        self.s.commit()

    @classmethod
    def setup_class(cls):
        cls.bp = BayesianPostgres(connection_string=configuration.POSTGRES_CONNECTION)
        cls.bp.connect()

    @pytest.mark.usefixtures("dispatcher_setup")
    def test_store(self):
        task_name = 'foo'
        arguments = {
            'ecosystem': self.en,
            'name': self.pn,
            'version': self.vi
        }
        res = {'real': 'result'}
        worker_id = 'id-1234'

        assert self.bp.store(arguments, 'flow_name', task_name, 'id-1234', res) is not None
        assert self.bp.get_worker_id_count(worker_id) == 1

    @pytest.mark.usefixtures("dispatcher_setup")
    def test_get_latest_task_result(self):
        tn = 'asd'
        tid1 = 'tid-1'
        tid2 = 'tid-2'
        res = {'some': 'thing'}
        arguments = {
            'ecosystem': self.en,
            'name': self.pn,
            'version': self.vi,
            'document_id': self.a.id
        }

        assert self.bp.store(arguments,
                             flow_name='blah',
                             task_name=tn,
                             task_id=tid1,
                             result=res) is not None
        res['later'] = 'aligator'
        assert self.bp.store(arguments,
                             flow_name='blah',
                             task_name=tn,
                             task_id=tid2,
                             result=res) is not None

        retrieved_res = self.bp.get_latest_task_result(arguments['ecosystem'],
                                                       arguments['name'],
                                                       arguments['version'],
                                                       tn)
        assert res == retrieved_res

    @pytest.mark.usefixtures("dispatcher_setup")
    def test_store_already_exists(self):
        tn = 'asd'
        tid = 'sdf'
        res = {'some': 'thing'}
        arguments = {
            'ecosystem': self.en,
            'name': self.pn,
            'version': self.vi,
            'document_id': self.a.id
        }

        self.bp.store(arguments, flow_name='blah', task_name=tn, task_id=tid, result=res)
        with pytest.raises(IntegrityError):
            self.bp.store(arguments, flow_name='blah', task_name=tn, task_id=tid, result=res)


@pytest.mark.usefixtures("dispatcher_setup")
class TestPackagePostgres(object):
    def setup_method(self, method):
        rdb()
        self.s = create_db_scoped_session()
        self.en = 'foo'
        self.pn = 'bar'
        self.e = Ecosystem(name=self.en, backend=EcosystemBackend.maven)
        self.p = Package(ecosystem=self.e, name=self.pn)
        self.a = PackageAnalysis(package=self.p, finished_at=datetime.datetime.now())
        self.a2 = PackageAnalysis(
            package=self.p,
            finished_at=datetime.datetime.now() + datetime.timedelta(seconds=10)
        )
        self.s.add(self.a)
        self.s.add(self.a2)
        self.s.commit()

    @classmethod
    def setup_class(cls):
        cls.pp = PackagePostgres(connection_string=configuration.POSTGRES_CONNECTION)
        cls.pp.connect()

    @pytest.mark.usefixtures("dispatcher_setup")
    def test_get_latest_task_entry(self):
        tn = 'asd'
        tid1 = 'tid_1'
        tid2 = 'tid_2'
        res = {'some': 'thing'}
        arguments = {
            'ecosystem': self.en,
            'name': self.pn,
            'document_id': self.a.id
        }
        self.pp.store(arguments, flow_name='blah', task_name=tn, task_id=tid1, result=res)
        res['later'] = 'aligator'
        self.pp.store(arguments, flow_name='blah', task_name=tn, task_id=tid2, result=res)
        entry = self.pp.get_latest_task_entry(self.en, self.pn, tn)
        assert entry.worker_id == tid2
        assert entry.worker == tn

    @pytest.mark.usefixtures("dispatcher_setup")
    def test_get_latest_task_result_no_results(self):
        assert self.pp.get_latest_task_result(self.en, self.pn, 'asd') is None


class TestStackPostgres(object):
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

    @classmethod
    def setup_class(cls):
        cls.sp = StackPostgres(connection_string=configuration.POSTGRES_CONNECTION)
        cls.sp.connect()

    @pytest.mark.usefixtures("dispatcher_setup")
    def test_retrieve_normal(self):
        wid = 'x'
        w = 'y'
        tr = {'1': '2'}
        wr = WorkerResult(analysis=self.a, worker_id=wid, worker=w, task_result=tr)
        self.s.add(wr)
        self.s.commit()

        assert self.sp.retrieve('whatever', w, wid) == tr

    @pytest.mark.usefixtures("dispatcher_setup")
    def test_store_normal(self):
        tn = 'asd'
        tid = 'sdf'
        res = {'some': 'thing'}
        self.sp.store(node_args={}, flow_name='blah', task_name=tn, task_id=tid, result=res)
        assert self.sp.retrieve('doesntmatter', tn, tid) == res

    @pytest.mark.usefixtures("dispatcher_setup")
    def test_store_already_exists(self):
        tn = 'asd'
        tid = 'sdf'
        res = {'some': 'thing'}
        self.sp.store(node_args={}, flow_name='blah', task_name=tn, task_id=tid, result=res)
        with pytest.raises(IntegrityError):
            self.sp.store(node_args={}, flow_name='blah', task_name=tn, task_id=tid, result=res)
