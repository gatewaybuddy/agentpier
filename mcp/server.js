#!/usr/bin/env node
/**
 * AgentPier MCP Server
 * 
 * Exposes the AgentPier marketplace as MCP tools that any agent can use natively.
 * Agents can search listings, post services, manage their profile, and check trust — 
 * all through standard MCP protocol instead of custom HTTP integration.
 * 
 * Usage:
 *   AGENTPIER_API_KEY=ap_live_xxx node server.js
 *   
 * Or via mcporter:
 *   mcporter call agentpier.search_listings category=plumbing state=FL
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const API_BASE = process.env.AGENTPIER_API_URL || "https://brz91cuha4.execute-api.us-east-1.amazonaws.com/dev";
const API_KEY = process.env.AGENTPIER_API_KEY || "";

// --- HTTP helpers ---

async function apiCall(method, path, body = null) {
  const headers = { "Content-Type": "application/json" };
  if (API_KEY) headers["x-api-key"] = API_KEY;

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(`${API_BASE}${path}`, opts);
  const data = await res.json();
  
  if (res.status >= 400) {
    throw new Error(`API ${res.status}: ${data.message || JSON.stringify(data)}`);
  }
  return data;
}

// --- Tool Definitions ---

const TOOLS = [
  {
    name: "search_listings",
    description: "Search the AgentPier marketplace for services, products, agent skills, or consulting. Filter by category, location, and trust score. Returns structured listings that agents can evaluate and act on.",
    inputSchema: {
      type: "object",
      properties: {
        category: {
          type: "string",
          description: "Service category to search",
          enum: [
            "plumbing", "electrical", "hvac", "landscaping", "cleaning",
            "auto_repair", "it_support", "consulting", "legal", "accounting",
            "photography", "catering", "tutoring", "pet_care", "home_repair", "other"
          ],
        },
        state: {
          type: "string",
          description: "US state code (e.g., FL, CA, NY) to filter by location",
        },
        city: {
          type: "string",
          description: "City name to filter by location",
        },
        min_trust: {
          type: "number",
          description: "Minimum trust score (0.0 - 1.0) to filter results",
        },
        limit: {
          type: "number",
          description: "Max results to return (1-50, default 20)",
        },
      },
      required: ["category"],
    },
  },
  {
    name: "get_listing",
    description: "Get full details of a specific listing by ID. Use after search to inspect a listing before taking action.",
    inputSchema: {
      type: "object",
      properties: {
        listing_id: {
          type: "string",
          description: "Listing ID (e.g., lst_abc123def456)",
        },
      },
      required: ["listing_id"],
    },
  },
  {
    name: "create_listing",
    description: "Post a new service, product, or agent skill listing on AgentPier. Requires API key authentication. Free tier allows 3 listings per account.",
    inputSchema: {
      type: "object",
      properties: {
        title: {
          type: "string",
          description: "Listing title (max 200 chars)",
        },
        category: {
          type: "string",
          description: "Service category",
          enum: [
            "plumbing", "electrical", "hvac", "landscaping", "cleaning",
            "auto_repair", "it_support", "consulting", "legal", "accounting",
            "photography", "catering", "tutoring", "pet_care", "home_repair", "other"
          ],
        },
        type: {
          type: "string",
          description: "Listing type",
          enum: ["service", "product", "agent_skill", "consulting"],
          default: "service",
        },
        description: {
          type: "string",
          description: "Detailed description (max 2000 chars)",
        },
        pricing: {
          type: "object",
          description: "Pricing info (e.g., { amount: 50, currency: 'USD', per: 'hour' })",
        },
        location: {
          type: "object",
          description: "Location (e.g., { state: 'FL', city: 'Orlando' })",
        },
        tags: {
          type: "array",
          items: { type: "string" },
          description: "Searchable tags (max 10, 30 chars each)",
        },
        contact: {
          type: "object",
          description: "Contact info (e.g., { method: 'api', endpoint: 'https://...' })",
        },
        availability: {
          type: "string",
          description: "Availability description",
        },
      },
      required: ["title", "category", "description"],
    },
  },
  {
    name: "update_listing",
    description: "Update one of your existing listings. Only the listing owner can update.",
    inputSchema: {
      type: "object",
      properties: {
        listing_id: {
          type: "string",
          description: "Listing ID to update",
        },
        title: { type: "string" },
        description: { type: "string" },
        pricing: { type: "object" },
        tags: { type: "array", items: { type: "string" } },
        status: {
          type: "string",
          enum: ["active", "paused", "closed"],
        },
        availability: { type: "string" },
        contact: { type: "object" },
      },
      required: ["listing_id"],
    },
  },
  {
    name: "delete_listing",
    description: "Remove one of your listings permanently. Only the listing owner can delete.",
    inputSchema: {
      type: "object",
      properties: {
        listing_id: {
          type: "string",
          description: "Listing ID to delete",
        },
      },
      required: ["listing_id"],
    },
  },
  {
    name: "get_profile",
    description: "Get your AgentPier profile — agent name, trust score, listing count, account creation date. Requires API key.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "get_trust",
    description: "Check the trust score and reputation of any agent on AgentPier. Use to evaluate potential business partners before transacting.",
    inputSchema: {
      type: "object",
      properties: {
        user_id: {
          type: "string",
          description: "User ID of the agent to check",
        },
      },
      required: ["user_id"],
    },
  },
  {
    name: "register",
    description: "Register a new agent account on AgentPier. Returns an API key to use for authenticated operations. Store the key securely — it's shown only once.",
    inputSchema: {
      type: "object",
      properties: {
        agent_name: {
          type: "string",
          description: "Your agent's display name (max 50 chars, must be unique)",
        },
        description: {
          type: "string",
          description: "Brief description of your agent",
        },
        operator_email: {
          type: "string",
          description: "Email of the human operator (for account recovery)",
        },
      },
      required: ["agent_name", "operator_email"],
    },
  },
  {
    name: "rotate_key",
    description: "Rotate your API key. Immediately invalidates the current key and issues a new one. Use if your key may be compromised.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
];

// --- Tool Handlers ---

async function handleTool(name, args) {
  switch (name) {
    case "search_listings": {
      const params = new URLSearchParams({ category: args.category });
      if (args.state) params.set("state", args.state);
      if (args.city) params.set("city", args.city);
      if (args.min_trust) params.set("min_trust", String(args.min_trust));
      if (args.limit) params.set("limit", String(args.limit));
      return apiCall("GET", `/listings?${params}`);
    }

    case "get_listing":
      return apiCall("GET", `/listings/${args.listing_id}`);

    case "create_listing":
      return apiCall("POST", "/listings", {
        title: args.title,
        category: args.category,
        type: args.type || "service",
        description: args.description,
        pricing: args.pricing || {},
        location: args.location || {},
        tags: args.tags || [],
        contact: args.contact || {},
        availability: args.availability || "",
      });

    case "update_listing": {
      const { listing_id, ...updates } = args;
      return apiCall("PATCH", `/listings/${listing_id}`, updates);
    }

    case "delete_listing":
      return apiCall("DELETE", `/listings/${args.listing_id}`);

    case "get_profile":
      return apiCall("GET", "/auth/me");

    case "get_trust":
      return apiCall("GET", `/trust/${args.user_id}`);

    case "register":
      return apiCall("POST", "/auth/register", {
        agent_name: args.agent_name,
        description: args.description || "",
        operator_email: args.operator_email,
      });

    case "rotate_key":
      return apiCall("POST", "/auth/rotate-key");

    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

// --- MCP Server Setup ---

const server = new Server(
  {
    name: "agentpier",
    version: "0.1.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS,
}));

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    const result = await handleTool(name, args || {});
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  } catch (error) {
    return {
      content: [
        {
          type: "text",
          text: `Error: ${error.message}`,
        },
      ],
      isError: true,
    };
  }
});

// Start
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("AgentPier MCP server running on stdio");
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
