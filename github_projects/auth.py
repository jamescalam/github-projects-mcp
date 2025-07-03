from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Annotated
import requests


# Security scheme for Bearer token authentication
security = HTTPBearer()

async def verify_github_token(credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]) -> str:
    """
    Verify that the provided token is a valid GitHub PAT.
    Returns the token if valid, raises HTTPException if invalid.
    """
    token = credentials.credentials
    
    # Validate token format (GitHub PATs start with specific prefixes)
    if not (token.startswith("github_pat_") or token.startswith("ghp_") or token.startswith("gho_")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid GitHub Personal Access Token format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Optional: Test the token by making a simple API call to GitHub
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        response = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired GitHub Personal Access Token",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify GitHub token - service temporarily unavailable",
        )
    
    return token