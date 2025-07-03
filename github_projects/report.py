from datetime import datetime
import re
import httpx
from typing import Any
from collections import defaultdict
from fastapi import HTTPException, status
from fastmcp import Context
from pydantic import BaseModel
from github_projects.schemas import RepoPRFilter, PullRequest
from github_projects.utils.datetime_utils import normalize_datetime_for_comparison, ensure_timezone_aware
from github_projects import ql

async def get_repo_prs_direct(
    pr_filter: RepoPRFilter,
    ctx: Context,
    PAT: str,
    GH_API_URL: str,
) -> list[PullRequest]:
    await ctx.info(f"Getting PRs for {pr_filter.owner}/{pr_filter.name}")
    variables = {
        "owner": pr_filter.owner,
        "name": pr_filter.name,
        "after": None,
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
    prs: list[PullRequest] = []

    while True:
        print(f"On page {variables['after']}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                GH_API_URL,
                json={"query": ql.get_repo_prs_direct, "variables": variables},
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
        
        # Check for errors
        if "errors" in result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"GraphQL errors: {result['errors']}"
            )
        
        # Get all PR nodes
        nodes = result["data"]["repository"]["pullRequests"]["nodes"]
        for node in nodes:
            valid_pr = True
            pr = PullRequest.from_gh_json_direct(node)
            
            # Apply filters (same filtering logic as before)
            if pr_filter.title:
                if not re.match(pr_filter.title, pr.title):
                    valid_pr = False
                    
            if pr_filter.state and (pr.state != pr_filter.state):
                valid_pr = False
                
            if pr_filter.merged_only and not pr.merged:
                valid_pr = False
                
            if pr_filter.merged_after:
                normalized_merged_at = normalize_datetime_for_comparison(pr.mergedAt)
                normalized_merged_after = normalize_datetime_for_comparison(pr_filter.merged_after)
                if not pr.mergedAt or (normalized_merged_at and normalized_merged_after and normalized_merged_at < normalized_merged_after):
                    valid_pr = False
                
            if pr_filter.merged_before:
                normalized_merged_at = normalize_datetime_for_comparison(pr.mergedAt)
                normalized_merged_before = normalize_datetime_for_comparison(pr_filter.merged_before)
                if not pr.mergedAt or (normalized_merged_at and normalized_merged_before and normalized_merged_at > normalized_merged_before):
                    valid_pr = False
                
            if pr_filter.updated_after:
                normalized_updated_at = normalize_datetime_for_comparison(pr.updatedAt)
                normalized_updated_after = normalize_datetime_for_comparison(pr_filter.updated_after)
                if normalized_updated_at and normalized_updated_after and normalized_updated_at < normalized_updated_after:
                    valid_pr = False
                
            if pr_filter.updated_before:
                normalized_updated_at = normalize_datetime_for_comparison(pr.updatedAt)
                normalized_updated_before = normalize_datetime_for_comparison(pr_filter.updated_before)
                if normalized_updated_at and normalized_updated_before and normalized_updated_at > normalized_updated_before:
                    valid_pr = False
                
            if pr_filter.created_after:
                normalized_created_at = normalize_datetime_for_comparison(pr.createdAt)
                normalized_created_after = normalize_datetime_for_comparison(pr_filter.created_after)
                if normalized_created_at and normalized_created_after and normalized_created_at < normalized_created_after:
                    valid_pr = False
                
            if pr_filter.created_before:
                normalized_created_at = normalize_datetime_for_comparison(pr.createdAt)
                normalized_created_before = normalize_datetime_for_comparison(pr_filter.created_before)
                if normalized_created_at and normalized_created_before and normalized_created_at > normalized_created_before:
                    valid_pr = False
                
            if pr_filter.author and (not pr.author or pr.author.get("login") != pr_filter.author):
                valid_pr = False
                
            if pr_filter.base_ref and (pr.baseRefName != pr_filter.base_ref):
                valid_pr = False

            if valid_pr:
                prs.append(pr)
                
        if result["data"]["repository"]["pullRequests"]["pageInfo"]["hasNextPage"]:
            variables["after"] = result["data"]["repository"]["pullRequests"]["pageInfo"]["endCursor"]
        else:
            break
    return prs

class AnalyticsData(BaseModel):
    """Container for processed analytics data"""
    daily_stats: list[dict[str, Any]]
    contributor_analysis: dict[str, dict[str, Any]]
    pr_type_analysis: dict[str, int]
    total_stats: dict[str, Any]
    time_period: dict[str, datetime | None]

class PRAnalyzer:
    """Analyzes pull request data and generates insights"""
    
    def __init__(self, pull_requests: list[Any]):
        self.pull_requests = pull_requests
        
    def analyze_time_period(self, start_date: datetime | None = None, 
                          end_date: datetime | None = None) -> AnalyticsData:
        """Analyze PRs within a specific time period"""
        
        # Filter PRs by date range if specified
        filtered_prs = self._filter_prs_by_date(start_date, end_date)
        
        if not filtered_prs:
            raise ValueError("No pull requests found in the specified time period")
        
        # Determine actual time period from data
        time_period = self._get_time_period(filtered_prs)
        
        return AnalyticsData(
            daily_stats=self._calculate_daily_stats(filtered_prs),
            contributor_analysis=self._analyze_contributors(filtered_prs),
            pr_type_analysis=self._analyze_pr_types(filtered_prs),
            total_stats=self._calculate_total_stats(filtered_prs),
            time_period=time_period
        )
    
    def _filter_prs_by_date(self, start_date: datetime | None, 
                           end_date: datetime | None) -> list[Any]:
        """Filter PRs by merge date within specified range"""
        filtered = []
        
        # Normalize filter dates for comparison
        start_dt = normalize_datetime_for_comparison(start_date)
        end_dt = normalize_datetime_for_comparison(end_date)
        
        for pr in self.pull_requests:
            if not pr.mergedAt:
                continue
                
            # Normalize PR merge date for comparison
            merge_date = normalize_datetime_for_comparison(pr.mergedAt)
            if not merge_date:
                continue
            
            if start_dt and merge_date < start_dt:
                continue
            if end_dt and merge_date > end_dt:
                continue
                
            filtered.append(pr)
        
        return filtered
    
    def _get_time_period(self, prs: list[Any]) -> dict[str, datetime]:
        """Get the actual time period covered by the PR data"""
        merge_dates = []
        for pr in prs:
            if pr.mergedAt:
                normalized_date = normalize_datetime_for_comparison(pr.mergedAt)
                if normalized_date:
                    merge_dates.append(normalized_date)
        
        if not merge_dates:
            now = ensure_timezone_aware(datetime.now())
            if now:
                return {"start": now, "end": now}
            else:
                # Fallback to naive datetime if timezone conversion fails
                return {"start": datetime.now(), "end": datetime.now()}
        
        start_date = min(merge_dates)
        end_date = max(merge_dates)
        
        return {
            "start": start_date,
            "end": end_date
        }
    
    def _calculate_daily_stats(self, prs: list[Any]) -> list[dict[str, Any]]:
        """Calculate daily statistics"""
        daily_data = defaultdict(lambda: {
            "additions": 0,
            "deletions": 0,
            "prs": 0,
            "net_change": 0,
            "authors": set(),
            "files_changed": 0
        })
        
        for pr in prs:
            if not pr.mergedAt:
                continue
                
            day_key = pr.mergedAt.strftime("%Y-%m-%d")
            day_data = daily_data[day_key]
            
            day_data["additions"] += pr.additions
            day_data["deletions"] += pr.deletions
            day_data["prs"] += 1
            day_data["net_change"] += (pr.additions - pr.deletions)
            day_data["files_changed"] += pr.changedFiles
            
            if pr.author and pr.author.get("login"):
                day_data["authors"].add(pr.author["login"])
        
        # Convert to list and add metadata
        daily_stats = []
        for date_str, data in sorted(daily_data.items()):
            daily_stats.append({
                "date": date_str,
                "additions": data["additions"],
                "deletions": data["deletions"],
                "prs": data["prs"],
                "net_change": data["net_change"],
                "files_changed": data["files_changed"],
                "author_count": len(data["authors"]),
                "authors": list(data["authors"])
            })
        
        return daily_stats
    
    def _analyze_contributors(self, prs: list[Any]) -> dict[str, dict[str, Any]]:
        """Analyze contributor statistics"""
        contributors = defaultdict(lambda: {
            "prs": 0,
            "additions": 0,
            "deletions": 0,
            "files_changed": 0,
            "first_contribution": None,
            "last_contribution": None
        })
        
        for pr in prs:
            if not pr.author or not pr.author.get("login"):
                continue
                
            author = pr.author["login"]
            contrib = contributors[author]
            
            contrib["prs"] += 1
            contrib["additions"] += pr.additions
            contrib["deletions"] += pr.deletions
            contrib["files_changed"] += pr.changedFiles
            
            if pr.mergedAt:
                normalized_merged_at = normalize_datetime_for_comparison(pr.mergedAt)
                if normalized_merged_at:
                    first_contrib = contrib["first_contribution"]
                    last_contrib = contrib["last_contribution"]
                    
                    if not first_contrib or (normalized_merged_at < normalize_datetime_for_comparison(first_contrib)):
                        contrib["first_contribution"] = pr.mergedAt
                    if not last_contrib or (normalized_merged_at > normalize_datetime_for_comparison(last_contrib)):
                        contrib["last_contribution"] = pr.mergedAt
        
        # Add calculated fields
        for author, stats in contributors.items():
            stats["net_change"] = stats["additions"] - stats["deletions"]
            stats["avg_additions_per_pr"] = stats["additions"] / stats["prs"] if stats["prs"] > 0 else 0
            stats["avg_deletions_per_pr"] = stats["deletions"] / stats["prs"] if stats["prs"] > 0 else 0
        
        return dict(contributors)
    
    def _analyze_pr_types(self, prs: list[Any]) -> dict[str, int]:
        """Analyze PR types based on title prefixes"""
        pr_types = defaultdict(int)
        
        for pr in prs:
            title = pr.title.lower() if pr.title else ""
            
            if title.startswith("feat"):
                pr_types["features"] += 1
            elif title.startswith("fix"):
                pr_types["fixes"] += 1
            elif title.startswith("refactor"):
                pr_types["refactors"] += 1
            elif title.startswith("chore"):
                pr_types["chores"] += 1
            elif title.startswith("docs"):
                pr_types["documentation"] += 1
            elif title.startswith("test"):
                pr_types["tests"] += 1
            else:
                pr_types["other"] += 1
        
        return dict(pr_types)
    
    def _calculate_total_stats(self, prs: list[Any]) -> dict[str, Any]:
        """Calculate overall statistics"""
        total_additions = sum(pr.additions for pr in prs)
        total_deletions = sum(pr.deletions for pr in prs)
        total_files = sum(pr.changedFiles for pr in prs)
        
        authors = set()
        for pr in prs:
            if pr.author and pr.author.get("login"):
                authors.add(pr.author["login"])
        
        return {
            "total_prs": len(prs),
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "net_change": total_additions - total_deletions,
            "total_files": total_files,
            "active_contributors": len(authors),
            "contributors": list(authors),
            "avg_additions_per_pr": total_additions / len(prs) if prs else 0,
            "avg_deletions_per_pr": total_deletions / len(prs) if prs else 0,
            "avg_files_per_pr": total_files / len(prs) if prs else 0
        }

class HTMLReportGenerator:
    """Generates HTML reports from analytics data"""
    
    def __init__(self, analytics_data: AnalyticsData):
        self.data = analytics_data
    
    def generate_report(self, title: str = "Pull Request Analytics Report") -> str:
        """Generate complete HTML report"""
        
        # Format time period
        start_date = self.data.time_period["start"].strftime("%B %d, %Y")
        end_date = self.data.time_period["end"].strftime("%B %d, %Y")
        period_str = f"{start_date} - {end_date}"
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    {self._get_styles()}
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 {title}</h1>
            <p>Development Activity Report - {period_str}</p>
        </div>
        
        {self._generate_stats_cards()}
        {self._generate_daily_chart_section()}
        {self._generate_contributor_charts()}
        {self._generate_contributor_table()}
        {self._generate_insights()}
    </div>
    
    {self._generate_javascript()}
</body>
</html>"""
        
        return html
    
    def _get_styles(self) -> str:
        """Get CSS styles for the report"""
        return """
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.1);
        }
        
        .header {
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        .header h1 {
            color: #2c3e50;
            margin: 0;
            font-size: 2.5em;
            font-weight: 700;
        }
        
        .header p {
            color: #7f8c8d;
            margin: 10px 0 0 0;
            font-size: 1.2em;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }
        
        .stat-number {
            font-size: 2.5em;
            font-weight: bold;
            margin: 0;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        
        .stat-label {
            font-size: 0.9em;
            opacity: 0.9;
            margin: 5px 0 0 0;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .chart-section {
            margin-bottom: 40px;
            background: #f8f9fa;
            padding: 25px;
            border-radius: 12px;
            border: 1px solid #e9ecef;
        }
        
        .chart-title {
            font-size: 1.5em;
            font-weight: 600;
            margin-bottom: 20px;
            color: #2c3e50;
            text-align: center;
        }
        
        .chart-container {
            position: relative;
            height: 400px;
            margin-bottom: 20px;
        }
        
        .chart-container.small {
            height: 300px;
        }
        
        .insights {
            background: #e8f4fd;
            border-left: 4px solid #3498db;
            padding: 20px;
            margin: 20px 0;
            border-radius: 0 8px 8px 0;
        }
        
        .insights h3 {
            margin: 0 0 10px 0;
            color: #2980b9;
        }
        
        .contributor-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        
        .contributor-table th,
        .contributor-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        
        .contributor-table th {
            background: #667eea;
            color: white;
            font-weight: 600;
        }
        
        .contributor-table tr:hover {
            background: #f5f5f5;
        }
        
        .trend-indicator {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: bold;
        }
        
        .trend-up {
            background: #d4edda;
            color: #155724;
        }
        
        .trend-down {
            background: #f8d7da;
            color: #721c24;
        }
        
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
    </style>"""
    
    def _generate_stats_cards(self) -> str:
        """Generate statistics cards section"""
        stats = self.data.total_stats
        
        return f"""
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{stats['total_prs']}</div>
                <div class="stat-label">PRs Merged</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['total_additions']:,}</div>
                <div class="stat-label">Lines Added</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['total_deletions']:,}</div>
                <div class="stat-label">Lines Deleted</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{'+'if stats['net_change'] >= 0 else ''}{stats['net_change']:,}</div>
                <div class="stat-label">Net Change</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['total_files']}</div>
                <div class="stat-label">Files Changed</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['active_contributors']}</div>
                <div class="stat-label">Active Contributors</div>
            </div>
        </div>"""
    
    def _generate_daily_chart_section(self) -> str:
        """Generate daily changes chart section"""
        # Find peak activity day
        peak_day = max(self.data.daily_stats, key=lambda x: x['additions']) if self.data.daily_stats else None
        peak_date = datetime.strptime(peak_day['date'], '%Y-%m-%d').strftime('%B %d') if peak_day else "N/A"
        
        insights = f"""
            <div class="insights">
                <h3>Key Insights:</h3>
                <ul>
                    <li><strong>Peak Activity Day:</strong> {peak_date} with {peak_day['additions']:,} lines added</li>
                    <li><strong>Daily Average:</strong> {self.data.total_stats['avg_additions_per_pr']:.0f} additions per PR</li>
                    <li><strong>Code Quality:</strong> {self.data.total_stats['total_deletions']:,} lines deleted shows active refactoring</li>
                </ul>
            </div>""" if peak_day else ""
        
        return f"""
        <div class="chart-section">
            <div class="chart-title">📈 Daily Code Changes</div>
            <div class="chart-container">
                <canvas id="dailyChangesChart"></canvas>
            </div>
            {insights}
        </div>"""
    
    def _generate_contributor_charts(self) -> str:
        """Generate contributor charts section"""
        return """
        <div class="grid-2">
            <div class="chart-section">
                <div class="chart-title">👥 Contributor Impact</div>
                <div class="chart-container small">
                    <canvas id="contributorChart"></canvas>
                </div>
            </div>
            
            <div class="chart-section">
                <div class="chart-title">🏷️ PR Types Distribution</div>
                <div class="chart-container small">
                    <canvas id="prTypesChart"></canvas>
                </div>
            </div>
        </div>"""
    
    def _generate_contributor_table(self) -> str:
        """Generate contributor performance table"""
        contributors = sorted(
            self.data.contributor_analysis.items(),
            key=lambda x: x[1]['additions'],
            reverse=True
        )
        
        rows = ""
        for name, stats in contributors:
            net_impact = stats['net_change']
            trend_class = 'trend-up' if net_impact > 0 else 'trend-down'
            trend_text = '📈 Growing' if net_impact > 0 else '🔄 Refactoring'
            
            rows += f"""
                <tr>
                    <td><strong>{name}</strong></td>
                    <td>{stats['prs']}</td>
                    <td>{stats['additions']:,}</td>
                    <td>{stats['deletions']:,}</td>
                    <td>{'+'if net_impact >= 0 else ''}{net_impact:,}</td>
                    <td>{stats['files_changed']}</td>
                    <td><span class="trend-indicator {trend_class}">{trend_text}</span></td>
                </tr>"""
        
        return f"""
        <div class="chart-section">
            <div class="chart-title">📊 Contributor Performance Analysis</div>
            <table class="contributor-table">
                <thead>
                    <tr>
                        <th>Contributor</th>
                        <th>PRs</th>
                        <th>Lines Added</th>
                        <th>Lines Deleted</th>
                        <th>Net Impact</th>
                        <th>Files Changed</th>
                        <th>Trend</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>"""
    
    def _generate_insights(self) -> str:
        """Generate insights section"""
        stats = self.data.total_stats
        pr_types = self.data.pr_type_analysis
        
        # Calculate percentages
        feature_pct = (pr_types.get('features', 0) / stats['total_prs'] * 100) if stats['total_prs'] > 0 else 0
        
        return f"""
        <div class="insights">
            <h3>🎯 Performance Highlights:</h3>
            <ul>
                <li><strong>Development Velocity:</strong> {stats['net_change']:,} net lines indicate {'substantial growth' if stats['net_change'] > 0 else 'code optimization'}</li>
                <li><strong>Quality Focus:</strong> {stats['total_deletions']:,} lines deleted show active refactoring and cleanup</li>
                <li><strong>Team Collaboration:</strong> {stats['active_contributors']} contributors with balanced distribution</li>
                <li><strong>Feature-Driven:</strong> {feature_pct:.0f}% of PRs were feature implementations</li>
                <li><strong>Average Impact:</strong> {stats['avg_additions_per_pr']:.0f} lines added per PR</li>
            </ul>
        </div>"""
    
    def _generate_javascript(self) -> str:
        """Generate JavaScript for charts"""
        # Prepare data for JavaScript
        daily_labels = [datetime.strptime(d['date'], '%Y-%m-%d').strftime('%b %d') for d in self.data.daily_stats]
        daily_additions = [d['additions'] for d in self.data.daily_stats]
        daily_deletions = [d['deletions'] for d in self.data.daily_stats]
        
        contributor_names = list(self.data.contributor_analysis.keys())
        contributor_additions = [self.data.contributor_analysis[name]['additions'] for name in contributor_names]
        
        pr_type_labels = list(self.data.pr_type_analysis.keys())
        pr_type_values = list(self.data.pr_type_analysis.values())
        
        return f"""
    <script>
        // Daily Changes Chart
        const dailyCtx = document.getElementById('dailyChangesChart').getContext('2d');
        new Chart(dailyCtx, {{
            type: 'line',
            data: {{
                labels: {daily_labels},
                datasets: [{{
                    label: 'Lines Added',
                    data: {daily_additions},
                    borderColor: '#2ecc71',
                    backgroundColor: 'rgba(46, 204, 113, 0.1)',
                    tension: 0.4,
                    fill: true
                }}, {{
                    label: 'Lines Deleted',
                    data: {daily_deletions},
                    borderColor: '#e74c3c',
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    tension: 0.4,
                    fill: true
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'top',
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Lines of Code'
                        }}
                    }}
                }}
            }}
        }});

        // Contributor Chart
        const contributorCtx = document.getElementById('contributorChart').getContext('2d');
        new Chart(contributorCtx, {{
            type: 'doughnut',
            data: {{
                labels: {contributor_names},
                datasets: [{{
                    data: {contributor_additions},
                    backgroundColor: [
                        '#3498db', '#e74c3c', '#f39c12', 
                        '#9b59b6', '#1abc9c', '#34495e',
                        '#e67e22', '#2ecc71', '#f1c40f'
                    ]
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom'
                    }}
                }}
            }}
        }});

        // PR Types Chart
        const prTypesCtx = document.getElementById('prTypesChart').getContext('2d');
        new Chart(prTypesCtx, {{
            type: 'bar',
            data: {{
                labels: {pr_type_labels},
                datasets: [{{
                    data: {pr_type_values},
                    backgroundColor: ['#2ecc71', '#e74c3c', '#f39c12', '#95a5a6', '#3498db', '#9b59b6', '#34495e']
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            stepSize: 1
                        }}
                    }}
                }}
            }}
        }});
    </script>"""