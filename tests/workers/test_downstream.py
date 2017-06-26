# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import pytest
import f8a_worker.workers.downstream
import f8a_worker.utils
from f8a_worker.workers import DownstreamUsageTask
from f8a_worker.enums import EcosystemBackend
from f8a_worker.models import Ecosystem
from requests import Response
import json, os

example_projects = [
    ('pypi', 'six', 'python-six', '1.9.0'),
    ('npm', 'serve-static', 'nodejs-serve-static', '1.10.0'),
    # TODO: Figure out what's wrong with the Java case
    #('maven', 'junit', 'junit', '4.12.0'),
    ('rubygems', 'nokogiri', 'rubygem-nokogiri', '1.5.11'),
]


def _make_ecosystem(name):
    return Ecosystem(name=name, backend=getattr(EcosystemBackend, name))


def _make_brew_command(srpms_to_report):
    stdout_template = """\
    {{
        "packages": {packages},
        "response": {{
            "brew": {brew},
            "registered_srpms": {srpms}
        }}
    }}"""
    raw_srpm_metadata = [srpm.copy() for srpm in srpms_to_report]
    for entry in raw_srpm_metadata:
        entry.pop('filename')
        entry['epoch'] = 0
        count_fields = ('patch_count', 'modified_line_count', 'modified_file_count')
        for field in count_fields:
            entry[field] = -1
    srpm_metadata = json.dumps(raw_srpm_metadata)
    raw_brew_metadata = [{'package': srpm['filename']} for srpm in srpms_to_report]
    for entry in raw_brew_metadata:
        entry['patch_files'] = []
        entry['diff'] = {
            'files': -1,
            'lines': -1,
            'changes': []
        }
    brew_metadata = json.dumps(raw_brew_metadata)

    class MockBrewCommand(object):
        def __init__(self, command):
            self.command = command

        def run(self, timeout=None, **kwargs):
            stdout = stdout_template.format(
                packages=str(self.command[-1:]).replace('\'', '"'),
                brew=brew_metadata,
                srpms=srpm_metadata,
            )
            return 0, stdout, ""
    return MockBrewCommand


def _make_pulp_client(usage_to_report):
    class MockPulpClient(object):
        def get_cdn_metadata_for_srpm(self, srpm_filename):
            metadata = usage_to_report[srpm_filename].copy()
            metadata["srpm_filename"] = srpm_filename
            return metadata
    return MockPulpClient


