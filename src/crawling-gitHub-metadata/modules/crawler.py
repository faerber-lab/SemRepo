import re
import requests
import base64

from bs4 import BeautifulSoup
from .utils import *


def get_repo_name_username(url, logger_obj):
    """
    Extract the repository name & author name from the given URL.

    Args:
        url (String): Repository URL.

    Returns:
        Tuple[String, String]: A tuple containing the Author Name and Repository Name.
                              If the URL is invalid or parsing fails, returns ('', '').
    """

    if not isinstance(url, str) or not url.strip():
        logger_obj.warning(f"{url}: Error: Invalid input. Expected a non-empty string.")
        return '', ''

    pattern = r"^https?://(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$"

    try:
        match = re.search(pattern, url.strip())

        if match:
            author_name = match.group(1)
            repo_name = match.group(2)
            return author_name, repo_name
        else:
            logger_obj.warning(f"{url}: Error: The provided URL is not a valid GitHub repository URL.")
            return '', ''
    
    except Exception as e:
        logger_obj.warning(f"An unexpected error occurred: {e}")
        return '', ''
    


def get_author_details(username, token, logger_obj):
    """
    Fetches and returns details of a GitHub user by their username.

    This function queries the GitHub API to retrieve profile information for the specified
    username. It extracts relevant details such as name, bio, location, email, and more,
    and returns them in a structured format.

    Args:
        username (str): The GitHub username of the user whose details are to be fetched.
        token (str, optional): A GitHub personal access token for authenticated requests.

    Returns:
        list: A list containing a dictionary with the following keys:
            - 'username' (str): The GitHub username.
            - 'user_url' (str): The URL of the user's GitHub profile.
            - 'name' (str): The full name of the user.
            - 'works_at' (str): The company the user works at.
            - 'blog' (str): The user's blog or website URL.
            - 'lives_in' (str): The user's location.
            - 'email' (str): The user's email address.
            - 'bio' (str): The user's bio or description.
            - 'twitter_username' (str): The user's Twitter handle.
            - 'user_type' (str): The type of user (e.g., 'User', 'Organization').
            - 'followers' (int): The number of followers the user has.
            - 'created_at' (str): The date the user's account was created (YYYY-MM-DD format).
            - 'updated_at' (str): The date the user's profile was last updated (YYYY-MM-DD format).
            - 'public_repos' (int): The number of public repositories the user has.

            Returns `None` if the request fails or the user is not found.

    Raises:
        None: Errors are handled internally, and a message is printed to the console if the request fails.
    """

    url = f"https://api.github.com/users/{username}"
    
    headers = {}
    if token:
        headers['Authorization'] = f'token {token}'
    
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        author_details = []
        user_details = response.json()

        author_details.append({
            'username': username,
            'user_url': user_details['html_url'],
            'name': user_details['name'],
            'works_at': user_details['company'],
            'blog': user_details['blog'],
            'lives_in': user_details['location'],
            'email': user_details['email'],
            'bio': user_details['bio'],
            'twitter_username': user_details['twitter_username'],
            'user_type': user_details['type'],
            'followers': user_details['followers'],
            'created_at': user_details['created_at'].split('T')[0],
            'updated_at': user_details['updated_at'].split('T')[0],
            'public_repos': user_details['public_repos']
        })

        return author_details
    else:
        logger_obj.warning(f"Error: Unable to fetch user details. Status code: {response.status_code}")
        return None



def get_about(soup, logger_obj):
    """
    Extracts the 'About' section text from a BeautifulSoup object representing a GitHub repository page.

    Args:
        soup (BeautifulSoup): A BeautifulSoup object containing the parsed HTML of a GitHub repository page.

    Returns:
        str: The text content of the 'About' section if found, otherwise an empty string.
    """

    if not isinstance(soup, BeautifulSoup):
        logger_obj.warning("Error: Invalid input. Expected a BeautifulSoup object.")
        return ''

    try:
        headers = soup.find_all('h2', class_='mb-3 h4')

        if not headers:
            return ''

        for header in headers:
            if 'About' in header.get_text(strip=True):
                about_paragraph = header.find_next_sibling('p', class_='f4 my-3')

                if about_paragraph:
                    return about_paragraph.get_text(strip=True)
                else:
                    return ''
        return ''

    except Exception as e:
        logger_obj.warning(f"An unexpected error occurred: {e}")
        return ''



