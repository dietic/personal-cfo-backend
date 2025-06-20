"""
Seed data for network providers and card types.

This is like setting up a reference catalog - defining all the standard
network providers and card types that users can choose from.
"""

NETWORK_PROVIDERS = [
    {
        "name": "Visa",
        "short_name": "VISA",
        "country": "GLOBAL",
        "color_primary": "#1A1F71",  # Visa blue
        "color_secondary": "#F7B600", # Visa gold
        "is_active": True
    },
    {
        "name": "Mastercard", 
        "short_name": "MC",
        "country": "GLOBAL",
        "color_primary": "#EB001B",  # Mastercard red
        "color_secondary": "#FF5F00", # Mastercard orange
        "is_active": True
    },
    {
        "name": "American Express",
        "short_name": "AMEX", 
        "country": "GLOBAL",
        "color_primary": "#006FCF",  # Amex blue
        "color_secondary": "#00A6F0", # Amex light blue
        "is_active": True
    },
    {
        "name": "Discover",
        "short_name": "DISC",
        "country": "GLOBAL", 
        "color_primary": "#FF6000",  # Discover orange
        "color_secondary": "#FFA500", # Discover light orange
        "is_active": True
    },
    {
        "name": "UnionPay",
        "short_name": "UP",
        "country": "GLOBAL",
        "color_primary": "#E21836",  # UnionPay red
        "color_secondary": "#0066CC", # UnionPay blue
        "is_active": True
    },
    {
        "name": "JCB",
        "short_name": "JCB",
        "country": "GLOBAL",
        "color_primary": "#0066CC",  # JCB blue
        "color_secondary": "#FF6600", # JCB orange
        "is_active": True
    },
    {
        "name": "Diners Club",
        "short_name": "DINERS",
        "country": "GLOBAL",
        "color_primary": "#0079BE",  # Diners blue
        "color_secondary": "#FFFFFF", # White
        "is_active": True
    },
    {
        "name": "Other",
        "short_name": "OTHER",
        "country": "GLOBAL",
        "color_primary": "#6B7280",  # Gray
        "color_secondary": "#9CA3AF", # Light gray
        "is_active": True
    }
]

CARD_TYPES = [
    {
        "name": "Credit Card",
        "short_name": "Credit",
        "country": "GLOBAL",
        "description": "Revolving credit with monthly payments and interest charges",
        "typical_interest_rate": "18-29% APR",
        "color_primary": "#DC2626",  # Red for credit (debt)
        "color_secondary": "#FEE2E2", # Light red
        "is_active": True
    },
    {
        "name": "Debit Card", 
        "short_name": "Debit",
        "country": "GLOBAL",
        "description": "Direct access to bank account funds",
        "typical_interest_rate": "N/A",
        "color_primary": "#059669",  # Green for debit (your money)
        "color_secondary": "#D1FAE5", # Light green
        "is_active": True
    },
    {
        "name": "Charge Card",
        "short_name": "Charge", 
        "country": "GLOBAL",
        "description": "Must be paid in full each month, no preset spending limit",
        "typical_interest_rate": "N/A (fees for late payment)",
        "color_primary": "#7C3AED",  # Purple for charge
        "color_secondary": "#EDE9FE", # Light purple
        "is_active": True
    },
    {
        "name": "Prepaid Card",
        "short_name": "Prepaid",
        "country": "GLOBAL", 
        "description": "Pre-loaded with funds, no credit check required",
        "typical_interest_rate": "N/A",
        "color_primary": "#F59E0B",  # Orange for prepaid
        "color_secondary": "#FEF3C7", # Light orange
        "is_active": True
    },
    {
        "name": "Store Card",
        "short_name": "Store",
        "country": "GLOBAL",
        "description": "Limited to specific retailer or group of stores",
        "typical_interest_rate": "22-30% APR",
        "color_primary": "#EC4899",  # Pink for store cards
        "color_secondary": "#FCE7F3", # Light pink
        "is_active": True
    },
    {
        "name": "Business Card",
        "short_name": "Business", 
        "country": "GLOBAL",
        "description": "Designed for business expenses and cash flow management",
        "typical_interest_rate": "15-25% APR",
        "color_primary": "#1F2937",  # Dark gray for business
        "color_secondary": "#F3F4F6", # Light gray
        "is_active": True
    }
]
