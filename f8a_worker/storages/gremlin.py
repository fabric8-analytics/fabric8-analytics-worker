#!/usr/bin/env python3

import os
import requests


class GremlinHttpBase(object):
    def __init__(self, gremlin_http_host=None, gremlin_http_port=None):
        self.gremlin_http_host = os.getenv('GREMLIN_HTTP_HOST', gremlin_http_host)
        self.gremlin_http_port = os.getenv('GREMLIN_HTTP_PORT', gremlin_http_port)


class GremlinHttp(GremlinHttpBase):
    def store_task_result(self, ecosystem, name, version, task_name, task_result):
        # TODO: implement
        print("#"*80)
        print("Storing result for {ecosystem}/{name}/{version}, task {task_name}".format(**locals()))
        print("#"*80)


class PackageGremlinHttp(GremlinHttpBase):
    def store_task_result(self, ecosystem, name, task_name, task_result):
        # TODO: implement
        print("#"*80)
        print("Storing result for {ecosystem}/{name}/{version}, task {task_name}".format(**locals()))
        print("#"*80)
