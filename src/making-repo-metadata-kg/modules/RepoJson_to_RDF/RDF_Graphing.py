from modules.Utils.utils import make_uri, combine_string, sort_languages_by_percentage, sort_contributors_by_commits, count_issue_ratio, parse_string
from modules.Utils.constants import *


def make_repo_url(data, graph):
    username, repo_name = data['url'].split('/')[-2:]
    repo_user_name = combine_string(username, repo_name)

    graph.add((make_uri('repository', repo_user_name), RDF.type, make_uri('_class', 'repository')))
    graph.add((make_uri('repository', repo_user_name), FABIO.hasURL, URIRef(data['url'])))
    graph.add((make_uri('repository', repo_user_name), DCTERMS.title, Literal(repo_name)))

    make_repo_about(repo_user_name, data['about'], graph)
    make_repo_topics(repo_user_name, data['topics'], graph)
    make_repo_language(repo_user_name, sort_languages_by_percentage(data['languages']), graph)
    make_repo_author(repo_user_name, data['author'], graph)
    make_repo_stargazers(repo_user_name, data['stars'], graph)
    make_repo_watchers(repo_user_name, data['watchers'], graph)
    make_repo_contributors(repo_user_name, sort_contributors_by_commits(data['contributors']), graph)
    make_repo_forks(repo_user_name, data['forks'], graph)
    make_repo_readme(repo_user_name, data['ReadMe'], graph)
    make_repo_issues(repo_user_name, data['issues'], graph)

    return repo_user_name



def make_repo_about(repo_user_name, repo_about, graph):
    if repo_about:
        graph.add((make_uri('repository', repo_user_name), DCTERMS.abstract, Literal(repo_about)))



def make_repo_topics(repo_user_name, repo_topics, graph):
    if repo_topics:
        for topic in repo_topics:
            graph.add((make_uri('repository', repo_user_name), FOAF.topic, make_uri('topic', topic)))



def make_repo_language(repo_user_name, repo_languages, graph):
    if repo_languages:
        count = 1

        for language_name, used_percentage in repo_languages.items():
            used_percentage = float(used_percentage.strip('%'))

            temp_string = combine_string(repo_user_name, str(count))

            graph.add((make_uri('repository', repo_user_name), make_uri('property', 'hasLanguageReference'), make_uri('languageReference', temp_string)))
            graph.add((make_uri('languageReference', temp_string), make_uri('property', 'hasLanguageName'), make_uri('programmingLanguage', parse_string(language_name))))
            graph.add((make_uri('languageReference', temp_string), make_uri('property', 'hasLanguageUsage'), Literal(used_percentage, datatype=XSD.float)))

            if count == 1:
                graph.add((make_uri('repository', repo_user_name), make_uri('property', 'hasPrimaryProgrammingLanguage'), make_uri('languageReference', temp_string)))

            count+=1



def make_repo_author(repo_user_name, repo_authors, graph):
    if repo_authors:
        for author in repo_authors:
            try:
                if author['user_type'] == 'User':
                    make_repo_author_user(repo_user_name, author, graph)

                elif author['user_type'] == 'Organization':
                    make_repo_author_organization(repo_user_name, author, graph)

            except Exception as e:
                print(f"Error processing author {author}: {e}")



def make_repo_author_organization(repo_user_name, repo_authors_organization, graph):
    graph.add((make_uri('organization', repo_authors_organization['username']), RDF.type, make_uri('_class', 'organization')))
    graph.add((make_uri('organization', repo_authors_organization['username']), FOAF.accountName, Literal(repo_authors_organization['username'])))
    graph.add((make_uri('organization', repo_authors_organization['username']), FABIO.hasUrl, URIRef(repo_authors_organization['user_url'])))

    graph.add((make_uri('organization', repo_authors_organization['username']), FOAF.name, Literal(repo_authors_organization['name'])))

    if repo_authors_organization['lives_in']: graph.add((make_uri('organization', repo_authors_organization['username']), make_uri('property', 'hasLocation'), Literal(repo_authors_organization['lives_in'])))
    
    if repo_authors_organization['blog']: graph.add((make_uri('organization', repo_authors_organization['username']), make_uri('property', 'hasBlog'), Literal(repo_authors_organization['blog'])))
    if repo_authors_organization['email']: graph.add((make_uri('organization', repo_authors_organization['username']), FOAF.mbox, Literal(repo_authors_organization['email'])))
    if repo_authors_organization['bio']: graph.add((make_uri('organization', repo_authors_organization['username']), FOAF.description, Literal(repo_authors_organization['bio'])))

    if repo_authors_organization['twitter_username']: graph.add((make_uri('organization', repo_authors_organization['username']), make_uri('property', 'hasTwitterAccount'), Literal(repo_authors_organization['twitter_username'])))
    if repo_authors_organization['followers']: graph.add((make_uri('organization', repo_authors_organization['username']), make_uri('property', 'hasFollowers'), Literal(repo_authors_organization['followers'], datatype=XSD.int)))
    
    graph.add((make_uri('organization', repo_authors_organization['username']), DCTERMS.created, Literal(repo_authors_organization['created_at'], datatype=XSD.date)))
    
    if repo_authors_organization['public_repos']: graph.add((make_uri('organization', repo_authors_organization['username']), make_uri('property', 'hasPublicRepository'), Literal(repo_authors_organization['public_repos'], datatype=XSD.int)))

    graph.add((make_uri('repository', repo_user_name), DCTERMS.creator, make_uri('organization', repo_authors_organization['username'])))

            

