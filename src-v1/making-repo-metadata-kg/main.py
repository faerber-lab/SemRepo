import json
import os

from rdflib import Graph, Namespace # type: ignore

from modules.Utils.constants import graph
from modules.RepoJson_to_RDF.RDF_Graphing import *
from modules.Connect_to_LPWC_and_SOA.main import connect_lpwc_and_soa


def read_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
     
    return data


def get_author_username(author):
    try:
        if author[0]['username']:
            return author[0]['username']
        
        return ''
    except Exception as e:
        print(author)
        print(f"get_author_username: {e}")
        print("==========================")


def get_author_name(author):
    try:
        if author[0]['name']:
            return author[0]['name']
        
        return ''
    except Exception as e:
        print(author)
        print(f"get_author_name: {e}")
        print("==========================")



def sort_dump(json_dump, lpwc_graph_path, git_graph):
    repo_user_name = make_repo_url(json_dump, git_graph)

    if repo_user_name:
        connect_lpwc_and_soa(lpwc_graph_path, json_dump['url'], repo_user_name, git_graph, get_author_name(json_dump['author']), get_author_username(json_dump['author']))


# =================================================================
print("Making Knowledge Graph...")

base_path = '/home/abra165f/ws_code_reuse/LPWC_Extension/Crawling_GitHub_Metadata/data'
lpwc_graph_path = '/home/abra165f/ws_code_reuse/LPWC_Extension/Creating_LPWC_Snapshot/filtered/filtered_lpwc_graph.nt'


print("==================="*5)
print("       Loaded filter LPWC Graph.")
print("==================="*5)

git_graph = Graph()

folders = os.listdir(base_path)


for folder in folders:
    files = os.listdir(os.path.join(base_path, folder))
    
    for file in files:
        sort_dump(read_json(os.path.join(base_path, folder, file)), lpwc_graph_path, git_graph)  


print("==================="*5)
print("       Saving the SemRepo KG.")
print("==================="*5)

git_graph.serialize(destination="/home/abra165f/ws_code_reuse/LPWC_Extension/Making_RDF_KG/graph/SemRepo_08-03-2025.nt", format="nt", encoding='UTF-8')