class TestDownstreamUsage(object):
    @pytest.mark.usefixtures("dispatcher_setup")
    @pytest.mark.timeout(20)
    @pytest.mark.parametrize(('ecosystem', 'project', 'package', 'version'), example_projects)
    def test_execute_no_anitya(self, rdb, ecosystem, project, package, version, monkeypatch):
        rdb.add(_make_ecosystem(ecosystem))
        rdb.commit()
        monkeypatch.setattr(f8a_worker.workers.downstream,
                            "TimedCommand",
                            _make_brew_command([]))
        # ensure we return None for digests
        monkeypatch.setattr(f8a_worker.workers.downstream.DownstreamUsageTask,
                            "parent_task_result",
                            lambda x, y: None)
        task = DownstreamUsageTask.create_test_instance(task_name='redhat_downstream')
        args = {'ecosystem': ecosystem, 'name': project, 'version': version}
        results = task.execute(arguments=args)
        assert results is not None
        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        assert results['status'] == 'error'
        task.validate_result(results)

    @pytest.mark.usefixtures("dispatcher_setup")
    @pytest.mark.timeout(20)
    @pytest.mark.parametrize(('ecosystem', 'project', 'package', 'version'), example_projects)
    def test_execute_mock_services(self, rdb, ecosystem, project, package, version, monkeypatch):
        # Mock the attempted access to Anitya
        expected_suffix = "{}/{}/".format(ecosystem, project)
        # Mock the result
        dummy_packages = [
            {
                'distro': ecosystem,
                'package_name': package
            }
        ]

        def _query_anitya_url(host_url, api_path):
            assert api_path.endswith(expected_suffix)
            result = Response()
            result.status_code = 200
            result.encoding = 'utf-8'
            dummy_data = {
                'api_path': api_path,
                'packages': dummy_packages
            }
            result._content = json.dumps(dummy_data).encode(result.encoding)
            return result
        monkeypatch.setattr(f8a_worker.workers.downstream,
                            "_query_anitya_url",
                            _query_anitya_url)

        # Mock the attempted access to Brew
        dummy_releases = ['1.el6', '1.el7']
        dummy_srpm_names = [
            "{}-{}-{}.src.rpm".format(package, version, dummy_releases[0]),
            "{}-{}-{}.src.rpm".format(package, version, dummy_releases[1]),
        ]
        dummy_srpm_details = [
            {
                'package_name': package,
                'version': version,
                'release': dummy_releases[0],
                'filename': dummy_srpm_names[0],
            },
            {
                'package_name': package,
                'version': version,
                'release':  dummy_releases[1],
                'filename': dummy_srpm_names[1],
            },
        ]
        monkeypatch.setattr(f8a_worker.workers.downstream,
                            "TimedCommand",
                            _make_brew_command(dummy_srpm_details))
        # Mock the attempted access to Pulp (these are not real product names)
        dummy_usage_details = {
            dummy_srpm_names[0]: {
                "rhsm_product_names": ["RHEL 6"],
                "rhn_channels": ["rhn-rhel-6"],
                "rhsm_content_sets": ["rhsm-rhel-6"],
            },
            dummy_srpm_names[1]: {
                "rhsm_product_names": ["RHEL 7"],
                "rhn_channels": ["rhn-rhel-7"],
                "rhsm_content_sets": ["rhsm-rhel-7"],
            },
        }
        monkeypatch.setattr(f8a_worker.workers.downstream,
                            "Pulp",
                            _make_pulp_client(dummy_usage_details))
        # ensure we return None for digests
        monkeypatch.setattr(f8a_worker.workers.downstream.DownstreamUsageTask,
                            "parent_task_result",
                            lambda x, y: None)

        # Check the rest of the task reacts as expected
        rdb.add(_make_ecosystem(ecosystem))
        rdb.commit()
        task = DownstreamUsageTask.create_test_instance(task_name='redhat_downstream')
        args = {'ecosystem': ecosystem, 'name': project, 'version': version}
        results = task.execute(arguments=args)
        assert results is not None
        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        assert results['status'] == 'success'
        task.validate_result(results)
        # We rely on the task's schema self-validation to verify output structure
        # Check the summary metadata
        summary = results['summary']
        assert summary['package_names'] == [package]
        srpm_releases = [srpm['release'] for srpm in summary['registered_srpms']]
        assert set(srpm_releases) == set(dummy_releases)
        assert len(srpm_releases) == 2
        assert summary['all_rhn_channels'] == ['rhn-rhel-6', 'rhn-rhel-7']
        assert summary['all_rhsm_content_sets'] == ['rhsm-rhel-6', 'rhsm-rhel-7']
        assert summary['all_rhsm_product_names'] == ['RHEL 6', 'RHEL 7']
        # Check our dummy data is reported as the response from Anitya
        anitya_response = results['details']['redhat_anitya']
        assert anitya_response['api_path'].endswith(expected_suffix)
        assert anitya_response['packages'] == dummy_packages
        # 'brew' should contain a corresponding entry for each registered SRPM
        brew_responses = results['details']['brew']
        for expected_name, brew_response in zip(dummy_srpm_names, brew_responses):
            assert brew_response['package'] == expected_name
        assert len(brew_responses) == len(dummy_srpm_names)
        # 'pulp_cdn' should also contain an entry for each registered SRPM
        pulp_responses = results['details']['pulp_cdn']
        for expected_name, pulp_response in zip(dummy_srpm_names, pulp_responses):
            assert pulp_response['srpm_filename'] == expected_name
        assert len(pulp_responses) == len(dummy_srpm_names)
