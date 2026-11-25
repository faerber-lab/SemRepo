import ast

def format_issue_labels(labels_lst):
    all_labels = []

    for l_lst in labels_lst:
        all_labels.append({
            "label_name": l_lst['name'],
            "label_description": l_lst['description']
        })

    return all_labels


def format_issue_assigned_to(assignees_lst):
    all_assignees = []

    for a_lst in assignees_lst:
        all_assignees.append({
            "assignee_name": a_lst['login'],
            "assignee_url": a_lst['html_url'],
            'assignee_type': a_lst['type']
        })

    return all_assignees


def format_issue_reaction(reaction_lst):
    del reaction_lst['url']

    return reaction_lst