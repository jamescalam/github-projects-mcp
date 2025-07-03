import os
#from github_projects.auth import verify_github_token
from github_projects.schemas import ProjectID, RepoFilter, Issue, Iteration, PullRequest, PRFilter, RepoPRFilter, PRAnalyticsRequest
from fastmcp import FastMCP, Context
from fastapi import HTTPException, status
import httpx
from github_projects import ql
import re
import sys
from github_projects.report import PRAnalyzer, HTMLReportGenerator, get_repo_prs_direct

mcp: FastMCP = FastMCP("github-projects")

GH_API_URL = "https://api.github.com/graphql"
PAT = os.environ["GITHUB_PAT"]


@mcp.tool()
async def generate_pr_analytics_report(
    request: PRAnalyticsRequest,
    ctx: Context,
) -> str:
    """
    Generate an HTML analytics report from Pull Request data.
    
    This tool analyzes pull request data and generates a comprehensive HTML report
    with interactive charts, contributor analysis, and development insights.
    
    Args:
        request: PRAnalyticsRequest containing:
            - owner: The owner of the repository
            - name: The name of the repository
            - report_title: Report title (optional)
            - merged_after: Analysis start date (optional)
            - merged_before: Analysis end date (optional)
    
    Returns:
        Complete HTML report as a string
    """
    
    await ctx.info(f"Generating analytics report: '{request.report_title}'")
    prs = await get_repo_prs_direct(
        pr_filter=request,
        ctx=ctx,
        PAT=PAT,
        GH_API_URL=GH_API_URL
    )
    await ctx.info(f"Analyzing {len(prs)} pull requests")
    await ctx.info("Analyzing pull request data...")
    analyzer = PRAnalyzer(prs)
    analytics_data = analyzer.analyze_time_period(
        start_date=request.merged_after,
        end_date=request.merged_before
    )
    try:
        # Log some analysis results
        stats = analytics_data.total_stats
        await ctx.info(f"Analysis complete:")
        await ctx.info(f"  - Total PRs analyzed: {stats['total_prs']}")
        await ctx.info(f"  - Lines added: {stats['total_additions']:,}")
        await ctx.info(f"  - Lines deleted: {stats['total_deletions']:,}")
        await ctx.info(f"  - Net change: {stats['net_change']:,}")
        await ctx.info(f"  - Active contributors: {stats['active_contributors']}")
        
        # Generate HTML report
        await ctx.info("Generating HTML report...")
        generator = HTMLReportGenerator(analytics_data)
        html_report = generator.generate_report(request.report_title)
        
        await ctx.info("Analytics report generated successfully!")
        await ctx.info(f"Report contains {len(html_report)} characters")
        
        return html_report
        
    except ValueError as e:
        await ctx.error(f"Validation error: {str(e)}")
        raise e
    except Exception as e:
        await ctx.error(f"Failed to generate analytics report: {str(e)}")
        raise e

@mcp.tool()
async def get_project_details(
    project_request: ProjectID,
    #token: Annotated[str, Depends(verify_github_token)],
    ctx: Context,
):
    """
    Get project details from GitHub using the provided Personal Access Token.
    
    The PAT should be provided in the Authorization header as: `Bearer your_token_here`
    """
    # Now you have access to both the project request data and the verified token
    # You can use the token to make authenticated requests to GitHub's API
    await ctx.info(f"Getting project details for {project_request.organization}/{project_request.project_number}")
    variables = {
        "org": project_request.organization,
        "number": project_request.project_number
    }

    if not PAT:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No GitHub Personal Access Token provided, this must be set via `GITHUB_PAT`"
        )
    
    headers = {
        "Authorization": f"Bearer {PAT}",
        "Accept": "application/vnd.github+json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GH_API_URL,
                json={"query": ql.get_project_details, "variables": variables},
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
        
        # Check for GraphQL errors
        if "errors" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"GitHub API error: {result['errors']}"
            )
        
        return result["data"]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch project data from GitHub: {str(e)}"
        )


