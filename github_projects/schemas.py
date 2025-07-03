from typing import Any
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from github_projects.utils.datetime_utils import parse_datetime_flexible, ensure_timezone_aware


class Iteration(BaseModel):
    id: str
    title: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    duration: int | None = None

    @classmethod
    def from_gh_json(cls, gh_json: dict) -> "Iteration":
        start_date = parse_datetime_flexible(gh_json.get("startDate"))
        end_date = parse_datetime_flexible(gh_json.get("endDate"))
        duration = gh_json.get("duration")
        
        # fill in missing values if we can
        if start_date and end_date and not duration:
            duration = (end_date - start_date).days
        if start_date and duration and not end_date:
            end_date = start_date + timedelta(days=duration)
        
        # build and return the iteration object
        return cls(
            id=gh_json["id"],
            title=gh_json.get("title"),
            start_date=start_date,
            end_date=end_date,
            duration=duration
        )

class User(BaseModel):
    login: str
    url: str

class Label(BaseModel):
    name: str
    color: str

class Repo(BaseModel):
    name_with_owner: str
    url: str

class Issue(BaseModel):
    id: str
    title: str
    url: str
    state: str
    body: str
    createdAt: datetime
    updatedAt: datetime
    closedAt: datetime | None
    author: User
    assignees: list[User]
    labels: list[Label]
    repo: Repo
    iteration: Iteration | None
    parent: Any | None

    @classmethod
    def from_gh_json(cls, gh_json: dict) -> "Issue":
        iteration = None
        # get iteration from fieldValues
        for fv in gh_json["fieldValues"]["nodes"]:
            if fv.get("field", {}).get("name") == "Iteration":
                iteration = Iteration(id=fv["iterationId"])
                break
        parent = cls.from_gh_json(gh_json.get("parent", {})) if gh_json.get("parent") else None
        content = gh_json["content"]
        
        # Parse datetimes with flexible parsing
        createdAt = parse_datetime_flexible(content["createdAt"])
        updatedAt = parse_datetime_flexible(content["updatedAt"])
        closedAt = parse_datetime_flexible(content.get("closedAt"))
        
        # Ensure required fields are present
        if not createdAt or not updatedAt:
            raise ValueError("createdAt and updatedAt are required fields")
        
        return cls(
            id=content["id"],
            title=content["title"],
            url=content["url"],
            state=content["state"],
            body=content["body"],
            createdAt=createdAt,
            updatedAt=updatedAt,
            closedAt=closedAt,
            author=User(**content["author"]),
            assignees=[User(**assignee) for assignee in content["assignees"]["nodes"]],
            labels=[Label(**label) for label in content["labels"]["nodes"]],
            repo=Repo(
                name_with_owner=content["repository"]["nameWithOwner"],
                url=content["repository"]["url"]
            ),
            iteration=iteration,
            parent=parent,
        )

class PullRequest(BaseModel):
    id: str
    number: int
    title: str
    url: str
    state: str  # OPEN, CLOSED, MERGED
    body: str | None
    createdAt: datetime
    updatedAt: datetime
    closedAt: datetime | None
    mergedAt: datetime | None
    merged: bool
    author: dict | None
    assignees: list[dict]
    labels: list[dict]
    repo: dict
    baseRefName: str
    headRefName: str
    additions: int
    deletions: int
    changedFiles: int
    reviews: list[dict]
    iteration: dict | None = None

    @classmethod
    def from_gh_json(cls, node: dict) -> "PullRequest":
        content = node.get("content", {})
        
        # Extract iteration info from fieldValues
        iteration = None
        field_values = node.get("fieldValues", {}).get("nodes", [])
        for field_value in field_values:
            if field_value.get("iterationId"):
                iteration = {
                    "id": field_value.get("iterationId"),
                    "title": None,  # You might want to add this
                    "start_date": None,
                    "end_date": None,
                    "duration": None
                }
                break
        
        # Parse datetimes with flexible parsing
        createdAt = parse_datetime_flexible(content.get("createdAt"))
        updatedAt = parse_datetime_flexible(content.get("updatedAt"))
        closedAt = parse_datetime_flexible(content.get("closedAt"))
        mergedAt = parse_datetime_flexible(content.get("mergedAt"))
        
        # Ensure required fields are present
        if not createdAt or not updatedAt:
            raise ValueError("createdAt and updatedAt are required fields")
        
        return cls(
            id=str(content.get("id", "")),
            number=int(content.get("number", 0)),
            title=str(content.get("title", "")),
            url=str(content.get("url", "")),
            state=str(content.get("state", "")),
            body=content.get("body"),
            createdAt=createdAt,
            updatedAt=updatedAt,
            closedAt=closedAt,
            mergedAt=mergedAt,
            merged=bool(content.get("merged", False)),
            author=content.get("author"),
            assignees=[assignee for assignee in content.get("assignees", {}).get("nodes", [])],
            labels=[label for label in content.get("labels", {}).get("nodes", [])],
            repo={
                "name_with_owner": content.get("repository", {}).get("nameWithOwner"),
                "url": content.get("repository", {}).get("url")
            },
            baseRefName=str(content.get("baseRefName", "")),
            headRefName=str(content.get("headRefName", "")),
            additions=int(content.get("additions", 0)),
            deletions=int(content.get("deletions", 0)),
            changedFiles=int(content.get("changedFiles", 0)),
            reviews=[review for review in content.get("reviews", {}).get("nodes", [])],
            iteration=iteration
        )

    @classmethod
    def from_gh_json_direct(cls, node: dict) -> "PullRequest":
        """Create PullRequest from direct repository GraphQL response (not wrapped in content)"""
        # Parse datetimes with flexible parsing
        createdAt = parse_datetime_flexible(node.get("createdAt"))
        updatedAt = parse_datetime_flexible(node.get("updatedAt"))
        closedAt = parse_datetime_flexible(node.get("closedAt"))
        mergedAt = parse_datetime_flexible(node.get("mergedAt"))
        
        # Ensure required fields are present
        if not createdAt or not updatedAt:
            raise ValueError("createdAt and updatedAt are required fields")
        
        return cls(
            id=str(node.get("id", "")),
            number=int(node.get("number", 0)),
            title=str(node.get("title", "")),
            url=str(node.get("url", "")),
            state=str(node.get("state", "")),
            body=node.get("body"),
            createdAt=createdAt,
            updatedAt=updatedAt,
            closedAt=closedAt,
            mergedAt=mergedAt,
            merged=bool(node.get("merged", False)),
            author=node.get("author"),
            assignees=[assignee for assignee in node.get("assignees", {}).get("nodes", [])],
            labels=[label for label in node.get("labels", {}).get("nodes", [])],
            repo={
                "name_with_owner": node.get("repository", {}).get("nameWithOwner"),
                "url": node.get("repository", {}).get("url")
            },
            baseRefName=str(node.get("baseRefName", "")),
            headRefName=str(node.get("headRefName", "")),
            additions=int(node.get("additions", 0)),
            deletions=int(node.get("deletions", 0)),
            changedFiles=int(node.get("changedFiles", 0)),
            reviews=[review for review in node.get("reviews", {}).get("nodes", [])],
            iteration=None  # No iteration data available from direct repo queries
        )

