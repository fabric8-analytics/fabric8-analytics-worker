from functools import reduce

from selinon.predicates import *

from f8a_worker.utils import parse_gh_repo


def isGhRepo(node_args, key):
    try:
        val = reduce(lambda m, k: m[k], key if isinstance(key, list) else [key], node_args)
        if parse_gh_repo(val):
            return True
        else:
            return False
    except Exception:
        return False