def get_topics(soup, logger_obj):
    """
    Extracts and returns a list of topics from a GitHub repository page's BeautifulSoup object.

    Args:
        soup (BeautifulSoup): A BeautifulSoup object representing the parsed HTML of a GitHub repository page.

    Returns:
        List[str]: A list of topics/tags associated with the repository. If no topics are found or an error occurs,
                   an empty list is returned.
    """

    if not isinstance(soup, BeautifulSoup):
        logger_obj.warning("Error: Invalid input. Expected a BeautifulSoup object.")
        return []

    all_topics = []

    try:
        topic_section = soup.find('h3', text='Topics')
        
        if topic_section:
            topic_link = topic_section.find_next_sibling('div', class_='my-3')
            
            if topic_link:
                topic_tags = topic_link.find_all('a', class_='topic-tag topic-tag-link')
                
                all_topics = [tag.get_text(strip=True) for tag in topic_tags]
        
        return all_topics

    except Exception as e:
        logger_obj.warning(f"An unexpected error occurred while extracting topics: {e}")
        return []



def get_languages(soup, logger_obj):
    """
    Extracts programming languages and their usage percentages from a GitHub repository's HTML soup.

    Args:
        soup (BeautifulSoup): A BeautifulSoup object representing the parsed HTML of a GitHub repository page.

    Returns:
        dict: A dictionary where keys are programming language names and values are their usage percentages.
              If no languages are found or the input is invalid, returns an empty dictionary.

    Example:
        {'Python': '60%', 'JavaScript': '30%', 'HTML': '10%'}
    """
    
    if not isinstance(soup, BeautifulSoup):
        logger_obj.warning("Error: Invalid input. Expected a BeautifulSoup object.")
        return {}

    links = soup.find_all('h2', class_='h4 mb-3')

    languages = {}

    for link in links:
        if 'Languages' in link.text:

            ul = link.find_next_sibling('ul', class_='list-style-none')
            if not ul:
                continue

            span1 = ul.find_all('span', class_='color-fg-default text-bold mr-1')
            for lang_span in span1:
                key = lang_span.text.strip()
                value_tag = lang_span.find_next_sibling()
                value = value_tag.text.strip() if value_tag else "N/A"
                languages[key] = value

    return languages



def get_stars(repo_url, github_token, logger_obj, max_stars=10000):
    """
    Fetches stargazers for a GitHub repository.

    Args:
        repo_url (str): URL of the GitHub repository.
        github_token (str): GitHub token for API access.
        max_stars (int, optional): Max stargazers to fetch. Defaults to 10,000.

    Returns:
        list: List of stargazers, each as a dict with 'user_name' and 'user_url'.
    """

    parts = repo_url.strip('/').split('/')
    owner = parts[-2]
    repo = parts[-1]
    
    base_url = f"https://api.github.com/repos/{owner}/{repo}/stargazers"
    all_stars = []
    page = 1

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3.star+json"
    }

    while True:
        request_url = f"{base_url}?page={page}&per_page=100"
        response = requests.get(request_url, headers=headers)
        
        if response.status_code != 200:
            logger_obj.warning(f"Error: {response.status_code} - {response.json().get('message', 'Unknown error')}")
            break

        stargazers = response.json()
        if not stargazers:
            break

        for stargazer in stargazers:
            user_name = stargazer['user']['login']
            url = "https://github.com/" + user_name

            all_stars.append({'user_name': user_name, 'user_url': url})


        if len(all_stars) >= max_stars:
            break

        page += 1

    return all_stars



