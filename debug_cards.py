#!/usr/bin/env python3
"""
Debug script to check cards and their bank providers
"""
import sys
import os
sys.path.append('/home/diego/Documents/personal-cfo/personal-cfo-backend')

from sqlalchemy.orm import sessionmaker, Session
from app.core.database import engine
from app.models.card import Card
from app.models.bank_provider import BankProvider
from app.models.user import User

def debug_cards():
    """Check what cards exist and their bank provider info"""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        print("=== DEBUGGING CARDS AND BANK PROVIDERS ===")
        
        # Get all cards with their bank providers
        cards = db.query(Card).all()
        print(f"\nFound {len(cards)} cards:")
        
        for card in cards:
            print(f"\n📱 Card: {card.card_name} (ID: {card.id})")
            print(f"   User ID: {card.user_id}")
            print(f"   Bank Provider ID: {card.bank_provider_id}")
            
            if card.bank_provider:
                print(f"   🏦 Bank Provider: {card.bank_provider.name}")
                print(f"   🏦 Short Name: {card.bank_provider.short_name}")
                
                # Determine bank type like the endpoint does
                bank_type = "BCP"  # Default fallback
                bank_short_name = card.bank_provider.short_name or card.bank_provider.name
                if "DINERS" in bank_short_name.upper():
                    bank_type = "DINERS"
                elif "BCP" in bank_short_name.upper():
                    bank_type = "BCP"
                    
                print(f"   📊 Detected Bank Type: {bank_type}")
            else:
                print(f"   ❌ No bank provider linked!")
        
        # Also check bank providers
        print(f"\n=== ALL BANK PROVIDERS ===")
        providers = db.query(BankProvider).all()
        for provider in providers:
            print(f"🏦 {provider.name} (Short: {provider.short_name}) - ID: {provider.id}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    debug_cards()
