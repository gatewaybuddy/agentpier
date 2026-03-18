"""Root API endpoints for AgentPier API discovery."""

import json
from utils.response import success, handler


@handler
def get_root(event, context):
    """Returns API discovery information for the root endpoint.""" 
    # Check if this is the actual root path or an undefined route
    path = event.get("path", "/")
    method = event.get("httpMethod", "GET")
    
    # If this is not the root path, return 404 
    if path != "/":
        from utils.response import not_found
        return not_found(f"Endpoint {method} {path} not found. Check the API documentation at https://agentpier.org/docs")
    
    # Return the normal root response
    return success(
        {
            "service": "AgentPier API",
            "version": "1.0.0",
            "description": "Trust standards and evaluation infrastructure for AI agent marketplaces",
            "docs": "https://agentpier.org",
            "endpoints": [
                "/standards/current",
                "/standards/agent", 
                "/standards/marketplace",
                "/listings",
                "/auth/challenge",
                "/trust/agents",
            ],
            "github": "https://github.com/gatewaybuddy/agentpier",
            "status": "operational"
        }
    )


@handler
def get_standards_index(event, context):
    """Returns standards index or redirects to current standards."""
    # Option A: Return a list of available standards endpoints
    return success(
        {
            "standards": {
                "current": "/standards/current",
                "agent": "/standards/agent", 
                "marketplace": "/standards/marketplace"
            },
            "description": "AgentPier certification standards",
            "version": "1.0.0"
        }
    )
    
    # Option B: Redirect to current standards (commented out)
    # from utils.response import redirect
    # return redirect("/standards/current")


@handler 
def get_docs_index(event, context):
    """Returns documentation index or redirects to GitHub docs."""
    return success(
        {
            "docs": {
                "certification_standards": "https://github.com/gatewaybuddy/agentpier/blob/main/docs/certification-standards-v1.md",
                "marketplace_standards": "https://github.com/gatewaybuddy/agentpier/blob/main/docs/marketplace-standards-v1.md",
                "api_reference": "https://github.com/gatewaybuddy/agentpier/blob/main/docs/api-reference.md",
                "integration_guide": "https://github.com/gatewaybuddy/agentpier/blob/main/docs/integration-guide.md"
            },
            "github": "https://github.com/gatewaybuddy/agentpier/tree/main/docs",
            "note": "Documentation is hosted on GitHub for transparency and version control"
        }
    )


@handler
def get_docs_proxy(event, context):
    """Handles requests to /docs/{filename} by redirecting to GitHub."""
    from utils.response import redirect
    
    # Get the requested file path from the proxy parameter
    path_params = event.get("pathParameters", {})
    proxy_path = path_params.get("proxy", "")
    
    if not proxy_path:
        # If no specific file requested, redirect to docs index
        return redirect("https://github.com/gatewaybuddy/agentpier/tree/main/docs")
    
    # Clean the path and redirect to GitHub
    github_url = f"https://github.com/gatewaybuddy/agentpier/blob/main/docs/{proxy_path}"
    return redirect(github_url)


@handler
def catch_all(event, context):
    """Handles all undefined routes with proper JSON error responses."""
    from utils.response import not_found
    
    # Get the requested path
    path = event.get("path", "unknown")
    method = event.get("httpMethod", "unknown")
    
    return not_found(f"Endpoint {method} {path} not found. Check the API documentation at https://agentpier.org/docs")