def get_watchers(repo_url, github_token, logger_obj, max_watchers=10000):
    """
    Fetches watchers of a GitHub repository.

    Args:
        repo_url (str): URL of the GitHub repository.
        github_token (str): GitHub personal access token.
        max_watchers (int, optional): Max watchers to fetch. Defaults to 10,000.

    Returns:
        list: List of watchers with their username and profile URL.
    """

    parts = repo_url.strip('/').split('/')
    owner = parts[-2]
    repo = parts[-1]
    
    base_url = f"https://api.github.com/repos/{owner}/{repo}/subscribers"
    all_watchers = []
    page = 1

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }

    while True:
        request_url = f"{base_url}?page={page}&per_page=100"
        response = requests.get(request_url, headers=headers)
        
        if response.status_code != 200:
            logger_obj.warning(f"Error: {response.status_code} - {response.json().get('message', 'Unknown error')}")
            break

        watchers = response.json()
        if not watchers:
            break

        for watcher in watchers:
            user_name = watcher['login']
            url = "https://github.com/" + user_name
            
            all_watchers.append({'user_name': user_name, 'user_url': url})

        if len(all_watchers) >= max_watchers:
            break

        page += 1

    return all_watchers



def get_forks(repo_url, github_token, logger_obj ,max_forks=1000):
    """
    Fetches active forks of a GitHub repository using the GitHub API.

    Args:
        repo_url (str): URL of the GitHub repository.
        github_token (str): GitHub personal access token.
        max_forks (int, optional): Max active forks to fetch. Defaults to 1000.

    Returns:
        list: A list of dictionaries, where each dictionary contains details about an active fork:
            - 'user_name': The GitHub username of the fork owner.
            - 'repo_forked_as': The full name of the forked repository (e.g., "owner/repo").
            - 'forked_repo_url': The URL of the forked repository on GitHub.
            - 'created_at': The date the fork was created (in 'YYYY-MM-DD' format).
            - 'updated_at': The date the fork was last updated (in 'YYYY-MM-DD' format).
            - 'stargzers_count': The number of stargazers for the forked repository.
            - 'watchers_count': The number of watchers for the forked repository.
            - 'forks_count': The number of forks of the forked repository.
            - 'open_issues_count': The number of open issues in the forked repository.
    """

    owner, repo = repo_url.strip('/').split('/')[-2:]
    base_url = f"https://api.github.com/repos/{owner}/{repo}/forks"
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
    all_forks = []
    page = 1

    while len(all_forks) < max_forks:
        response = requests.get(f"{base_url}?page={page}&per_page=100", headers=headers)
        
        if response.status_code != 200 or not (forks := response.json()):
            break

        for fork in forks:
            if fork['updated_at'] != fork['created_at']:
                fork_details = {
                    'user_name': fork['owner']['login'],
                    'user_url': "https://github.com/" + fork['owner']['login'],
                    'repo_forked_as': fork['full_name'],
                    'forked_repo_url': fork['html_url'],
                    'created_at': fork['created_at'].split('T')[0],
                    'updated_at': fork['updated_at'].split('T')[0],
                    'stargzers_count': fork['stargazers_count'],
                    'watchers_count': fork['watchers_count'],
                    'forks_count': fork['forks_count'],
                    'open_issues_count': fork['open_issues_count']
                }
                all_forks.append(fork_details)

        page += 1

    return all_forks



def get_contributors(repo_url, token, logger_obj, max_contributors=10000):
    """
    Fetches contributors of a GitHub repository using the GitHub API.

    Args:
        owner (str): Owner of the repository.
        repo (str): Name of the repository.
        token (str): GitHub personal access token for authentication.
        max_contributors (int, optional): Maximum number of contributors to fetch. Defaults to 10,000.

    Returns:
        list: List of contributors with their username, user url and number of commits.
    """

    owner, repo = repo_url.strip('/').split('/')[-2:]
    base_url = f"https://api.github.com/repos/{owner}/{repo}/contributors"
    headers = {'Authorization': f'token {token}'} if token else {}
    all_contributors = []
    page = 1

    while len(all_contributors) < max_contributors:
        response = requests.get(base_url, headers=headers, params={'per_page': 100, 'page': page})

        if response.status_code == 200:
            contributors = response.json()
            if not contributors:
                break

            for contributor in contributors:
                all_contributors.append({
                    'user_name': contributor.get('login', 'N/A'),
                    'user_url': "https://github.com/" + contributor.get('login', 'N/A'),
                    'no_of_commits': contributor.get('contributions', 0)
                })

            page += 1
        elif response.status_code == 403:
            logger_obj.warning("Rate limit exceeded. Please wait or use a token.")
            break
        elif response.status_code == 404:
            logger_obj.warning("Repository not found. Please check the owner and repo names.")
            break
        else:
            logger_obj.warning(f"Failed to fetch contributors: {response.status_code} - {response.reason}")
            break


    return all_contributors



