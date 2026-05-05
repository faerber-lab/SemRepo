## Reproducibility and Sustainability of Research Software — Use Case

### Overview
Reproducibility in computational research depends not just on code availability, but on whether repositories remain maintained and usable over time. This is closely tied to _software sustainability_. SemRepo enables large-scale auditing by linking publications to GitHub repositories and exposing signals such as issues, commits, contributors, stars, and forks in a unified graph, supporting systematic detection of inactive or weakly maintained research software.

### Methodology
We analyze 20,000 research-linked repositories from SemRepo. Following prior work [[1]](https://link.springer.com/article/10.1007/s10664-026-10846-y), we define key indicators of repository health: development activity (commits), community engagement (contributors), and maintenance responsiveness (issue resolution).

Using the SemRepo SPARQL endpoint, we compute three indicator groups per repository:

- *Issue Closure Rate*: proportion of closed issues, indicating maintenance responsiveness  
- *Activity Indicators*: commits and contributors, capturing development intensity and continuity [[1](https://link.springer.com/article/10.1007/s10664-026-10846-y), [2](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0152976)]  
- *Popularity Metrics*: stars and forks, reflecting community uptake and visibility  

The SPARQL queries below extract the 20k subset and compute these health indicators:
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

### Results and Analysis
Our analysis (see [source code](./reproducibility-auditing.ipynb)) highlights significant heterogeneity in repository quality. Specifically, 46.4% of repositories fall into the high-risk (non-reproducible) category, 26.9% into medium risk, and only 26.6% into low risk. Additionally, 8.3% show extremely low activity, suggesting likely abandonment. Overall, these findings indicate that a substantial share of research software is poorly maintained, raising serious concerns about long-term usability and reproducibility. Further details are provided in the paper.

[1] Linåker, J., Olsson, T. & Papatheocharous, E. _Assessing open source software health in organizations’ intake processes: A qualitative study on the practitioners’ perspective_. Empir Software Eng 31, 105 (2026). https://doi.org/10.1007/s10664-026-10846-y

[2] Chełkowski, T., Gloor, P.A., Jemielniak, D.: _Inequalities in open source software development: Analysis of contributor’s commits in apache software foundation projects_. PLOS ONE 11(4), e0152976 (2016). https://doi.org/10.1371/journal.pone.0152976 
