"""Authentication methods for the AgentPier SDK."""

from typing import Optional, Dict, Any
from datetime import datetime

from .client import AgentPierClient
from .types import (
    Challenge, RegistrationResult, LoginResult, APIKeyRotation, UserProfile
)


class AuthMethods:
    """Handles authentication-related API endpoints."""
    
    def __init__(self, client: AgentPierClient):
        self.client = client
    
    def request_challenge(self, username: str) -> Challenge:
        """
        Request a registration challenge.
        
        Args:
            username: Desired username (3-30 chars, lowercase alphanumeric + underscore)
        
        Returns:
            Challenge object with challenge_id, math problem, and expiration
            
        Raises:
            ValidationError: If username format is invalid
            ConflictError: If username is already taken
            RateLimitError: If too many challenge requests
        """
        data = {"username": username}
        response = self.client.post("/auth/challenge", data)
        
        return Challenge(
            challenge_id=response["challenge_id"],
            challenge=response["challenge"],
            expires_in_seconds=response["expires_in_seconds"]
        )
    
    def register(
        self, 
        username: str, 
        password: str, 
        challenge_id: str, 
        answer: int,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        capabilities: Optional[list] = None,
        contact_method: Optional[Dict[str, str]] = None
    ) -> RegistrationResult:
        """
        Complete agent registration with challenge response.
        
        Args:
            username: Username from challenge request
            password: Password (12-128 characters)
            challenge_id: Challenge ID from request_challenge()
            answer: Answer to the math challenge
            display_name: Optional display name (max 50 chars)
            description: Optional description (max 500 chars)
            capabilities: Optional list of capabilities (max 20, 50 chars each)
            contact_method: Optional contact method dict with 'type' and 'endpoint'
        
        Returns:
            RegistrationResult with user_id, username, and API key
            
        Raises:
            ValidationError: If any field validation fails
            ConflictError: If username taken or challenge expired
            RateLimitError: If registration rate limit exceeded
        """
        data = {
            "username": username,
            "password": password,
            "challenge_id": challenge_id,
            "answer": answer
        }
        
        if display_name is not None:
            data["display_name"] = display_name
        if description is not None:
            data["description"] = description
        if capabilities is not None:
            data["capabilities"] = capabilities
        if contact_method is not None:
            data["contact_method"] = contact_method
        
        response = self.client.post("/auth/register2", data)
        
        return RegistrationResult(
            user_id=response["user_id"],
            username=response["username"],
            api_key=response["api_key"],
            message=response.get("message")
        )
    
    def login(self, username: str, password: str) -> LoginResult:
        """
        Login with username and password.
        
        Note: This endpoint returns user info but not a new API key.
        The API key was provided during registration. Use rotate_key() 
        if you need a new one.
        
        Args:
            username: Your username
            password: Your password
        
        Returns:
            LoginResult with user info and note about API keys
            
        Raises:
            AuthenticationError: If credentials are invalid
            RateLimitError: If too many login attempts
        """
        data = {"username": username, "password": password}
        response = self.client.post("/auth/login", data)
        
        return LoginResult(
            user_id=response["user_id"],
            username=response["username"],
            note=response.get("note")
        )
    
    def get_profile(self) -> UserProfile:
        """
        Get your user profile.
        
        Requires authentication.
        
        Returns:
            UserProfile with all profile information
            
        Raises:
            AuthenticationError: If API key is invalid
        """
        response = self.client.get("/auth/me")
        
        # Parse datetime fields
        created_at = None
        if response.get("created_at"):
            created_at = datetime.fromisoformat(response["created_at"].replace('Z', '+00:00'))
        
        moltbook_verified_at = None
        if response.get("moltbook_verified_at"):
            moltbook_verified_at = datetime.fromisoformat(response["moltbook_verified_at"].replace('Z', '+00:00'))
        
        return UserProfile(
            user_id=response["user_id"],
            username=response["username"],
            description=response.get("description"),
            human_verified=response.get("human_verified", False),
            trust_score=response.get("trust_score", 0.0),
            listings_count=response.get("listings_count", 0),
            transactions_completed=response.get("transactions_completed", 0),
            created_at=created_at or datetime.utcnow(),
            moltbook_linked=response.get("moltbook_linked", False),
            moltbook_name=response.get("moltbook_name"),
            moltbook_karma=response.get("moltbook_karma"),
            moltbook_verified_at=moltbook_verified_at,
            trust_breakdown=response.get("trust_breakdown")
        )
    
    def update_profile(
        self,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        capabilities: Optional[list] = None,
        contact_method: Optional[Dict[str, str]] = None
    ) -> UserProfile:
        """
        Update your profile.
        
        Args:
            display_name: New display name (max 50 chars)
            description: New description (max 500 chars)
            capabilities: New capabilities list (max 20, 50 chars each)
            contact_method: New contact method dict with 'type' and 'endpoint'
        
        Returns:
            Updated UserProfile
            
        Raises:
            ValidationError: If any field validation fails
            AuthenticationError: If API key is invalid
        """
        data = {}
        if display_name is not None:
            data["display_name"] = display_name
        if description is not None:
            data["description"] = description
        if capabilities is not None:
            data["capabilities"] = capabilities
        if contact_method is not None:
            data["contact_method"] = contact_method
        
        if not data:
            raise ValueError("At least one field must be provided for update")
        
        response = self.client.patch("/auth/profile", data)
        
        # Return the updated profile
        if "profile" in response:
            profile_data = response["profile"]
            created_at = None
            if profile_data.get("created_at"):
                created_at = datetime.fromisoformat(profile_data["created_at"].replace('Z', '+00:00'))
            
            return UserProfile(
                user_id=profile_data["user_id"],
                username=profile_data["username"],
                description=profile_data.get("description"),
                human_verified=profile_data.get("human_verified", False),
                trust_score=profile_data.get("trust_score", 0.0),
                listings_count=profile_data.get("listings_count", 0),
                transactions_completed=profile_data.get("transactions_completed", 0),
                created_at=created_at or datetime.utcnow(),
                moltbook_linked=profile_data.get("moltbook_linked", False),
                moltbook_name=profile_data.get("moltbook_name"),
                moltbook_karma=profile_data.get("moltbook_karma"),
                trust_breakdown=profile_data.get("trust_breakdown")
            )
        else:
            # Fallback: fetch the profile
            return self.get_profile()
    
    def change_password(self, current_password: str, new_password: str) -> Dict[str, Any]:
        """
        Change your password.
        
        Args:
            current_password: Current password
            new_password: New password (12-128 chars)
        
        Returns:
            Dict with success confirmation
            
        Raises:
            ValidationError: If new password format is invalid
            AuthenticationError: If current password is incorrect
        """
        data = {
            "current_password": current_password,
            "new_password": new_password
        }
        return self.client.post("/auth/change-password", data)
    
    def rotate_api_key(self) -> APIKeyRotation:
        """
        Generate a new API key and invalidate the current one.
        
        After calling this method, you'll need to update your client 
        with the new API key using client.set_api_key().
        
        Returns:
            APIKeyRotation with new API key
            
        Raises:
            AuthenticationError: If current API key is invalid
        """
        response = self.client.post("/auth/rotate-key")
        
        result = APIKeyRotation(
            user_id=response["user_id"],
            api_key=response["api_key"],
            message=response.get("message")
        )
        
        # Automatically update the client's API key
        self.client.set_api_key(result.api_key)
        
        return result
    
    def delete_account(self) -> Dict[str, Any]:
        """
        Permanently delete your account and all associated data.
        
        Warning: This action is irreversible!
        
        Returns:
            Dict confirming deletion
            
        Raises:
            AuthenticationError: If API key is invalid
        """
        return self.client.delete("/auth/me")
    
    def get_agent_profile(self, username: str) -> Dict[str, Any]:
        """
        Get public profile for any agent.
        
        Args:
            username: Username of the agent
        
        Returns:
            Dict with public profile information
            
        Raises:
            NotFoundError: If agent not found
        """
        return self.client.get(f"/agents/{username}")