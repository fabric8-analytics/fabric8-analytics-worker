# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import flexmock
import pytest

import json
import requests

from cucoslib.pulp import Pulp


def _pulp_client():
    return Pulp(pulp_url="http://dummy.invalid", pulp_auth=(None, None))


@pytest.mark.offline
class TestPulp(object):

    def test_get_repositories(self):
        dummy_filename = "nodejs-express-4.13.3-4.el7.src.rpm"
        dummy_repos = ["rhel-7-server-ose-3_DOT_2-rpms__x86_64",
                       "rhel-7-server-ose-3_DOT_1-rpms__x86_64"]
        dummy_data = [
            {
                "repository_memberships": dummy_repos,
                "_href": "/pulp/api/v2/content/units/rpm/998bb87c-17f6-4d65-a165-232db3e32bf7/",
                "sourcerpm": dummy_filename,
                "_id": "998bb87c-17f6-4d65-a165-232db3e32bf7",
                "children": {}
            }
        ]
        mock_response = requests.Response()
        mock_response.status_code = requests.codes.ok
        mock_response.encoding = 'utf-8'
        mock_response._content = json.dumps(dummy_data).encode(mock_response.encoding)
        pulp = _pulp_client()
        flexmock(pulp).should_receive("post_pulp_api")\
                      .once()\
                      .and_return(mock_response)
        assert set(pulp.get_repositories_for_srpm(dummy_filename)) == set(dummy_repos)

    def _make_dummy_pulp_client(self):
        dummy_repo_id = "rhel-6-workstation-source-rpms__6Workstation__x86_64"
        dummy_api_path = "/pulp/api/v2/repositories/" + dummy_repo_id + "/"
        dummy_product_id = "71"
        dummy_content_set = "rhel-6-workstation-source-rpms"
        dummy_rhn_channels = ["rhel-x86_64-workstation-6",
                              "rhel-x86_64-workstation-6-debuginfo"]
        dummy_data = {
            "display_name": dummy_repo_id,
            "notes": {
                "platform_version": "6",
                "eng_product": dummy_product_id,
                "relative_url": "content/dist/rhel/workstation/6/6Workstation/x86_64/source/SRPMS",
                "content_set": dummy_content_set,
                "rhn_channels": ",".join(dummy_rhn_channels),
            },
            "id": dummy_repo_id
        }
        mock_response = requests.Response()
        mock_response.status_code = requests.codes.ok
        mock_response.encoding = 'utf-8'
        mock_response._content = json.dumps(dummy_data).encode(mock_response.encoding)
        pulp = _pulp_client()
        dummy_data = (dummy_repo_id, dummy_api_path, dummy_product_id,
                      dummy_content_set, dummy_rhn_channels)
        return pulp, dummy_data, mock_response

    def test_get_cdn_metadata_for_repo(self):
        # This just tests the response unpacking, the metadata health checks
        # provide the full end-to-end integration testing against the CDN
        pulp, dummy_data, mock_response = self._make_dummy_pulp_client()
        repo_id, api_path, product_id, content_set, rhn_channels = dummy_data
        flexmock(pulp).should_receive("query_pulp_api")\
                      .with_args(api_path)\
                      .and_return(mock_response)
        fields = ("eng_product", "content_set", "rhn_channels")
        metadata = pulp.get_cdn_fields_for_repo(repo_id, fields)
        assert metadata["eng_product"] == [product_id]
        assert metadata["content_set"] == [content_set]
        assert metadata["rhn_channels"] == rhn_channels

    def test_get_cdn_metadata_for_srpm(self):
        # This just tests the response unpacking, the metadata health checks
        # provide the full end-to-end integration testing against the CDN
        pulp, dummy_data, mock_response = self._make_dummy_pulp_client()
        repo_id, api_path, product_id, content_set, rhn_channels = dummy_data
        flexmock(pulp).should_receive("query_pulp_api")\
                      .with_args(api_path)\
                      .twice()\
                      .and_return(mock_response)
        srpm_filename = "example.src.rpm"
        flexmock(pulp).should_receive("get_repositories_for_srpm")\
                      .with_args(srpm_filename)\
                      .and_return([repo_id, repo_id])
        product_name = "Example Product"
        flexmock(pulp).should_receive("_get_product_name")\
                      .with_args(product_id)\
                      .and_return(product_name)
        metadata = pulp.get_cdn_metadata_for_srpm(srpm_filename)
        assert metadata == {
            "srpm_filename": srpm_filename,
            "rhsm_product_names": [product_name],
            "rhsm_content_sets": [content_set],
            "rhn_channels": rhn_channels,
        }
