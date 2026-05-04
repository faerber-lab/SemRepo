## Reproducibility and Sustainability of Research Software - Use Case

### Overview
Reproducibility in computational research depends not only on the availability of code, but also on whether repositories remain maintained and usable over time, which is closely tied to software sustainability. SemRepo enables large-scale auditing by linking publications to GitHub repositories and exposing signals such as issues, commits, contributors, stars, and forks in a unified graph, allowing systematic detection of inactive or weakly maintained software without ad hoc API queries or manual inspection.

### Methodology
we conduct a reproducibility-auditing study on 20,000 research repositories from SemRepo, linked through LPWC. We operationalize sustainability using maintenance, activity, and community uptake signals computed via SPARQL queries.
Prior work identifies key indicators of repository health, including development activity (commits), community engagement (contributors), and maintenance responsiveness (issue resolution). We compute three groups of indicators per repository:

- *Issue Closure Rate*: proportion of closed issues, proxying maintenance responsiveness.  
- *Activity Indicators*: commits and contributors, capturing development intensity and continuity~\cite{Chelkowski2016InequalitiesOSS,Linaker2026OSSHealth}.  
- *Popularity Metrics*: stars and forks, reflecting community uptake and visibility.

We provide all resources for this use case: the [20k subset dataset](./semrepo-20k.csv) and the [source code](./reproducibility-auditing.ipynb).

The following is SPARQL code to harvest the 20k subset dataset directly from the SPARQL endpoint:
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX fabio: <http://purl.org/spar/fabio/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX sr: <https://semrepo.org/property/>
PREFIX srclass: <https://semrepo.org/class/>

SELECT
  ?repoEntity
  ?githubUrl
  ?lpwcRepo
  ?created

  # Adoption
  ?stars
  ?forks
  ?watchers

  # Issues
  ?issues
  ?openIssues
  ?closedIssues
  ?comments

  # Community
  ?contributors

  # Language
  ?primaryLanguage
  ?topic

  (SUM(?commits) AS ?total_commits)

WHERE {
  GRAPH <https://semrepo.org> {

    ?repoEntity rdf:type srclass:repository ;
                fabio:hasURL ?githubUrl .

    OPTIONAL { ?repoEntity sr:hasLpwcUrl ?lpwcRepo . }
    OPTIONAL { ?repoEntity dct:created ?created . }

    OPTIONAL { ?repoEntity sr:hasTotalStargazers ?stars . }
    OPTIONAL { ?repoEntity sr:hasTotalForks ?forks . }
    OPTIONAL { ?repoEntity sr:hasTotalWatchers ?watchers . }

    OPTIONAL { ?repoEntity sr:hasTotalIssues ?issues . }
    OPTIONAL { ?repoEntity sr:hasTotalOpenIssues ?openIssues . }
    OPTIONAL { ?repoEntity sr:hasTotalClosedIssues ?closedIssues . }
    OPTIONAL { ?repoEntity sr:hasTotalComments ?comments . }

    OPTIONAL { ?repoEntity sr:hasTotalContributor ?contributors . }

    OPTIONAL {
      ?repoEntity sr:hasPrimaryProgrammingLanguage ?lang .
      ?lang sr:hasLanguageName ?primaryLanguage .
    }

    OPTIONAL { ?repoEntity foaf:topic ?topic . }

    OPTIONAL {
      ?repoEntity sr:hasContributorReference ?contRef .
      ?contRef sr:hasCommits ?commits .
    }

  }
}

GROUP BY
  ?repoEntity ?githubUrl ?lpwcRepo ?created
  ?stars ?forks ?watchers
  ?issues ?openIssues ?closedIssues ?comments
  ?contributors
  ?primaryLanguage ?topic

ORDER BY DESC(?total_commits)
LIMIT 20000
```