@mcp.tool()
async def get_repo_issues(
    #token: Annotated[str, Depends(verify_github_token)],
    repo_filter: RepoFilter,
    ctx: Context,
) -> list[Issue]:
    await ctx.info(f"Getting issues for {repo_filter.organization}/{repo_filter.project_number}")
    variables = {
        "org": repo_filter.organization,
        "number": repo_filter.project_number,
        "after": None
    }

    if not PAT:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No GitHub Personal Access Token provided, this must be set via `GITHUB_PAT`"
        )

    headers = {
        "Authorization": f"Bearer {PAT}",
        "Accept": "application/vnd.github+json"
    }
    tasks: list[Issue] = []

    while True:
        print(f"On page {variables['after']}")

        headers = {
            "Authorization": f"Bearer {PAT}",
            "Accept": "application/vnd.github+json"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GH_API_URL,
                json={"query": ql.get_tasks, "variables": variables},
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
        
        # get all graph nodes
        nodes = result["data"]["organization"]["projectV2"]["items"]["nodes"]
        for node in nodes:
            if node.get("content", {}):
                valid_task = True
                task = Issue.from_gh_json(node)
                if repo_filter.title:
                    if not re.match(repo_filter.title, task.title):
                        valid_task = False
                if repo_filter.iteration_id:
                    if not (
                        task.iteration  # confirm task has an iteration
                        and task.iteration.id == repo_filter.iteration_id  # check iteration matches
                    ):
                        # if we got here, the task is not valid with this filter
                        valid_task = False
                if repo_filter.state and (task.state != repo_filter.state):
                    valid_task = False
                if repo_filter.updated_after and (task.updatedAt < repo_filter.updated_after):
                    valid_task = False
                if repo_filter.updated_before and (task.updatedAt > repo_filter.updated_before):
                    valid_task = False
                # TODO other filter conditions to go here
                if valid_task:
                    tasks.append(task)
        if result["data"]["organization"]["projectV2"]["items"]["pageInfo"]["hasNextPage"]:
            variables["after"] = result["data"]["organization"]["projectV2"]["items"]["pageInfo"]["endCursor"]
        else:
            break

    return tasks


@mcp.tool()
async def get_project_iterations(
    #token: Annotated[str, Depends(verify_github_token)],
    project: ProjectID,
    ctx: Context,
) -> list[Iteration]:
    """Endpoint for getting all current and future iterations for a project. This is
    a shallow endpoint and does not include past iterations.
    """
    await ctx.info(f"Getting iterations for {project.organization}/{project.project_number}")
    variables = {
        "org": project.organization,
        "number": project.project_number
    }

    if not PAT:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No GitHub Personal Access Token provided, this must be set via `GITHUB_PAT`"
        )

    headers = {
        "Authorization": f"Bearer {PAT}",
        "Accept": "application/vnd.github+json"
    }
    iterations: list[Iteration] = []
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GH_API_URL,
            json={"query": ql.get_iterations, "variables": variables},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
    
    # parse response into list of Iteration objects
    for node in result["data"]["organization"]["projectV2"]["fields"]["nodes"]:
        if node.get("name") == "Iteration":
            # this contains all of our iteration info for the project
            for iteration in node["configuration"]["iterations"]:
                iterations.append(Iteration.from_gh_json(iteration))
    return iterations


@mcp.tool()
async def get_repo_prs(
    pr_filter: RepoPRFilter,
    ctx: Context,
) -> list[PullRequest]:
    return await get_repo_prs_direct(
        pr_filter=pr_filter, 
        ctx=ctx, 
        PAT=PAT, 
        GH_API_URL=GH_API_URL
    )

if __name__ == "__main__":
    try:
        print("Starting MCP server...", file=sys.stderr)
        mcp.run(transport="stdio")
    except Exception as e:
        print(f"MCP server failed to start: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
