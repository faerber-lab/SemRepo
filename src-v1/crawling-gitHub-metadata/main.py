import requests
import pickle
import time
import json
import os

from requests.adapters import HTTPAdapter, Retry

from modules.crawler import *
from logger import get_logger

# Constants
MAX_RETRIES = 20
BACKOFF_FACTOR = 0.3
STATUS_FORCELIST = [429]
ALLOWED_METHODS = ["HEAD", "GET", "OPTIONS"]
MIN_TOKEN_LIMIT = 10

# Configure retry strategy for requests
retry_strategy = Retry(
    total=MAX_RETRIES,
    backoff_factor=BACKOFF_FACTOR,
    status_forcelist=STATUS_FORCELIST,
    allowed_methods=ALLOWED_METHODS
)
adapter = HTTPAdapter(max_retries=retry_strategy)

# Create a session with retry logic
session = requests.Session()
session.mount("http://", adapter)
session.mount("https://", adapter)


def read_pkl_file(file_path: str):
    """Read and return data from a pickle file."""
    try:
        with open(file_path, 'rb') as file:
            return pickle.load(file)
        
    except (pickle.PickleError, FileNotFoundError) as e:
        logger_obj.warning(f"Error reading pickle file: {e}")
        return None



def check_token_limit(token):
    headers = {"Authorization": f"token {token}"}
    url = "https://api.github.com/rate_limit"

    try:
        response = session.get(url, headers=headers)
        response.raise_for_status()
        rate_limit_data = response.json()["rate"]
        return rate_limit_data["remaining"]
    
    except requests.exceptions.RequestException as e:
        logger_obj.warning(f"Error checking token limit for {token}: {e}")
        return None



def handle_token_exhaustion(all_tokens):
    reset_time = None
    headers = {"Authorization": f"token {all_tokens[0]}"}
    url = "https://api.github.com/rate_limit"

    try:
        response = session.get(url, headers=headers)
        response.raise_for_status()
        reset_time = response.json()["rate"]["reset"]
    except requests.exceptions.RequestException as e:
        logger_obj.warning(f"Error fetching reset time for token {all_tokens[0]}: {e}")
        return

    if reset_time:
        current_time = time.time()
        wait_time = max(reset_time - current_time, 0) 
        logger_obj.info(f"All tokens exhausted. Waiting for {wait_time:.0f} seconds until the first token resets.")
        time.sleep(wait_time + 10) 
        logger_obj.info(f"Resetting to the first token: {all_tokens[0]}")



def check_tokens_limit(all_tokens, current_index):
    remaining = check_token_limit(all_tokens[current_index])
    if remaining is not None and remaining > MIN_TOKEN_LIMIT:
        return all_tokens[current_index], current_index

    current_index = (current_index + 1) % len(all_tokens)
    logger_obj.info(f"************Switched to token: {all_tokens[current_index]}")

    all_exhausted = True
    for token in all_tokens:
        remaining = check_token_limit(token)
        if remaining is not None and remaining > MIN_TOKEN_LIMIT:
            all_exhausted = False
            break

    if all_exhausted:
        handle_token_exhaustion(all_tokens)
        current_index = 0

    return all_tokens[current_index], current_index



def create_folder_if_not_exists(folder_path: str) -> None:
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        logger_obj.info(f"Folder created: {folder_path}")
    else:
        logger_obj.info(f"Folder already exists: {folder_path}")



def process_github_repos(github_links, github_tokens_file_path, save_json_file) -> None:
    all_tokens = read_pkl_file(github_tokens_file_path)

    if not all_tokens:
        logger_obj.warning("No tokens available. Exiting.")
        return
    
    create_folder_if_not_exists(save_json_file)

    all_saved_file = os.listdir(save_json_file)

    token_index = 0
    token = all_tokens[token_index]

    logger_obj.info(f'Total Repos: {len(github_links)}')
    logger_obj.info("===============================================================================================")

    count = 1

    for url in github_links:
        repo_info = get_repo_name_username(url, logger_obj)

        if not repo_info:
            continue

        author_username, repo_name = repo_info
        
        file_name_to_compare = f'{author_username}_{repo_name}_repo.json'

        if file_name_to_compare in all_saved_file:
            continue
        else:
            logger_obj.info(f'This was left: {url}')

        response = session.get(url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")

            try:
                author_dict = get_author_details(author_username, token, logger_obj) 
                token, token_index = check_tokens_limit(all_tokens, token_index)

                about = get_about(soup, logger_obj)
                topics_lst = get_topics(soup, logger_obj)
                languages_lst = get_languages(soup, logger_obj)

                star_lst = get_stars(url, token, logger_obj)
                token, token_index = check_tokens_limit(all_tokens, token_index)

                watcher_lst = get_watchers(url, token, logger_obj)
                token, token_index = check_tokens_limit(all_tokens, token_index)

                forks_lst = get_forks(url, token, logger_obj)
                token, token_index = check_tokens_limit(all_tokens, token_index)

                contributors_lst = get_contributors(url, token, logger_obj)
                token, token_index = check_tokens_limit(all_tokens, token_index)

                issue_lst = get_issues(url, token, logger_obj)
                token, token_index = check_tokens_limit(all_tokens, token_index)

                readme_content = get_readme_content(url, token, logger_obj)
                token, token_index = check_tokens_limit(all_tokens, token_index)


                with open(f"{save_json_file}/{author_username}_{repo_name}_repo.json", "w") as f:
                    json.dump({
                        'url': url,
                        'repositoryName': repo_name,
                        'about': about,
                        'topics': topics_lst,
                        'languages': languages_lst,
                        'author': author_dict,
                        'stars': star_lst,
                        'watchers': watcher_lst,
                        'forks': forks_lst,
                        'contributors': contributors_lst,
                        'issues': issue_lst,
                        'ReadMe': readme_content
                    }, f, indent=4)

                    logger_obj.info(f'Repository Crawled:  {url} ---  {count} Done')
                    logger_obj.info("===============================================================================================")
                    count+=1

            except Exception as e:
                logger_obj.warning(f"Error: {e}")



# File paths
file_path_github_links = '/home/abra165f/ws_code_reuse/LPWC_Extension/Crawling_GitHub_Metadata/github_links/170001_175000.pkl'
file_name_without_extension = os.path.splitext(os.path.basename(file_path_github_links))[0]

file_path_tokens = '/home/abra165f/ws_code_reuse/LPWC_Extension/Crawling_GitHub_Metadata/tokens/tokens.pkl'
file_path_save_json = os.path.join('/home/abra165f/ws_code_reuse/LPWC_Extension/Crawling_GitHub_Metadata/data', file_name_without_extension)
file_path_logs = '/home/abra165f/ws_code_reuse/LPWC_Extension/Crawling_GitHub_Metadata/logs'

logger_obj = get_logger(file_path_logs, file_name_without_extension)

# Execute the process
github_links = read_pkl_file(file_path_github_links)

if github_links:
    process_github_repos(github_links, file_path_tokens, file_path_save_json)
else:
    logger_obj.warning("No GitHub links found.")