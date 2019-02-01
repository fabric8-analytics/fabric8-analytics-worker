"""Predicates used by dispatcher."""

from functools import reduce
from f8a_worker.utils import parse_gh_repo

# Required by Selinon
# You may want to update this file with new version of Selinon
from selinon.predicates import alwaysFalse
from selinon.predicates import alwaysTrue
from selinon.predicates import argsEmpty
from selinon.predicates import argsFieldBool
from selinon.predicates import argsFieldContain
from selinon.predicates import argsFieldDict
from selinon.predicates import argsFieldEqual
from selinon.predicates import argsFieldExist
from selinon.predicates import argsFieldFloat
from selinon.predicates import argsFieldGreater
from selinon.predicates import argsFieldGreaterEqual
from selinon.predicates import argsFieldInt
from selinon.predicates import argsFieldLenEqual
from selinon.predicates import argsFieldLenGreater
from selinon.predicates import argsFieldLenGreaterEqual
from selinon.predicates import argsFieldLenLess
from selinon.predicates import argsFieldLenNotEqual
from selinon.predicates import argsFieldLess
from selinon.predicates import argsFieldLessEqual
from selinon.predicates import argsFieldList
from selinon.predicates import argsFieldNone
from selinon.predicates import argsFieldNotEqual
from selinon.predicates import argsFieldStr
from selinon.predicates import argsFieldUrlNetloc
from selinon.predicates import argsFieldUrlPath
from selinon.predicates import argsFieldUrlScheme
from selinon.predicates import argsIsBool
from selinon.predicates import argsIsDict
from selinon.predicates import argsIsFloat
from selinon.predicates import argsIsInt
from selinon.predicates import argsIsList
from selinon.predicates import argsIsNone
from selinon.predicates import argsIsStr
from selinon.predicates import empty
from selinon.predicates import envEqual
from selinon.predicates import envExist
from selinon.predicates import fieldBool
from selinon.predicates import fieldContain
from selinon.predicates import fieldDict
from selinon.predicates import fieldEqual
from selinon.predicates import fieldExist
from selinon.predicates import fieldFloat
from selinon.predicates import fieldGreater
from selinon.predicates import fieldGreaterEqual
from selinon.predicates import fieldInt
from selinon.predicates import fieldLenEqual
from selinon.predicates import fieldLenGreater
from selinon.predicates import fieldLenGreaterEqual
from selinon.predicates import fieldLenLess
from selinon.predicates import fieldLenNotEqual
from selinon.predicates import fieldLess
from selinon.predicates import fieldLessEqual
from selinon.predicates import fieldList
from selinon.predicates import fieldNone
from selinon.predicates import fieldNotEqual
from selinon.predicates import fieldStr
from selinon.predicates import fieldUrlNetloc
from selinon.predicates import fieldUrlPath
from selinon.predicates import fieldUrlScheme
from selinon.predicates import httpStatus
from selinon.predicates import isBool
from selinon.predicates import isDict
from selinon.predicates import isFloat
from selinon.predicates import isInt
from selinon.predicates import isList
from selinon.predicates import isNone
from selinon.predicates import isStr


assert alwaysFalse
assert alwaysTrue
assert argsEmpty
assert argsFieldBool
assert argsFieldContain
assert argsFieldDict
assert argsFieldEqual
assert argsFieldExist
assert argsFieldFloat
assert argsFieldGreater
assert argsFieldGreaterEqual
assert argsFieldInt
assert argsFieldLenEqual
assert argsFieldLenGreater
assert argsFieldLenGreaterEqual
assert argsFieldLenLess
assert argsFieldLenNotEqual
assert argsFieldLess
assert argsFieldLessEqual
assert argsFieldList
assert argsFieldNone
assert argsFieldNotEqual
assert argsFieldStr
assert argsFieldUrlNetloc
assert argsFieldUrlPath
assert argsFieldUrlScheme
assert argsIsBool
assert argsIsDict
assert argsIsFloat
assert argsIsInt
assert argsIsList
assert argsIsNone
assert argsIsStr
assert empty
assert envEqual
assert envExist
assert fieldBool
assert fieldContain
assert fieldDict
assert fieldEqual
assert fieldExist
assert fieldFloat
assert fieldGreater
assert fieldGreaterEqual
assert fieldInt
assert fieldLenEqual
assert fieldLenGreater
assert fieldLenGreaterEqual
assert fieldLenLess
assert fieldLenNotEqual
assert fieldLess
assert fieldLessEqual
assert fieldList
assert fieldNone
assert fieldNotEqual
assert fieldStr
assert fieldUrlNetloc
assert fieldUrlPath
assert fieldUrlScheme
assert httpStatus
assert isBool
assert isDict
assert isFloat
assert isInt
assert isList
assert isNone
assert isStr


def isGhRepo(node_args, key):
    """Predicate if the repository is on GitHub."""
    try:
        val = reduce(lambda m, k: m[k], key if isinstance(key, list) else [key], node_args)
        if parse_gh_repo(val):
            return True
        else:
            return False
    except Exception:
        return False