# API schemas
class ProjectID(BaseModel):
    """Request schema for getting basic project information."""
    organization: str = Field(
        ...,
        description="The name of the organization, for example 'aurelio-labs'."
    )
    project_number: int = Field(
        ...,
        description=(
            "The number of the project. This can be found in the URL of the project "
            "page, for example 'https://github.com/orgs/aurelio-labs/projects/1' uses "
            "project number 1."
        )
    )

class RepoFilter(ProjectID):
    """Request schema for filtering repo item."""
    title: str | None = Field(
        None,
        description="The title of the item, for example 'Fix bug'. Uses regex to match.",
        examples=[
            "Fix bug",
            "\[EPIC\].*",
        ]
    )
    state: str | None = Field(
        None,
        description="The state of the item, for example 'OPEN' or 'CLOSED'."
    )
    iteration_id: str | None = Field(
        None,
        description="The iteration ID, for example '9e342e9b'."
    )
    updated_after: datetime | None = Field(
        None,
        description="The date and time after which the item was updated.",
        examples=[
            "2025-01-01",
            "2025-01-01",
        ]
    )
    updated_before: datetime | None = Field(
        None,
        description="The date and time before which the item was updated.",
        examples=[
            "2025-01-01",
            "2025-01-01",
        ]
    )

class PRFilter(ProjectID):
    title: str | None = Field(
        None,
        description="The title of the item, for example 'Fix bug'. Uses regex to match.",
    )
    iteration_id: str | None = Field(
        None,
        description="The iteration ID, for example '9e342e9b'."
    )
    state: str | None = Field(
        None, description="The state of the item, for example 'OPEN' or 'CLOSED'."
    )
    merged_after: datetime | None = Field(
        None,
        description="The date and time after which the item was merged.",
    )
    merged_before: datetime | None = Field(
        None,
        description="The date and time before which the item was merged.",
    )
    updated_after: datetime | None = Field(
        None,
        description="The date and time after which the item was updated.",
    )
    updated_before: datetime | None = Field(
        None,
        description="The date and time before which the item was updated.",
    )
    author: str | None = Field(
        None,
        description="The author of the item, for example 'jamescalam'."
    )
    merged_only: bool = Field(
        False,
        description="Only return merged PRs."
    )

class RepoPRFilter(BaseModel):
    owner: str = Field(
        ...,
        description="The organization name, for example 'aurelio-labs'."
    )
    name: str = Field(
        ..., 
        description="The repository name, for example 'semantic-router'."
    )
    title: str | None = Field(
        None,
        description="The title of the PR, for example 'Fix bug'. Uses regex to match.",
    )
    state: str | None = Field(
        None, 
        description="The state of the PR, for example 'OPEN', 'CLOSED', or 'MERGED'."
    )
    merged_after: datetime | None = Field(
        None,
        description="The date and time after which the PR was merged.",
    )
    merged_before: datetime | None = Field(
        None,
        description="The date and time before which the PR was merged.",
    )
    updated_after: datetime | None = Field(
        None,
        description="The date and time after which the PR was updated.",
    )
    updated_before: datetime | None = Field(
        None,
        description="The date and time before which the PR was updated.",
    )
    created_after: datetime | None = Field(
        None,
        description="The date and time after which the PR was created.",
    )
    created_before: datetime | None = Field(
        None,
        description="The date and time before which the PR was created.",
    )
    author: str | None = Field(
        None,
        description="The author of the PR, for example 'jamescalam'."
    )
    merged_only: bool = Field(
        False,
        description="Only return merged PRs."
    )
    base_ref: str | None = Field(
        None,
        description="Filter by base branch, for example 'main' or 'dev'."
    )

class PRAnalyticsRequest(RepoPRFilter):
    """Request model for PR analytics report generation"""
    report_title: str = Field(
        default="Pull Request Analytics Report",
        description="Title for the analytics report"
    )
    merged_after: datetime = Field(
        default=datetime.now() - timedelta(days=30),
        description="The date and time after which the PR was merged.",
    )
    merged_before: datetime = Field(
        default=datetime.now(),
        description="The date and time before which the PR was merged.",
    )