def make_repo_author_user(repo_user_name, repo_authors_users, graph):
    graph.add((make_uri('person', repo_authors_users['username']), RDF.type, make_uri('_class', 'person')))
    graph.add((make_uri('person', repo_authors_users['username']), make_uri('property', 'hasPersonType'), make_uri('_class', 'author')))
    graph.add((make_uri('person', repo_authors_users['username']), FOAF.accountName, Literal(repo_authors_users['username'])))
    graph.add((make_uri('person', repo_authors_users['username']), FABIO.hasUrl, URIRef(repo_authors_users['user_url'])))

    graph.add((make_uri('person', repo_authors_users['username']), FOAF.name, Literal(repo_authors_users['name'])))

    if repo_authors_users['works_at']: graph.add((make_uri('person', repo_authors_users['username']), FOAF.affiliation, Literal(repo_authors_users['works_at'])))
    if repo_authors_users['lives_in']: graph.add((make_uri('person', repo_authors_users['username']), make_uri('property', 'hasLocation'), Literal(repo_authors_users['lives_in'])))
    
    if repo_authors_users['blog']: graph.add((make_uri('person', repo_authors_users['username']), make_uri('property', 'hasBlog'), Literal(repo_authors_users['blog'])))
    if repo_authors_users['email']: graph.add((make_uri('person', repo_authors_users['username']), FOAF.mbox, Literal(repo_authors_users['email'])))
    if repo_authors_users['bio']: graph.add((make_uri('person', repo_authors_users['username']), FOAF.description, Literal(repo_authors_users['bio'])))

    if repo_authors_users['twitter_username']: graph.add((make_uri('person', repo_authors_users['username']), make_uri('property', 'hasTwitterAccount'), Literal(repo_authors_users['twitter_username'])))
    if repo_authors_users['followers']: graph.add((make_uri('person', repo_authors_users['username']), make_uri('property', 'hasFollowers'), Literal(repo_authors_users['followers'], datatype=XSD.int)))
    
    graph.add((make_uri('person', repo_authors_users['username']), DCTERMS.created, Literal(repo_authors_users['created_at'], datatype=XSD.date)))
    
    if repo_authors_users['public_repos']: graph.add((make_uri('person', repo_authors_users['username']), make_uri('property', 'hasPublicRepository'), Literal(repo_authors_users['public_repos'], datatype=XSD.int)))

    graph.add((make_uri('repository', repo_user_name), DCTERMS.creator, make_uri('person', repo_authors_users['username'])))



def make_repo_stargazers(repo_user_name, repo_stargazers, graph):
    if repo_stargazers:
        
        graph.add((make_uri('repository', repo_user_name), make_uri('property', 'hasTotalStargazers'), Literal(len(repo_stargazers), datatype=XSD.int)))
        for stargazer in repo_stargazers:
            graph.add((make_uri('person', stargazer['user_name']), RDF.type, make_uri('_class', 'person')))
            graph.add((make_uri('person', stargazer['user_name']), make_uri('property', 'hasPersonType'), make_uri('_class', 'stargazer')))
            graph.add((make_uri('repository', repo_user_name), make_uri('property', 'hasStargazer'), make_uri('person', stargazer['user_name'])))
            graph.add((make_uri('person', stargazer['user_name']), FOAF.accountName, Literal(stargazer['user_name'])))
            graph.add((make_uri('person', stargazer['user_name']), FABIO.hasUrl, URIRef(stargazer['user_url'])))



