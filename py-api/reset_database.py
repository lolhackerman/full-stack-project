#!/usr/bin/env python3
"""Reset database and clear all old auth data to start fresh with new workspace code format."""

import os
from dotenv import load_dotenv

load_dotenv()

# Check if MongoDB is enabled
ENABLE_MONGODB = os.getenv("ENABLE_MONGODB", "false").lower() == "true"

if not ENABLE_MONGODB:
    print("❌ MongoDB is not enabled. Set ENABLE_MONGODB=true in .env")
    exit(1)

from app.database import get_database

def reset_all_collections():
    """Drop all collections and start fresh."""
    db = get_database()
    
    collections_to_drop = [
        'verification_codes',
        'sessions',
        'chat_messages',
        'chat_threads',
        'uploaded_files',
        'cover_letters',
        'job_descriptions'
    ]
    
    print("🗑️  Clearing all collections...")
    for collection_name in collections_to_drop:
        try:
            db[collection_name].drop()
            print(f"   ✓ Dropped {collection_name}")
        except Exception as e:
            print(f"   ⚠️  Could not drop {collection_name}: {e}")
    
    print("\n✅ Database reset complete!")
    print("📝 All data has been cleared. The app will now use the new workspace code format.")
    print("   - New codes will be 6-character alphanumeric (e.g., ABC123)")
    print("   - Codes serve as both access key and profile ID")
    print("   - Users can re-enter their code to access their workspace")

if __name__ == "__main__":
    print("🚀 Resetting database for new workspace code format...")
    print("   This will DELETE ALL existing data.")
    
    confirm = input("\n⚠️  Are you sure? Type 'yes' to continue: ")
    if confirm.lower() == 'yes':
        reset_all_collections()
    else:
        print("❌ Reset cancelled.")
