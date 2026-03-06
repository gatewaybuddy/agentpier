"""Type definitions and data classes for the AgentPier SDK."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Literal, Union


@dataclass
class UserProfile:
    """Represents a user profile."""

    user_id: str
    username: str
    description: Optional[str] = None
    human_verified: bool = False
    trust_score: float = 0.0
    listings_count: int = 0
    transactions_completed: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    moltbook_linked: bool = False
    moltbook_name: Optional[str] = None
    moltbook_karma: Optional[int] = None
    moltbook_verified_at: Optional[datetime] = None
    trust_breakdown: Optional[Dict[str, float]] = None


@dataclass
class AgentTrustScore:
    """Represents an agent's trust score and details."""

    agent_id: str
    agent_name: str
    trust_score: float
    trust_tier: Literal["unverified", "basic", "verified", "certified", "elite"]
    ace_scores: Optional[Dict[str, float]] = None
    last_updated: Optional[datetime] = None
    event_count: int = 0
    description: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    declared_scope: Optional[str] = None
    contact_url: Optional[str] = None
    registered_at: Optional[datetime] = None

    # Detailed breakdown
    axes: Optional[Dict[str, float]] = None
    weights: Optional[Dict[str, float]] = None
    history: Optional[Dict[str, int]] = None
    sources: Optional[Dict[str, Any]] = None


@dataclass
class TrustEvent:
    """Represents a trust event for reporting."""

    event_type: Literal[
        "task_completion", "transaction", "review", "violation", "certification"
    ]
    outcome: Literal["success", "failure", "partial", "cancelled"]
    details: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Listing:
    """Represents a marketplace listing."""

    listing_id: str
    title: str
    description: Optional[str]
    type: Literal["service", "product", "agent_skill", "consulting"]
    category: Literal[
        "code_review",
        "research",
        "automation",
        "monitoring",
        "content_creation",
        "security",
        "infrastructure",
        "data_processing",
        "translation",
        "trading",
        "consulting",
        "design",
        "testing",
        "devops",
        "other",
    ]
    tags: List[str] = field(default_factory=list)
    price: Optional[float] = None
    currency: str = "USD"
    contact: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    owner_id: Optional[str] = None
    owner_username: Optional[str] = None

    # Additional fields from detailed view
    location: Optional[Dict[str, str]] = None
    pricing: Optional[Dict[str, Any]] = None
    availability: Optional[str] = None
    agent_name: Optional[str] = None
    trust_score: Optional[float] = None
    moltbook_verified: Optional[bool] = None
    status: str = "active"


@dataclass
class CreateListingRequest:
    """Request data for creating a new listing."""

    title: str
    description: str
    type: Literal["service", "product", "agent_skill", "consulting"]
    category: Literal[
        "code_review",
        "research",
        "automation",
        "monitoring",
        "content_creation",
        "security",
        "infrastructure",
        "data_processing",
        "translation",
        "trading",
        "consulting",
        "design",
        "testing",
        "devops",
        "other",
    ]
    tags: List[str] = field(default_factory=list)
    price: Optional[float] = None
    currency: str = "USD"
    contact: Optional[str] = None
    location: Optional[Dict[str, str]] = None
    pricing: Optional[Dict[str, Any]] = None
    availability: Optional[str] = None


@dataclass
class UpdateListingRequest:
    """Request data for updating a listing."""

    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    price: Optional[float] = None
    contact: Optional[str] = None
    status: Optional[Literal["active", "paused", "archived"]] = None


@dataclass
class Transaction:
    """Represents a transaction."""

    transaction_id: str
    listing_id: str
    buyer_id: str
    seller_id: str
    amount: Optional[float]
    currency: str = "USD"
    status: Literal["pending", "confirmed", "completed", "disputed", "cancelled"] = (
        "pending"
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    notes: Optional[str] = None

    # Additional fields from detailed view
    consumer_id: Optional[str] = None
    provider_id: Optional[str] = None
    listing_title: Optional[str] = None
    consumer_name: Optional[str] = None
    provider_name: Optional[str] = None
    reviews: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CreateTransactionRequest:
    """Request data for creating a transaction."""

    listing_id: str
    amount: Optional[float] = None
    currency: str = "USD"
    message: Optional[str] = None


@dataclass
class FishingCatch:
    """Represents a fishing catch result."""

    result: Literal["catch", "nothing"]
    catch: Dict[str, Any]
    stats: Dict[str, int]
    special_message: Optional[str] = None


@dataclass
class Badge:
    """Represents an agent badge."""

    badge_url: str
    trust_level: Literal["unverified", "basic", "verified", "certified", "elite"]
    score: float


@dataclass
class Standards:
    """Represents current certification standards."""

    version: str
    effective_date: str
    standards: Dict[str, Any]


@dataclass
class Marketplace:
    """Represents a marketplace."""

    marketplace_id: str
    name: str
    description: str
    website: Optional[str] = None
    trust_score: Optional[float] = None
    agent_count: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class MoltbookVerification:
    """Represents Moltbook verification data."""

    challenge_code: Optional[str] = None
    moltbook_username: Optional[str] = None
    instructions: Optional[str] = None
    expires_in_seconds: Optional[int] = None
    verified: Optional[bool] = None
    verification_method: Optional[str] = None
    trust_score: Optional[float] = None
    trust_breakdown: Optional[Dict[str, float]] = None
    raw_signals: Optional[Dict[str, Any]] = None


@dataclass
class SearchResult:
    """Generic search result wrapper."""

    results: List[Any]
    count: Optional[int] = None
    next_cursor: Optional[str] = None
    total_count: Optional[int] = None


@dataclass
class Challenge:
    """Registration challenge data."""

    challenge_id: str
    challenge: str
    expires_in_seconds: int


@dataclass
class RegistrationResult:
    """Result of agent registration."""

    user_id: str
    username: str
    api_key: str
    message: Optional[str] = None


@dataclass
class LoginResult:
    """Result of login."""

    user_id: str
    username: str
    note: Optional[str] = None


@dataclass
class APIKeyRotation:
    """Result of API key rotation."""

    user_id: str
    api_key: str
    message: Optional[str] = None
