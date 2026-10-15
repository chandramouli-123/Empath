import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

supabase_url = os.environ.get("SUPABASE_URL", "")
supabase_key = os.environ.get("SUPABASE_ANON_KEY", "")

supabase: Client = None
if supabase_url and supabase_key and "your-project" not in supabase_url:
    try:
        supabase = create_client(supabase_url, supabase_key)
    except Exception as e:
        logger.warning(f"Supabase client initialization failed: {e}")

