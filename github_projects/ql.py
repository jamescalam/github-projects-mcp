get_project_details = """
query($org: String!, $number: Int!) {
  organization(login: $org) {
    projectV2(number: $number) {
      id
      title
      number
      url
      fields(first: 20) {
        nodes {
          ... on ProjectV2Field {
            id
            name
            dataType
          }
          ... on ProjectV2IterationField {
            id
            name
            configuration {
              iterations {
                startDate
                id
                title
              }
            }
          }
          ... on ProjectV2SingleSelectField {
            id
            name
            options {
              id
              name
            }
          }
        }
      }
      items(first: 10) {
        nodes {
          id
          content {
            ... on Issue {
              id
              title
              url
            }
            ... on PullRequest {
              id
              title
              url
            }
          }
        }
      }
    }
  }
}
"""

# graphql query for getting all iterations for a project
get_iterations = """
query($org: String!, $number: Int!) {
  organization(login: $org) {
    projectV2(number: $number) {
      fields(first: 20) {
        nodes {
          ... on ProjectV2IterationField {
            id
            name
            configuration {
              iterations {
                id
                title
                startDate
                duration
              }
            }
          }
        }
      }
    }
  }
}
"""

# graphql query for getting tasks
get_tasks = """
query($org: String!, $number: Int!, $after: String) {
  organization(login: $org) {
    projectV2(number: $number) {
      items(first: 100, after: $after) {
        nodes {
          content {
            ... on Issue {
              id
              number
              title
              url
              state
              body
              createdAt
              updatedAt
              closedAt
              author {
                login
                url
              }
              assignees(first: 10) {
                nodes {
                  login
                  url
                }
              }
              labels(first: 10) {
                nodes {
                  name
                  color
                }
              }
              repository {
                nameWithOwner
                url
              }
            }
          }
          fieldValues(first: 20) {
            nodes {
              ... on ProjectV2ItemFieldIterationValue {
                iterationId
                field {
                  ... on ProjectV2IterationField {
                    id
                    name
                  }
                }
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""

# graphql query for getting PRs
get_prs = """
query($org: String!, $number: Int!, $after: String) {
  organization(login: $org) {
    projectV2(number: $number) {
      items(first: 100, after: $after) {
        nodes {
          content {
            ... on PullRequest {
              id
              number
              title
              url
              state
              body
              createdAt
              updatedAt
              closedAt
              mergedAt
              merged
              mergeable
              author {
                login
                url
              }
              assignees(first: 10) {
                nodes {
                  login
                  url
                }
              }
              labels(first: 10) {
                nodes {
                  name
                  color
                }
              }
              repository {
                nameWithOwner
                url
              }
              baseRefName
              headRefName
              additions
              deletions
              changedFiles
              reviews(first: 10) {
                nodes {
                  state
                  author {
                    login
                  }
                }
              }
            }
          }
          fieldValues(first: 20) {
            nodes {
              ... on ProjectV2ItemFieldIterationValue {
                iterationId
                field {
                  ... on ProjectV2IterationField {
                    id
                    name
                  }
                }
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""

# GraphQL query for getting PRs directly from repository
get_repo_prs_direct = """
query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(
      first: 100, 
      after: $after, 
      states: [MERGED, CLOSED, OPEN], 
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      nodes {
        id
        number
        title
        url
        state
        body
        createdAt
        updatedAt
        closedAt
        mergedAt
        merged
        mergeable
        author {
          login
          url
        }
        assignees(first: 10) {
          nodes {
            login
            url
          }
        }
        labels(first: 10) {
          nodes {
            name
            color
          }
        }
        repository {
          nameWithOwner
          url
        }
        baseRefName
        headRefName
        additions
        deletions
        changedFiles
        reviews(first: 10) {
          nodes {
            state
            author {
              login
            }
          }
        }
        commits(first: 1) {
          nodes {
            commit {
              authoredDate
              message
            }
          }
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
"""