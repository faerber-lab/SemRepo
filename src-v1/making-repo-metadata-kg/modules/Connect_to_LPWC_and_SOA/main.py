from modules.Utils.utils import make_uri
from modules.Utils.constants import *



def get_repository_object(lpwc_graph_path, search_term):
    with open(lpwc_graph_path, 'r', encoding='utf-8') as file:
        for line in file:
            if search_term in line:
                return line
            

def get_obj(file_path, search_term):
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            if search_term in line:
                return line
            

def get_author_objs(file_path, search_term):
    matching_lines = []
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            if search_term in line:
                matching_lines.append(line.strip()) 
    return matching_lines


# ========================================================================================

def connect_lpwc_and_soa(lpwc_graph_path, repo_url, repo_user_name, git_graph, author_name, author_username):

    search_term = ' <http://purl.org/spar/fabio/hasURL> <' + repo_url + '> .'

    repo_obj = get_repository_object(lpwc_graph_path, search_term)

    if repo_obj:
        cleaned_repo_obj = repo_obj.replace(search_term, '').strip().strip('<>')
        git_graph.add((make_uri('repository', repo_user_name), make_uri('property', 'hasLpwcUrl'), URIRef(cleaned_repo_obj)))


        if author_name:
            search_term_1 = ' <https://linkedpaperswithcode.com/property/hasOfficialRepository> <' + cleaned_repo_obj + '> .'
            result = get_obj(lpwc_graph_path, search_term_1)

            if result:
                paper_obj = result.replace(search_term_1, '').strip().strip('<>')

                search_term_2 = '<' + paper_obj + '>' + ' <http://purl.org/dc/terms/creator> '
                author_results = get_author_objs(lpwc_graph_path, search_term_2)

                if author_results:
                    for author in author_results:
                        author_obj = author.replace(search_term_2, '').strip().strip('<> .')
                        
                        search_term_3 = '<' + author_obj + '>' + ' <http://xmlns.com/foaf/0.1/name>'

                        author_name_soa = get_obj(lpwc_graph_path, search_term_3)

                        if author_name_soa:
                            author_name_obj = author_name_soa.replace(search_term_3, '').strip().strip('. ""')

                            if author_name_obj == author_name:
                                git_graph.add((make_uri('person', author_username), make_uri('property', 'hasSoaUrl'), URIRef(author_obj)))