from functools import reduce

from selinonlib.predicates import *

from f8a_worker.utils import parse_gh_repo

def isGhRepo(message, key):
    try:
        val = reduce(lambda m, k: m[k], key if isinstance(key, list) else [key], message)
        if parse_gh_repo(val):
            return True
        else:
            return False
    except:
        return False
