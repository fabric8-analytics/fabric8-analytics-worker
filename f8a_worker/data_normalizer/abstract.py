"""Abstract data normalizer."""

import abc

from f8a_worker.utils import parse_gh_repo


class AbstractDataNormalizer(abc.ABC):
    """Abstract data normalizer.

    Base class for all other data normalizers.
    """

    """Mapping from ecosystem-specific keys to their normalized form.

    E.g: (('licenses', 'declared_licenses'),)
    """
    _key_map = tuple()

    @abc.abstractmethod
    def __init__(self, mercator_json):
        """Initialize function.

        :param mercator_json: dict, data from mercator
        """
        self._raw_data = mercator_json
        self._data = self._transform_keys(self._key_map)

    @abc.abstractmethod
    def normalize(self):
        """Normalize output from Mercator."""

    def _transform_keys(self, keymap, lower=True):
        """Collect known keys and/or rename existing keys.

        :param keymap: n-tuple of 2-tuples
            each 2-tuple can have one of these forms:
            ('a',) - get 'a'
            ('b', 'c',) - get 'b' and rename it to 'c'
            (('d', 'e',),) - get 'd' or 'e'
            (('f', 'g',), 'h') - get 'f' or 'g' and rename it to 'h'
        :param lower: bool, convert keys to lowercase
        :return: dictionary with keys from keymap only
        """
        out = {}
        value = None
        for pair in keymap:
            in_key = pair[0]
            if not isinstance(in_key, tuple):
                value = self._raw_data.get(in_key, None)
            else:  # e.g. ('license', 'licenses',)
                for in_k in in_key:
                    value = self._raw_data.get(in_k, None)
                    if value is not None:
                        break
                in_key = in_k
            key = in_key if len(pair) == 1 else pair[1]
            if lower:
                key = key.lower()
            out[key] = value
        return out

    @staticmethod
    def _join_name_email(name_email_dict, name_key='name', email_key='email'):
        """Join name and email values into a string.

        # {'name':'A', 'email':'B@C.com'} -> 'A <B@C.com>'
        """
        if not isinstance(name_email_dict, dict):
            return None

        if not name_email_dict:
            return None

        name_email_str = name_email_dict.get(name_key) or ''
        if isinstance(name_email_dict.get(email_key), str):
            if name_email_str:
                name_email_str += ' '
            name_email_str += '<' + name_email_dict[email_key] + '>'
        return name_email_str

    @staticmethod
    def _rf(iterable):
        """Remove false/empty/None items from iterable."""
        return list(filter(None, iterable))

    @staticmethod
    def _split_keywords(keywords, separator=None):
        """Split keywords (string) with separator.

        If separator is not specified, use either colon or whitespace.
        """
        if keywords is None:
            return []
        if isinstance(keywords, list):
            return keywords
        if separator is None:
            separator = ',' if ',' in keywords else ' '
        keywords = keywords.split(separator)
        keywords = [kw.strip() for kw in keywords]
        return keywords

    @staticmethod
    def _identify_gh_repo(homepage):
        """Return code repository dict filled with homepage."""
        if parse_gh_repo(homepage):
            return {'url': homepage, 'type': 'git'}
        return None
