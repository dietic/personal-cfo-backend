from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import uuid
import re

from app.models.merchant import Merchant
from app.core.exceptions import NotFoundError

class MerchantService:
    
    @staticmethod
    def get_user_merchants(db: Session, user_id: uuid.UUID) -> List[Merchant]:
        """Get all merchants for a user"""
        return db.query(Merchant).filter(Merchant.user_id == user_id).all()
    
    @staticmethod
    def get_merchant_names(db: Session, user_id: uuid.UUID) -> List[str]:
        """Get list of canonical merchant names for a user"""
        merchants = db.query(Merchant.canonical_name).filter(Merchant.user_id == user_id).all()
        return [m.canonical_name for m in merchants]
    
    @staticmethod
    def merchant_exists(db: Session, user_id: uuid.UUID, merchant_name: str) -> bool:
        """Check if a merchant already exists for the user"""
        if not merchant_name:
            return False
            
        # Check if canonical name matches (case insensitive)
        merchant = db.query(Merchant).filter(
            Merchant.user_id == user_id,
            func.lower(Merchant.canonical_name) == func.lower(merchant_name.strip())
        ).first()
        
        return merchant is not None
    
    @staticmethod
    def create_merchant(db: Session, user_id: uuid.UUID, canonical_name: str, 
                       category: Optional[str] = None) -> Merchant:
        """Create a new merchant"""
        # Clean and standardize the canonical name
        canonical_name = MerchantService._standardize_merchant_name(canonical_name)
        
        merchant = Merchant(
            user_id=user_id,
            canonical_name=canonical_name,
            display_name=canonical_name,
            category=category,
            transaction_count="1"
        )
        
        db.add(merchant)
        return merchant
    
    @staticmethod
    def _standardize_merchant_name(name: str) -> str:
        """Standardize a merchant name to canonical form"""
        if not name:
            return "Unknown Merchant"
        
        # Convert to title case
        name = name.strip().title()
        
        # Remove common suffixes and location details
        patterns_to_remove = [
            r'\s+LIMA\s*PE.*$', r'\s+PE.*$', r'\s*\d+.*$', 
            r'\s*S\.A\.?C\.?I\.?.*$', r'\s*S\.?A\.?.*$',
            r'\s*E\.?I\.?R\.?L\.?.*$', r'\s*S\.?A\.?C\.?.*$',
            r'\s*S\.?R\.?L\.?.*$', r'\s*INC\.?.*$', r'\s*LLC\.?.*$'
        ]
        
        for pattern in patterns_to_remove:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)
        
        # Remove extra whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        
        # Common brand standardizations
        brand_mappings = {
            r'^MAKRO\s+': 'Makro',
            r'^METRO\s+': 'Metro',
            r'^WONG\s+': 'Wong',
            r'^RIPLEY\s+': 'Ripley',
            r'^FALABELLA\s+': 'Falabella',
            r'^TOTTUS\s+': 'Tottus',
            r'^PLAZA\s+VEA\s+': 'Plaza Vea',
            r'^VIVANDA\s+': 'Vivanda',
            r'^OPENAI\s+': 'OpenAI',
            r'STEAM': 'Steam',
            r'^AMAZON\s+': 'Amazon',
            r'^NETFLIX\s+': 'Netflix',
            r'DIRECTV': 'DirectTV',
            r'DIRECT TV': 'DirectTV',
            r'CAD DIRECTV': 'DirectTV',
        }
        
        for pattern, replacement in brand_mappings.items():
            if re.search(pattern, name, re.IGNORECASE):
                name = replacement
                break
        
        return name
    
    @staticmethod
    def get_merchants_for_ai_prompt(db: Session, user_id: uuid.UUID) -> str:
        """Get formatted merchant list for AI prompt"""
        merchants = MerchantService.get_user_merchants(db, user_id)
        
        if not merchants:
            return "No existing merchants found. AI should standardize new merchant names using common brand names."
        
        merchant_list = []
        for merchant in merchants:
            merchant_list.append(f"- {merchant.canonical_name}")
        
        return "\n".join(merchant_list)
    
    @staticmethod
    def process_ai_merchant(db: Session, user_id: uuid.UUID, ai_merchant_name: str, 
                           category: Optional[str] = None):
        """Process a merchant name returned by AI - add to database if not exists"""
        if not ai_merchant_name or ai_merchant_name.strip() == "":
            return
            
        # Standardize the AI-provided merchant name
        standardized_name = MerchantService._standardize_merchant_name(ai_merchant_name)
        
        # Check if merchant already exists
        if not MerchantService.merchant_exists(db, user_id, standardized_name):
            # Create new merchant
            MerchantService.create_merchant(db, user_id, standardized_name, category)
            db.commit()
            print(f"✅ Added new merchant: {standardized_name}")
        else:
            # Update transaction count for existing merchant
            merchant = db.query(Merchant).filter(
                Merchant.user_id == user_id,
                func.lower(Merchant.canonical_name) == func.lower(standardized_name)
            ).first()
            if merchant:
                merchant.transaction_count = str(int(merchant.transaction_count or "0") + 1)
                db.commit()
                print(f"✅ Updated transaction count for: {standardized_name}")

    @staticmethod
    def learn_from_transaction(db: Session, user_id: uuid.UUID, raw_merchant: str, 
                              standardized_merchant: str, category: Optional[str] = None):
        """
        Learn from a transaction to build merchant registry with categories
        This processes the AI-standardized merchant and adds/updates it in the database
        """
        if not standardized_merchant or standardized_merchant.strip() == "":
            return
            
        # Process the AI-provided merchant name
        MerchantService.process_ai_merchant(db, user_id, standardized_merchant, category)