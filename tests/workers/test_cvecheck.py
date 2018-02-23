from datadiff.tools import assert_equal
from flexmock import flexmock
import os
import pytest
from shutil import copy
from f8a_worker.object_cache import EPVCache
from f8a_worker.utils import tempdir
from f8a_worker.workers import CVEcheckerTask

from . import instantiate_task


@pytest.mark.usefixtures("dispatcher_setup")
class TestCVEchecker(object):
    @pytest.mark.parametrize(('cve_id', 'score', 'vector', 'severity'), [
        ('CVE-2017-0249', 7.3, 'CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:L', 'high'),
        ('cve-2015-1164', 4.3, 'AV:N/AC:M/Au:N/C:N/I:P/A:N', 'medium')
    ])
    def test_get_cve_impact(self, cve_id, score, vector, severity):
        score_, vector_, severity_ = CVEcheckerTask.get_cve_impact(cve_id)
        assert score_ == score
        assert vector_ == vector
        assert severity_ == severity

    @pytest.mark.usefixtures('npm')
    def test_npm_geddy(self):
        args = {'ecosystem': 'npm', 'name': 'geddy', 'version': '13.0.7'}
        task = instantiate_task(cls=CVEcheckerTask, task_name='security_issues')
        results = task.execute(args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        assert results['status'] == 'success'
        assert results['summary'] == ['CVE-2015-5688']
        # http://www.cvedetails.com/version/186008/Geddyjs-Geddy-13.0.7.html
        expected_details = [{
            "cvss": {
                "score": 5.0,
                "vector": "AV:N/AC:L/Au:N/C:P/I:N/A:N"
            },
            "description": "Directory traversal vulnerability in lib/app/index.js in Geddy "
                           "before 13.0.8 for Node.js allows remote attackers "
                           "to read arbitrary files via a ..%2f (dot dot encoded slash) "
                           "in the PATH_INFO to the default URI.",
            "id": "CVE-2015-5688",
            "references": [
                "http://cve.mitre.org/cgi-bin/cvename.cgi?name=2015-5688",
                "http://www.cvedetails.com/cve-details.php?t=1&cve_id=CVE-2015-5688",
                "https://github.com/geddy/geddy/commit/2de63b68b3aa6c08848f261ace550a37959ef231",
                "https://github.com/geddy/geddy/issues/697",
                "https://github.com/geddy/geddy/pull/699",
                "https://github.com/geddy/geddy/releases/tag/v13.0.8",
                "https://nodesecurity.io/advisories/geddy-directory-traversal",
                "https://web.nvd.nist.gov/view/vuln/detail?vulnId=2015-5688"
            ],
            "severity": "medium"}]
        assert_equal(results.get('details'), expected_details)

    def test_maven_commons_collections(self):
        jar_path = os.path.join(
                    os.path.dirname(
                     os.path.abspath(__file__)), '..', 'data', 'maven',
                                                 'commons-collections-3.2.1.jar')
        args = {'ecosystem': 'maven', 'name': 'commons-collections:commons-collections',
                'version': '3.2.1'}
        flexmock(EPVCache).should_receive('get_source_tarball').and_return(jar_path)
        task = instantiate_task(cls=CVEcheckerTask, task_name='security_issues')
        results = task.execute(arguments=args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        expected_details = [{
            "cvss": {
                "score": 7.5,
                "vector": "AV:N/AC:L/Au:?/C:P/I:P/A:P"
            },
            "description": "Serialized-object interfaces in certain Cisco Collaboration and "
                           "Social Media; Endpoint Clients and Client Software; Network "
                           "Application, Service, and Acceleration; Network and Content Security "
                           "Devices; Network Management and Provisioning; Routing and Switching - "
                           "Enterprise and Service Provider; Unified Computing; Voice and Unified "
                           "Communications Devices; Video, Streaming, TelePresence, and "
                           "Transcoding Devices; Wireless; and Cisco Hosted Services products "
                           "allow remote attackers to execute arbitrary commands via a crafted "
                           "serialized Java object, related to the "
                           "Apache Commons Collections (ACC) library.",
            "id": "CVE-2015-6420",
            "references": [
                "http://www.securityfocus.com/bid/78872",
                "https://www.tenable.com/security/research/tra-2017-23",
                "https://www.tenable.com/security/research/tra-2017-14",
                "https://h20566.www2.hpe.com/portal/site/hpsc/public/kb/"
                "docDisplay?docId=emr_na-c05376917",
                "https://h20566.www2.hpe.com/portal/site/hpsc/public/kb/"
                "docDisplay?docId=emr_na-c05390722",
                "http://tools.cisco.com/security/center/content/CiscoSecurityAdvisory/"
                "cisco-sa-20151209-java-deserialization"
            ],
            "severity": "High"}, {
            "cvss": {
                "score": 7.5,
                "vector": "CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
            },
            "description": "It was found that the Apache commons-collections library permitted "
                           "code execution when deserializing objects involving a specially "
                           "constructed chain of classes. A remote attacker could use this flaw to "
                           "execute arbitrary code with the permissions of the application using "
                           "the commons-collections library.\n",
            "id": "CVE-2015-7501",
            "references": [
                "http://foxglovesecurity.com/2015/11/06/what-do-weblogic-websphere-jboss-jenkins-"
                "opennms-and-your-application-have-in-common-this-vulnerability/"],
            "severity": "critical",
            'attribution': 'https://github.com/victims/victims-cve-db, CC BY-SA 4.0, modified'
        }
        ]
        assert_equal(results.get('details'), expected_details)

    def test_python_mako(self):
        extracted = os.path.join(
                        os.path.dirname(
                         os.path.abspath(__file__)), '..', 'data', 'pypi', 'Mako-0.3.3')
        args = {'ecosystem': 'pypi', 'name': 'mako', 'version': '0.3.3'}
        flexmock(EPVCache).should_receive('get_extracted_source_tarball').and_return(extracted)
        task = instantiate_task(cls=CVEcheckerTask, task_name='security_issues')
        results = task.execute(arguments=args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        assert results['status'] == 'success'
        assert results['summary'] == ['CVE-2010-2480']
        # http://www.cvedetails.com/version/94328/Makotemplates-Mako-0.3.3.html
        expected_details = [{
            "cvss": {
                "score": 4.3,
                "vector": "AV:N/AC:M/Au:?/C:?/I:P/A:?"
            },
            "description": "Mako before 0.3.4 relies on the cgi.escape function in the Python "
                           "standard library for cross-site scripting (XSS) protection, "
                           "which makes it easier for remote attackers to conduct XSS attacks via "
                           "vectors involving single-quote characters and a JavaScript onLoad "
                           "event handler for a BODY element.",
            "id": "CVE-2010-2480",
            "references": [
                "http://www.makotemplates.org/CHANGES",
                "http://bugs.python.org/issue9061",
                "http://lists.opensuse.org/opensuse-security-announce/2010-08/msg00001.html"
            ],
            "severity": "Medium"}]
        assert_equal(results.get('details'), expected_details)

    def test_python_requests(self):
        """To make sure that python CPE suppression works (issue#131)."""
        extracted = os.path.join(
                        os.path.dirname(
                         os.path.abspath(__file__)), '..', 'data', 'pypi', 'requests-2.5.3')
        args = {'ecosystem': 'pypi', 'name': 'requests', 'version': '2.5.3'}
        flexmock(EPVCache).should_receive('get_extracted_source_tarball').and_return(extracted)
        task = instantiate_task(cls=CVEcheckerTask, task_name='security_issues')
        results = task.execute(arguments=args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        assert results['status'] == 'success'
        assert results['summary'] == ['CVE-2015-2296']
        # http://www.cvedetails.com/version/180634/Python-requests-Requests-2.5.3.html
        expected_details = [{
            "cvss": {
                "score": 6.8,
                "vector": "AV:N/AC:M/Au:?/C:P/I:P/A:P"
            },
            "description": "The resolve_redirects function in sessions.py in requests 2.1.0 "
                           "through 2.5.3 allows remote attackers to conduct session fixation "
                           "attacks via a cookie without a host value in a redirect.",
            "id": "CVE-2015-2296",
            "references": [
                "https://warehouse.python.org/project/requests/2.6.0/",
                "https://github.com/kennethreitz/requests/commit/"
                "3bd8afbff29e50b38f889b2f688785a669b9aafc",
                "http://www.openwall.com/lists/oss-security/2015/03/14/4",
                "http://www.openwall.com/lists/oss-security/2015/03/15/1",
                "http://www.ubuntu.com/usn/USN-2531-1",
                "http://advisories.mageia.org/MGASA-2015-0120.html"
            ],
            "severity": "Medium"}]
        assert_equal(results.get('details'), expected_details)

    def test_python_salt(self):
        """To make sure we can scan source with standalone PKG-INFO.

        https://github.com/jeremylong/DependencyCheck/issues/896
        """
        pkg_info = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'data', 'pypi', 'salt-2016.11.6', 'PKG-INFO')
        args = {'ecosystem': 'pypi', 'name': 'salt', 'version': '2016.11.6'}
        with tempdir() as extracted:
            # We need a write-access into extracted/
            copy(pkg_info, extracted)
            flexmock(EPVCache).should_receive('get_extracted_source_tarball').and_return(extracted)
            task = instantiate_task(cls=CVEcheckerTask, task_name='security_issues')
            results = task.execute(arguments=args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        assert results['status'] == 'success'
        assert results['summary'] == ['CVE-2017-12791', 'CVE-2017-14695', 'CVE-2017-14696']
        # http://www.cvedetails.com/version/222059/Saltstack-Salt-2016.11.6.html
        expected_details = [
            {
                "cvss": {
                    "score": 7.5,
                    "vector": "AV:N/AC:L/Au:?/C:P/I:P/A:P"
                },
                "description": "Directory traversal vulnerability in minion id validation in "
                               "SaltStack Salt before 2016.11.7 and 2017.7.x before 2017.7.1 "
                               "allows remote minions with incorrect credentials to authenticate "
                               "to a master via a crafted minion ID.",
                "id": "CVE-2017-12791",
                "references": [
                    "http://www.securityfocus.com/bid/100384",
                    "https://bugzilla.redhat.com/show_bug.cgi?id=1482006",
                    "https://github.com/saltstack/salt/pull/42944",
                    "https://docs.saltstack.com/en/2016.11/topics/releases/2016.11.7.html",
                    "https://docs.saltstack.com/en/latest/topics/releases/2017.7.1.html",
                    "https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=872399"
                ],
                "severity": "High"
            },
            {
                "cvss": {
                    "score": 7.5,
                    "vector": "AV:N/AC:L/Au:?/C:P/I:P/A:P"
                },
                "description": "Directory traversal vulnerability in minion id validation "
                               "in SaltStack Salt before 2016.3.8, 2016.11.x before 2016.11.8, "
                               "and 2017.7.x before 2017.7.2 allows remote minions with incorrect "
                               "credentials to authenticate to a master via a crafted minion ID.  "
                               "NOTE: this vulnerability exists because of an incomplete fix "
                               "for CVE-2017-12791.",
                "id": "CVE-2017-14695",
                "references": [
                    "https://docs.saltstack.com/en/latest/topics/releases/2016.11.8.html",
                    "https://docs.saltstack.com/en/latest/topics/releases/2016.3.8.html",
                    "http://lists.opensuse.org/opensuse-updates/2017-10/msg00073.html",
                    "https://bugzilla.redhat.com/show_bug.cgi?id=1500748",
                    "https://github.com/saltstack/salt/commit/"
                    "80d90307b07b3703428ecbb7c8bb468e28a9ae6d",
                    "http://lists.opensuse.org/opensuse-updates/2017-10/msg00075.html",
                    "https://docs.saltstack.com/en/latest/topics/releases/2017.7.2.html"
                ],
                "severity": "High"
            },
            {
                "cvss": {
                    "score": 5.0,
                    "vector": "AV:N/AC:L/Au:?/C:?/I:?/A:P"
                },
                "description": "SaltStack Salt before 2016.3.8, 2016.11.x before 2016.11.8, "
                               "and 2017.7.x before 2017.7.2 allows remote attackers to cause "
                               "a denial of service via a crafted authentication request.",
                "id": "CVE-2017-14696",
                "references": [
                    "https://github.com/saltstack/salt/commit/"
                    "5f8b5e1a0f23fe0f2be5b3c3e04199b57a53db5b",
                    "https://docs.saltstack.com/en/latest/topics/releases/2016.11.8.html",
                    "https://docs.saltstack.com/en/latest/topics/releases/2016.3.8.html",
                    "http://lists.opensuse.org/opensuse-updates/2017-10/msg00073.html",
                    "http://lists.opensuse.org/opensuse-updates/2017-10/msg00075.html",
                    "https://bugzilla.redhat.com/show_bug.cgi?id=1500742",
                    "https://docs.saltstack.com/en/latest/topics/releases/2017.7.2.html"
                ],
                "severity": "Medium"
            }
        ]
        assert_equal(results.get('details'), expected_details)

    @pytest.mark.usefixtures('nuget')
    def test_nuget_system_net_http(self):
        args = {'ecosystem': 'nuget', 'name': 'System.Net.Http', 'version': '4.1.1'}
        task = instantiate_task(cls=CVEcheckerTask, task_name='security_issues')
        results = task.execute(arguments=args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        # https://github.com/dotnet/announcements/issues/12
        # http://www.cvedetails.com/version/220163/Microsoft-System.net.http-4.1.1.html
        assert set(results.get('summary')) >= {'CVE-2017-0247', 'CVE-2017-0248',
                                               'CVE-2017-0249', 'CVE-2017-0256'}
        details = results.get('details')
        assert isinstance(details, list) and len(details) >= 4
        for detail in details:
            assert set(detail.keys()) == {'cvss', 'description', 'id', 'references', 'severity'}
            assert detail['description']
            assert detail['references']
            assert set(detail['cvss'].keys()) == {'score', 'vector'}