def make_repo_watchers(repo_user_name, repo_watchers, graph):
    if repo_watchers:

        graph.add((make_uri('repository', repo_user_name), make_uri('property', 'hasTotalWatchers'), Literal(len(repo_watchers), datatype=XSD.int)))
        for watcher in repo_watchers:
            graph.add((make_uri('person', watcher['user_name']), RDF.type, make_uri('_class', 'person')))
            graph.add((make_uri('person', watcher['user_name']), make_uri('property', 'hasPersonType'), make_uri('_class', 'watcher')))
            graph.add((make_uri('repository', repo_user_name), make_uri('property', 'hasWatcher'), make_uri('person', watcher['user_name'])))
            graph.add((make_uri('person', watcher['user_name']), FOAF.accountName, Literal(watcher['user_name'])))
            graph.add((make_uri('person', watcher['user_name']), FABIO.hasUrl, URIRef(watcher['user_url'])))



def make_repo_contributors(repo_user_name, repo_contributors, graph):
    if repo_contributors:
        count = 1

        graph.add((make_uri('repository', repo_user_name), make_uri('property', 'hasTotalContributor'), Literal(len(repo_contributors), datatype=XSD.int)))
        for contributor in repo_contributors:
            temp_string = combine_string(repo_user_name, str(count))

            graph.add((make_uri('person', contributor['user_name']), RDF.type, make_uri('_class', 'person')))
            graph.add((make_uri('person', contributor['user_name']), make_uri('property', 'hasPersonType'), make_uri('_class', 'contributor')))
            graph.add((make_uri('person', contributor['user_name']), FOAF.accountName, Literal(contributor['user_name'])))
            graph.add((make_uri('person', contributor['user_name']), FABIO.hasUrl, URIRef(contributor['user_url'])))

            graph.add((make_uri('repository', repo_user_name), make_uri('property', 'hasContributorReference'), make_uri('contributorReference', temp_string)))
            graph.add((make_uri('contributorReference', temp_string), make_uri('property', 'hasContributor'), make_uri('person', contributor['user_name'])))
            graph.add((make_uri('contributorReference', temp_string), make_uri('property', 'hasCommits'), Literal(contributor['no_of_commits'], datatype=XSD.int)))

            if count == 1 and contributor['no_of_commits'] != 0:
                graph.add((make_uri('repository', repo_user_name), make_uri('property', 'hasTopContributor'), make_uri('contributorReference', temp_string)))
            
            count+=1



def make_repo_forks(repo_user_name, repo_forks, graph):
    if repo_forks:
        
        graph.add((make_uri('repository', repo_user_name), make_uri('property', 'hasTotalForks'), Literal(len(repo_forks), datatype=XSD.int)))
        for fork in repo_forks:
            graph.add((make_uri('repository', repo_user_name), make_uri('property', 'forkedAs'), make_uri('forked_repo', fork['repo_forked_as'])))


            graph.add((make_uri('forked_repo', fork['repo_forked_as']), make_uri('property', 'forkedBy'), make_uri('person', fork['user_name'])))
            graph.add((make_uri('forked_repo', fork['repo_forked_as']), FABIO.hasUrl, URIRef(fork['forked_repo_url'])))
            graph.add((make_uri('forked_repo', fork['repo_forked_as']), DCTERMS.created, Literal(fork['created_at'], datatype=XSD.date)))

            graph.add((make_uri('forked_repo', fork['repo_forked_as']), make_uri('property', 'hasTotalOpenIssues'), Literal(fork['open_issues_count'], datatype=XSD.int)))
            graph.add((make_uri('forked_repo', fork['repo_forked_as']), make_uri('property', 'hasTotalForks'), Literal(fork['forks_count'], datatype=XSD.int)))
            graph.add((make_uri('forked_repo', fork['repo_forked_as']), make_uri('property', 'hasTotalStargazers'), Literal(fork['stargzers_count'], datatype=XSD.int)))
            graph.add((make_uri('forked_repo', fork['repo_forked_as']), make_uri('property', 'hasTotalWatchers'), Literal(fork['watchers_count'], datatype=XSD.int)))


            graph.add((make_uri('person', fork['user_name']), RDF.type,  make_uri('_class', 'person')))
            graph.add((make_uri('person', fork['user_name']), make_uri('property', 'hasPersonType'), make_uri('_class', 'forker')))
            graph.add((make_uri('person', fork['user_name']), FABIO.hasUrl,  URIRef(fork['user_url'])))
            graph.add((make_uri('person', fork['user_name']), FABIO.accountName,  Literal(fork['user_name'])))



