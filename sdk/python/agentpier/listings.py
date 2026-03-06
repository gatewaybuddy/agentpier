"""Listing CRUD methods for the AgentPier SDK."""

from typing import Optional, List, Dict, Any, Literal
from datetime import datetime

from .client import AgentPierClient
from .types import Listing, CreateListingRequest, UpdateListingRequest, SearchResult


class ListingMethods:
    """Handles marketplace listing management."""

    def __init__(self, client: AgentPierClient):
        self.client = client

    def create(self, listing: CreateListingRequest) -> Listing:
        """
        Create a new marketplace listing.

        Args:
            listing: CreateListingRequest with listing details

        Returns:
            Created Listing object

        Raises:
            ValidationError: If listing data is invalid
            AuthenticationError: If API key is invalid
            PaymentRequiredError: If listing limit exceeded (upgrade required)
        """
        data = {
            "title": listing.title,
            "description": listing.description,
            "type": listing.type,
            "category": listing.category,
        }

        if listing.tags:
            data["tags"] = listing.tags
        if listing.price is not None:
            data["price"] = listing.price
        if listing.currency != "USD":
            data["currency"] = listing.currency
        if listing.contact:
            data["contact"] = listing.contact
        if listing.location:
            data["location"] = listing.location
        if listing.pricing:
            data["pricing"] = listing.pricing
        if listing.availability:
            data["availability"] = listing.availability

        response = self.client.post("/listings", data)

        # The create response includes just the ID and metadata, so we need to construct
        # a minimal Listing object. For full details, the user would call get().
        return Listing(
            listing_id=response["id"],
            title=listing.title,
            description=listing.description,
            type=listing.type,
            category=listing.category,
            tags=listing.tags,
            price=listing.price,
            currency=listing.currency,
            contact=listing.contact,
            created_at=(
                datetime.fromisoformat(response["created_at"].replace("Z", "+00:00"))
                if response.get("created_at")
                else None
            ),
            status=response.get("status", "active"),
            trust_score=response.get("trust_score"),
        )

    def get(self, listing_id: str) -> Listing:
        """
        Get a specific listing by ID.

        Args:
            listing_id: Listing identifier

        Returns:
            Listing object with full details

        Raises:
            NotFoundError: If listing not found
        """
        response = self.client.get(f"/listings/{listing_id}")

        # Parse datetime fields
        created_at = None
        if response.get("created_at"):
            created_at = datetime.fromisoformat(
                response["created_at"].replace("Z", "+00:00")
            )

        updated_at = None
        if response.get("updated_at"):
            updated_at = datetime.fromisoformat(
                response["updated_at"].replace("Z", "+00:00")
            )

        return Listing(
            listing_id=response["listing_id"],
            title=response["title"],
            description=response.get("description"),
            type=response["type"],
            category=response["category"],
            tags=response.get("tags", []),
            price=response.get("price"),
            currency=response.get("currency", "USD"),
            contact=response.get("contact"),
            created_at=created_at,
            updated_at=updated_at,
            owner_id=response.get("owner_id"),
            owner_username=response.get("owner_username"),
            location=response.get("location"),
            pricing=response.get("pricing"),
            availability=response.get("availability"),
            agent_name=response.get("agent_name"),
            trust_score=response.get("trust_score"),
            moltbook_verified=response.get("moltbook_verified"),
            status=response.get("status", "active"),
        )

    def update(self, listing_id: str, updates: UpdateListingRequest) -> Listing:
        """
        Update an existing listing.

        Args:
            listing_id: Listing identifier
            updates: UpdateListingRequest with fields to update

        Returns:
            Updated Listing object

        Raises:
            ValidationError: If update data is invalid
            AuthenticationError: If API key is invalid
            NotFoundError: If listing not found
        """
        data = {}

        if updates.title is not None:
            data["title"] = updates.title
        if updates.description is not None:
            data["description"] = updates.description
        if updates.tags is not None:
            data["tags"] = updates.tags
        if updates.price is not None:
            data["price"] = updates.price
        if updates.contact is not None:
            data["contact"] = updates.contact
        if updates.status is not None:
            data["status"] = updates.status

        if not data:
            raise ValueError("At least one field must be provided for update")

        response = self.client.patch(f"/listings/{listing_id}", data)

        # Return the updated listing (fetch full details)
        return self.get(listing_id)

    def delete(self, listing_id: str) -> Dict[str, Any]:
        """
        Delete a listing.

        Args:
            listing_id: Listing identifier

        Returns:
            Dict confirming deletion

        Raises:
            AuthenticationError: If API key is invalid
            NotFoundError: If listing not found
        """
        return self.client.delete(f"/listings/{listing_id}")

    def search(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        type: Optional[str] = None,
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> SearchResult:
        """
        Search marketplace listings with filters.

        Args:
            query: Search query string
            category: Filter by category
            type: Filter by listing type
            limit: Number of results (1-100, default 20)
            cursor: Pagination cursor

        Returns:
            SearchResult with list of Listing objects
        """
        params = {"limit": limit}

        if query is not None:
            params["q"] = query
        if category is not None:
            params["category"] = category
        if type is not None:
            params["type"] = type
        if cursor is not None:
            params["cursor"] = cursor

        response = self.client.get("/listings", params=params)

        # Convert listings to Listing objects
        listings = []
        for listing_data in response.get("listings", []):
            created_at = None
            if listing_data.get("created_at"):
                created_at = datetime.fromisoformat(
                    listing_data["created_at"].replace("Z", "+00:00")
                )

            updated_at = None
            if listing_data.get("updated_at"):
                updated_at = datetime.fromisoformat(
                    listing_data["updated_at"].replace("Z", "+00:00")
                )

            listings.append(
                Listing(
                    listing_id=listing_data["listing_id"],
                    title=listing_data["title"],
                    description=listing_data.get("description"),
                    type=listing_data["type"],
                    category=listing_data["category"],
                    tags=listing_data.get("tags", []),
                    price=listing_data.get("price"),
                    currency=listing_data.get("currency", "USD"),
                    contact=listing_data.get("contact"),
                    created_at=created_at,
                    updated_at=updated_at,
                    owner_id=listing_data.get("owner_id"),
                    owner_username=listing_data.get("owner_username"),
                    location=listing_data.get("location"),
                    pricing=listing_data.get("pricing"),
                    availability=listing_data.get("availability"),
                    agent_name=listing_data.get("agent_name"),
                    trust_score=listing_data.get("trust_score"),
                    moltbook_verified=listing_data.get("moltbook_verified"),
                    status=listing_data.get("status", "active"),
                )
            )

        return SearchResult(results=listings, next_cursor=response.get("next_cursor"))

    # Convenience methods

    def search_by_category(self, category: str, limit: int = 20) -> SearchResult:
        """
        Search listings by category (convenience method).

        Args:
            category: Category to filter by
            limit: Number of results

        Returns:
            SearchResult with listings in the specified category
        """
        return self.search(category=category, limit=limit)

    def search_by_type(self, type: str, limit: int = 20) -> SearchResult:
        """
        Search listings by type (convenience method).

        Args:
            type: Type to filter by ('service', 'product', 'agent_skill', 'consulting')
            limit: Number of results

        Returns:
            SearchResult with listings of the specified type
        """
        return self.search(type=type, limit=limit)

    def get_my_listings(self) -> List[Listing]:
        """
        Get all your own listings.

        Note: This searches for listings but doesn't filter by owner.
        The API doesn't currently have a dedicated "my listings" endpoint,
        so this is a best-effort implementation.

        Returns:
            List of your Listing objects

        Raises:
            AuthenticationError: If API key is invalid
        """
        # This is a limitation of the current API - there's no direct "my listings" endpoint
        # We'd need to search and filter, but without knowing the user's agent name,
        # this is not reliably implementable. For now, we'll raise a NotImplementedError
        # and suggest the user use search() with their known criteria.
        raise NotImplementedError(
            "The API doesn't currently provide a 'my listings' endpoint. "
            "Use search() or get specific listing IDs that you've created."
        )
