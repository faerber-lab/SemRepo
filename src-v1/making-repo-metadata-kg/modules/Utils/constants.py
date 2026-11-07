import rdflib # type: ignore
from rdflib import URIRef, Literal, XSD # type: ignore
from rdflib.namespace import Namespace # type: ignore
from rdflib.namespace import RDF # type: ignore

graph = rdflib.Graph()

base = Namespace("https://semrepo.org/")

repo = Namespace(f"{base}repository/")
forked_repo = Namespace(f"{base}forkedRepo/")
topic = Namespace(f"{base}topic/")
_class = Namespace(f"{base}class/")
_property = Namespace(f"{base}property/")
languageReference = Namespace(f"{base}languagereference/")
programmingLanguage = Namespace(f"{base}programminglanguage/")
person = Namespace(f"{base}person/")
contributorReference = Namespace(f"{base}contributorreference/")
status = Namespace(f"{base}issuestatus/")
issue_label_reference = Namespace(f"{base}issuelabelreference/")
label_name = Namespace(f"{base}labelname/")
bot = Namespace(f"{base}bot/")
organization = Namespace(f"{base}organization/")



DCTERMS = Namespace("http://purl.org/dc/terms/")
FABIO = Namespace("http://purl.org/spar/fabio/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")


TYPE_MAP = {
    'repository': repo,
    '_class': _class,
    'property': _property,
    'topic': topic,
    'languageReference': languageReference,
    'programmingLanguage': programmingLanguage,
    'person': person,
    'contributorReference' : contributorReference,
    'status': status,
    'forked_repo': forked_repo,
    'issue_label_reference': issue_label_reference,
    'label_name': label_name,
    'bot': bot,
    'organization': organization
}