def make_repo_readme(repo_user_name, repo_readme, graph):
    if repo_readme:
        graph.add((make_uri('repository', repo_user_name), make_uri('property', 'hasReadMeContent'), Literal(repo_readme)))



def make_repo_issues(repo_user_name, repo_issues, graph):
    if repo_issues:
        open, closed = count_issue_ratio(repo_issues)

        graph.add((make_uri('repository', repo_user_name), make_uri('property', 'hasTotalIssues'), Literal(len(repo_issues), datatype=XSD.int)))
        graph.add((make_uri('repository', repo_user_name), make_uri('property', 'hasTotalOpenIssues'), Literal(open, datatype=XSD.int)))
        graph.add((make_uri('repository', repo_user_name), make_uri('property', 'hasTotalClosedIssues'), Literal(closed, datatype=XSD.int)))

        for issue in repo_issues:
            temp_string = combine_string('issue', str(issue['issue_id']))
            temp_string = combine_string(repo_user_name, temp_string)

            graph.add((make_uri('repository', repo_user_name), make_uri('property', 'hasIssue'), make_uri('repository', temp_string)))

            graph.add((make_uri('repository', temp_string), DCTERMS.title, Literal(issue['issue_title'])))
            graph.add((make_uri('repository', temp_string), FABIO.hasUrl, Literal(issue['issue_url'])))
            graph.add((make_uri('repository', temp_string), make_uri('property', 'issueState'), make_uri('status', issue['issue_state'])))

            graph.add((make_uri('repository', temp_string), DCTERMS.created, Literal(issue['issue_created_at'], datatype=XSD.date)))
            
            if issue['issue_comments_count'] != 0:
                graph.add((make_uri('repository', temp_string), make_uri('property', 'hasTotalComments'), Literal(issue['issue_comments_count'], datatype=XSD.int)))

            make_repo_issue_labels(temp_string, issue['issue_labels'], graph)
            make_repo_issue_author(temp_string, issue['issue_author'], issue['issue_author_type'], issue['issue_author_url'], graph)



def make_repo_issue_labels(temp_string, repo_issue_labels, graph):
    if repo_issue_labels:
        
        count = 1
        for issue_label in repo_issue_labels:
            temp_string_new = combine_string(temp_string, str(count))

            graph.add((make_uri('repository', temp_string), make_uri('property', 'hasIssueLabelReference'), make_uri('issue_label_reference', temp_string_new)))
            graph.add((make_uri('issue_label_reference', temp_string_new), make_uri('property', 'hasIssueLabelName'), make_uri('label_name', parse_string(issue_label['label_name']))))
            graph.add((make_uri('issue_label_reference', temp_string_new), make_uri('property', 'hasIssueLabelDescription'), Literal(issue_label['label_description'])))
            
            count+=1



def make_repo_issue_author(temp_string, repo_issue_author, repo_issue_author_type, repo_issue_author_url, graph):
    if repo_issue_author_type == 'User':
        graph.add((make_uri('person', repo_issue_author), RDF.type,  make_uri('_class', 'person')))
        graph.add((make_uri('person', repo_issue_author), make_uri('property', 'hasPersonType'), make_uri('_class', 'issueauthor')))
        graph.add((make_uri('person', repo_issue_author), FABIO.hasUrl,  URIRef(repo_issue_author_url)))
        graph.add((make_uri('person', repo_issue_author), FOAF.accountName, Literal(repo_issue_author)))

        graph.add((make_uri('repository', temp_string), make_uri('property', 'hasIssueAuthor'),  make_uri('person', repo_issue_author)))

    elif repo_issue_author_type == 'Bot':
        graph.add((make_uri('bot', repo_issue_author), RDF.type,  make_uri('_class', 'bot')))
        graph.add((make_uri('bot', repo_issue_author), make_uri('property', 'hasBotType'), make_uri('_class', 'issueauthor')))
        graph.add((make_uri('bot', repo_issue_author), FABIO.hasUrl,  URIRef(repo_issue_author_url)))
        graph.add((make_uri('bot', repo_issue_author), FOAF.accountName, Literal(repo_issue_author)))

        graph.add((make_uri('repository', temp_string), make_uri('property', 'hasIssueAuthor'),  make_uri('bot', repo_issue_author)))