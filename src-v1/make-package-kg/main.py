import json
import os
import rdflib # type: ignore


from tqdm import tqdm # type: ignore
from rdflib import URIRef, Literal # type: ignore


def read_json_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

        return data
    

def get_username_reponame(url):
    username, repo_name = url.split('/')[-2:][::-1]

    return username, repo_name


def combine_string(string1, string2):
    return string1 + '/' + string2


json_folder = '/home/abra165f/ws_code_reuse/LPWC_Extension/Extract_Libraries/package_data'
json_files = os.listdir(json_folder)

print("Total Repos: ", len(json_files))


graph_package = rdflib.Graph()

pkg_lst = []


for _file in tqdm(json_files, desc="Processing files"):
    dump = read_json_file(os.path.join(json_folder, _file))
    username, repo_name = get_username_reponame(dump['url'])

    repo_user_name = combine_string(username, repo_name)


    for pkg_name in dump['used_package']:

        graph_package.add((URIRef(combine_string('https://semrepo.org/repository', repo_user_name)), URIRef('https://semrepo.org/property/usedPackage'), URIRef(combine_string('https://semrepo.org/package', pkg_name))))

        if pkg_name not in pkg_lst:
            graph_package.add((URIRef(combine_string('https://semrepo.org/package', pkg_name)), URIRef('http://purl.org/dc/terms/title'), Literal(pkg_name)))

            graph_package.add((URIRef(combine_string('https://semrepo.org/package', pkg_name)), URIRef('http://purl.org/spar/fabio/hasUrl'), URIRef(combine_string('https://pypi.org/project', pkg_name))))

            pkg_lst.append(pkg_name)



graph_package.serialize(destination='/home/abra165f/ws_code_reuse/LPWC_Extension/Make_Package_KG/graph/package_10-03-2025.nt', format='nt', encoding='UTF-8')