"""
Shared Supabase client for Vercel serverless API functions.

Usage:
    from lib.supabase_client import get_supabase

    supabase = get_supabase()
    result = supabase.table('users').select('*').execute()

Environment variables (set in Vercel dashboard):
    SUPABASE_URL        - Your Supabase project URL
    SUPABASE_SERVICE_KEY - Service role key (full access, server-side only)
"""

import os
from supabase import create_client, Client

_client: Client | None = None


def get_supabase() -> Client:
    """Get or create a Supabase client singleton."""
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
        if not url or not key:
            raise RuntimeError(
                "Missing SUPABASE_URL or SUPABASE_SERVICE_KEY environment variables. "
                "Set these in your Vercel project settings."
            )
        _client = create_client(url, key)
    return _client
