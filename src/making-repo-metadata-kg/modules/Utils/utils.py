from rdflib import URIRef, Literal # type: ignore
import urllib.parse
from modules.Utils.constants import *


def make_uri(type_, name):
    namespace = TYPE_MAP.get(type_)
    if namespace: 
        return namespace[name]
    else: 
        return URIRef(name)


def combine_string(string1, string2):
    return string1 + "/" + string2


def sort_languages_by_percentage(languages):
    sorted_languages = sorted(languages.items(), key=lambda item: float(item[1].strip('%')) / 100, reverse=True)

    return dict(sorted_languages)


def sort_contributors_by_commits(contributors):
    return sorted(contributors, key=lambda x: x['no_of_commits'], reverse=True)


def count_issue_ratio(data):
    closed = 0
    open = 0
    for issue in data:
        if issue['issue_state'] == 'closed':
            closed+=1
        elif issue['issue_state'] == 'open':
            open+=1

    return open, closed


def parse_string(string_to_encode):
    return urllib.parse.quote(string_to_encode)


def read_lpwc_kg():
    pass