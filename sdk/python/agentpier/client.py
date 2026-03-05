"""Main AgentPier client class."""

import time
from typing import Optional, Dict, Any, Union
from urllib.parse import urljoin

import requests

from .exceptions import (
    AgentPierError, NetworkError, raise_for_status
)


class AgentPierClient:
    """
    Core HTTP client for the AgentPier API.
    
    Handles authentication, rate limiting, retries, and response parsing.
    
    Security Note: All error messages are automatically sanitized to prevent 
    API key exposure in logs or exception traces.
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        base_url: str = "https://api.agentpier.org",
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize the AgentPier client.
        
        Args:
            api_key: Your AgentPier API key (starts with 'ap_live_' or 'ap_test_')
            base_url: Base URL for the API (defaults to production)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Base delay between retries in seconds (uses exponential backoff)
        """
        # Validate API key format if provided
        if api_key is not None:
            self._validate_api_key(api_key)
        
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Default headers
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "agentpier-python-sdk/1.0.0"
        }
        
        if self.api_key:
            self.headers["X-API-Key"] = self.api_key
    
    def set_api_key(self, api_key: str) -> None:
        """Set or update the API key."""
        self._validate_api_key(api_key)
        self.api_key = api_key
        self.headers["X-API-Key"] = api_key
    
    def _validate_api_key(self, api_key: str) -> None:
        """
        Validate API key format.
        
        Args:
            api_key: API key to validate
            
        Raises:
            AgentPierError: If API key format is invalid
        """
        if not isinstance(api_key, str):
            raise AgentPierError("API key must be a string")
        
        if not api_key.startswith('ap_'):
            raise AgentPierError("API key must start with 'ap_' prefix (e.g., 'ap_live_xxx' or 'ap_test_xxx')")
        
        # Check for common patterns
        if api_key.startswith('ap_live_') or api_key.startswith('ap_test_'):
            # Valid prefixes
            pass
        else:
            raise AgentPierError("API key must start with 'ap_live_' or 'ap_test_' prefix")
    
    def _sanitize_api_key(self, text: str) -> str:
        """
        Sanitize API keys from error messages and logs.
        
        Args:
            text: Text that might contain API keys
            
        Returns:
            Sanitized text with API keys replaced by placeholder
        """
        if not self.api_key or not text:
            return text
        
        # Replace the full API key with a masked version
        if self.api_key in text:
            # Show only prefix and last 4 characters for debugging
            if len(self.api_key) > 8:
                masked_key = self.api_key[:8] + "****" + self.api_key[-4:]
            else:
                masked_key = "ap_****"
            text = text.replace(self.api_key, masked_key)
        
        return text
    
    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint."""
        return urljoin(self.base_url + '/', endpoint.lstrip('/'))
    
    def _should_retry(self, response: requests.Response, attempt: int) -> bool:
        """Determine if a request should be retried."""
        if attempt >= self.max_retries:
            return False
        
        # Retry on 5xx server errors
        if response.status_code >= 500:
            return True
        
        # Retry on specific 429 responses if Retry-After is reasonable
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                try:
                    retry_seconds = int(retry_after)
                    # Only retry if the delay is reasonable (< 60 seconds)
                    return retry_seconds <= 60
                except ValueError:
                    pass
        
        return False
    
    def _get_retry_delay(self, attempt: int, response: Optional[requests.Response] = None) -> float:
        """Calculate retry delay using exponential backoff."""
        # Check for Retry-After header first
        if response and response.status_code == 429:
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
        
        # Exponential backoff: base_delay * (2 ^ attempt)
        return self.retry_delay * (2 ** attempt)
    
    def request(
        self, 
        method: str, 
        endpoint: str, 
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Any:
        """
        Make an HTTP request to the AgentPier API with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., '/auth/me')
            json_data: JSON data to send in request body
            params: Query parameters
            headers: Additional headers to send
            **kwargs: Additional arguments passed to requests
        
        Returns:
            Parsed JSON response data
            
        Raises:
            NetworkError: For connection/timeout issues
            AgentPierError: For API errors (subclasses for specific error types)
        """
        url = self._build_url(endpoint)
        
        # Merge headers
        req_headers = self.headers.copy()
        if headers:
            req_headers.update(headers)
        
        # Request kwargs
        req_kwargs = {
            'timeout': self.timeout,
            'headers': req_headers,
            **kwargs
        }
        
        if json_data is not None:
            req_kwargs['json'] = json_data
        
        if params:
            req_kwargs['params'] = params
        
        last_exception = None
        
        # SECURITY: All exception messages below are sanitized to prevent API key exposure
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.request(method, url, **req_kwargs)
                
                # Check if we should retry
                if self._should_retry(response, attempt):
                    delay = self._get_retry_delay(attempt, response)
                    time.sleep(delay)
                    continue
                
                # Parse response
                try:
                    response_data = response.json() if response.content else {}
                except ValueError:
                    response_data = {}
                
                # Raise for HTTP errors
                raise_for_status(response, response_data)
                
                return response_data
                
            except requests.exceptions.ConnectionError as e:
                sanitized_error = self._sanitize_api_key(str(e))
                last_exception = NetworkError(f"Connection error: {sanitized_error}")
                if attempt < self.max_retries:
                    delay = self._get_retry_delay(attempt)
                    time.sleep(delay)
                    continue
                raise last_exception
                
            except requests.exceptions.Timeout as e:
                sanitized_error = self._sanitize_api_key(str(e))
                last_exception = NetworkError(f"Request timeout: {sanitized_error}")
                if attempt < self.max_retries:
                    delay = self._get_retry_delay(attempt)
                    time.sleep(delay)
                    continue
                raise last_exception
                
            except requests.exceptions.RequestException as e:
                # Other requests errors
                sanitized_error = self._sanitize_api_key(str(e))
                raise NetworkError(f"Request error: {sanitized_error}")
            
            except AgentPierError:
                # Re-raise AgentPier errors without retry
                raise
        
        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        else:
            raise AgentPierError("Max retries exceeded")
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """Make a GET request."""
        return self.request('GET', endpoint, params=params, **kwargs)
    
    def post(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """Make a POST request."""
        return self.request('POST', endpoint, json_data=json_data, **kwargs)
    
    def patch(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """Make a PATCH request."""
        return self.request('PATCH', endpoint, json_data=json_data, **kwargs)
    
    def delete(self, endpoint: str, **kwargs) -> Any:
        """Make a DELETE request."""
        return self.request('DELETE', endpoint, **kwargs)
    
    def put(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """Make a PUT request."""
        return self.request('PUT', endpoint, json_data=json_data, **kwargs)