def get_issues(repo_url, token, logger_obj, max_issues=20000):
    """
    Fetch both open and closed issues from a GitHub repository using the GitHub API.

    Args:
        repo_url (str): The URL of the GitHub repository.
        token (str): GitHub personal access token for authentication.
        max_issues (int, optional): Maximum number of issues to fetch. Defaults to 20000.

    Returns:
        list[dict]: A list of dictionaries, where each dictionary represents an issue.
            Each issue dictionary contains the following keys:
                - 'issue_id': int - The issue number.
                - 'issue_title': str - The title of the issue.
                - 'issue_url': str - The URL to the issue on GitHub.
                - 'issue_state': str - The state of the issue (e.g., 'open' or 'closed').
                - 'issue_labels': list[str] - A list of labels associated with the issue.
                - 'issue_author': str - The GitHub username of the issue author.
                - 'issue_author_type': str - The type of the issue author (e.g., 'User' or 'Bot').
                - 'issue_author_url': str - The URL to the issue author's GitHub profile.
                - 'issue_assigned_to': list[str] - A list of usernames assigned to the issue.
                - 'issue_created_at': str - The creation date of the issue in 'YYYY-MM-DD' format.
                - 'issue_updated_at': str - The last update date of the issue in 'YYYY-MM-DD' format.
                - 'issue_comments_count': int - The number of comments on the issue.
                - 'reactions': dict - A dictionary of reactions (e.g., thumbs up, thumbs down) on the issue.

    Raises:
        Exception: If the API request fails (non-200 status code), an exception is raised with the error details.
    """

    owner, repo = repo_url.strip('/').split('/')[-2:]
    all_issues = []
    base_url = f"https://api.github.com/repos/{owner}/{repo}/issues"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    params = {
        "state": "all",  
        "per_page": 100, 
        "page": 1
    }

    while len(all_issues) < max_issues:
        response = requests.get(base_url, headers=headers, params=params)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch issues: {response.status_code} - {response.text}")

        current_issues = response.json()
        if not current_issues:
            break  

        for issue in current_issues:
            if 'pull_request' not in issue:
                all_issues.append({
                    'issue_id': issue['number'],
                    'issue_title': issue['title'],
                    'issue_url': issue['html_url'],
                    'issue_state': issue['state'],
                    'issue_labels': format_issue_labels(issue['labels']),
                    'issue_author': issue['user']['login'],
                    'issue_author_type': issue['user']['type'],
                    'issue_author_url': issue['user']['html_url'],
                    'issue_assigned_to': format_issue_assigned_to(issue['assignees']),
                    'issue_created_at': issue['created_at'].split('T')[0],
                    'issue_updated_at': issue['updated_at'].split('T')[0],
                    'issue_comments_count': issue['comments'],
                    'reactions': format_issue_reaction(issue['reactions'])
                })
        
        params["page"] += 1

    return all_issues



def get_readme_content(repo_url, token, logger_obj):
    owner, repo = repo_url.strip('/').split('/')[-2:]

    base_url = f"https://api.github.com/repos/{owner}/{repo}/readme"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+raw"
    }

    response = requests.get(base_url, headers=headers)

    if response.status_code == 200:
        readme_content = base64.b64decode(response.json()["content"]).decode("utf-8")
    
        return readme_content
    
    else:
        return ''