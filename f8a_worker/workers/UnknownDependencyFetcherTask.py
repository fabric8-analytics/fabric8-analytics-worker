#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 28 10:46:40 2018

@author: slakkara
"""

from __future__ import division
import os
import json
import traceback
import datetime

import requests
import os
from collections import Counter, defaultdict
import re
import logging
import semantic_version as sv

from f8a_worker.graphutils import (GREMLIN_SERVER_URL_REST, create_package_dict,select_latest_version, LICENSE_SCORING_URL_REST)
from f8a_worker.base import BaseTask
from f8a_worker.utils import get_session_retry






def get_dependency_data(self,list):
        #LIst is list of dependencies from parser
        #for item in list:
        # Hardcoded ecosystem
        #str1=("org.apache.maven.resolver:io.vertx:vertx-core:3.4.1")
        GREMLIN_SERVER_URL_REST="http://bayesian-gremlin-http-preview-b6ff-bayesian-preview.b6ff.rh-idev.openshiftapps.com"
        ecosystem="maven"
        dep_pkg_list_unknown=[]
        dep_pkg_list_known=[]
        

        #list=str1.split(":")
        #list=["io.vertx","vertx-core","3.4.1"]
        for item in list:
            list=item.split(":")
            #list=["org.apache.maven.resolver","maven-resolver-transport-wagon","1.0.3"]
            result = []
            name=list[0]+":"+list[1]
            version=list[2]
           #ecosystem="maven"
            qstring = ("g.V().has('pecosystem','" + ecosystem + "').has('pname','" + \
                   name+ "').has('version','" + version + "').tryNext()")
            payload = {'gremlin': qstring}
            try:
                graph_req = get_session_retry().post(GREMLIN_SERVER_URL_REST,data=json.dumps(payload))
                                             #json.dumps(payload))
                if graph_req.status_code == 200:
                    graph_resp = graph_req.json()
                    #graph_resp={}
                    if graph_resp.get('result', {}).get('data'):
                        result.append(graph_resp["result"])
                        if (result[0]['data'][0]['present']):
                            dep_pkg_list_known.append(ecosystem+":"+name+":"+version)
                        elif not (result[0]['data'][0]['present']):
                            dep_pkg_list_unknown.append(ecosystem+":"+name+":"+version)
                        else:
                            continue
                            
                            #store known_dependency_info in a list
                    else:
                       #self.dep_pkg_list_unknown.append(ecosystem+":"+name+":"+version) #store unknown_dependency_info in a list
                        #log.error("Failed retrieving dependency data.")
                        continue
            except Exception:
                #self.log.exception("Error retrieving dependency data.")
                #print("Error connecting server")
                #print(item)
                continue
        return (dep_pkg_list_unknown)


class UnknownDependencyFetcherTask(BaseTask): 
        def execute(self, arguments):
            result = get_dependency_data(arguments['result'])
            return {"result":result}
    
