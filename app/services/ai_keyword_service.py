"""
Service for generating AI-powered keywords using OpenAI.
Provides location-aware keyword generation based on user IP and category.
"""
from typing import List, Dict, Any, Optional
import json
import requests
from sqlalchemy.orm import Session
from fastapi import Request, HTTPException

from app.services.ai_service import AIService
from app.models.user import User
from app.models.category import Category
from app.models.category_keyword import CategoryKeyword
from app.core.config import settings


class AIKeywordService:
    """Service for AI-powered keyword generation"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.ai_service = AIService()
    
    def get_country_from_ip(self, ip_address: str) -> Optional[str]:
        """Get country code from IP address using ipapi.co"""
        if not ip_address or ip_address == "127.0.0.1":
            # For localhost/development, try to detect real IP first
            try:
                public_ip = requests.get("https://api.ipify.org", timeout=3).text.strip()
                if public_ip and public_ip != "127.0.0.1":
                    ip_address = public_ip
                else:
                    # If we can't get public IP, default to Peru for local development
                    return "PE"  # Default to Peru for localhost in Peruvian context
            except:
                return "PE"  # Default to Peru for localhost in Peruvian context
            
        try:
            response = requests.get(
                f"https://ipapi.co/{ip_address}/country/",
                timeout=5
            )
            if response.status_code == 200:
                country = response.text.strip()
                return country if len(country) == 2 else "PE"  # Default to Peru if detection fails
        except (requests.RequestException, ValueError):
            pass
            
        return "PE"  # Fallback to Peru for Peruvian users
    
    def get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        if request.client and request.client.host:
            return request.client.host
        
        # Check common headers for IP
        for header in ['X-Forwarded-For', 'X-Real-IP', 'X-Client-IP']:
            if header in request.headers:
                ips = request.headers[header].split(',')
                return ips[0].strip()
                
        return "127.0.0.1"  # Fallback
    
    def can_generate_ai_keywords(self, user: User) -> bool:
        """Check if user can generate AI keywords based on plan and usage"""
        # Free users cannot use AI keyword generation
        if user.plan_tier.value == "free":
            return False
            
        # Check monthly usage limit (30 times per month)
        if user.ai_keyword_usage_count >= 30:
            return False
            
        return True
    
    def increment_ai_usage(self, user: User) -> None:
        """Increment AI keyword usage counter"""
        from sqlalchemy import func
        from datetime import datetime
        
        # Reset counter if it's a new month - use Python comparison
        needs_reset = (user.ai_keyword_reset_at is None or 
                      user.ai_keyword_reset_at.replace(tzinfo=None) < datetime.utcnow())
        
        if needs_reset:
            user.ai_keyword_usage_count = 0
            user.ai_keyword_reset_at = func.now() + func.make_interval(0, 0, 0, 30)
        
        user.ai_keyword_usage_count += 1
        user.ai_keyword_last_used = func.now()
        # Don't commit here - let the calling method handle the transaction
    
    def generate_category_keywords(
        self, 
        user: User, 
        category: Category, 
        country_code: str,
        count: int = 20
    ) -> List[str]:
        """Generate AI-powered keywords for a category"""
        
        # Get country name from code
        country_names = {
            "PE": "Peru", "US": "United States", "MX": "Mexico", 
            "ES": "Spain", "AR": "Argentina", "CO": "Colombia",
            "CL": "Chile", "BR": "Brazil", "EC": "Ecuador",
            "UY": "Uruguay", "PY": "Paraguay", "BO": "Bolivia",
            "VE": "Venezuela", "CR": "Costa Rica", "PA": "Panama",
            "DO": "Dominican Republic", "GT": "Guatemala", "SV": "El Salvador",
            "HN": "Honduras", "NI": "Nicaragua"
        }
        
        country_name = country_names.get(country_code, "the user's country")
        
        prompt = f"""
You are an expert in financial transaction classification and consumer commerce in {country_name}. Your task is to generate exactly {count} keywords used to categorize transactions under the category "{category.name}".

These keywords will be matched against user bank transaction descriptions. Accuracy is critical — keywords must directly reflect **real merchants in {country_name} whose primary business aligns with the category**.

### OUTPUT FORMAT:
Return only a **JSON array of lowercase strings**, each representing a core merchant name. No extra text.

---

### HARD RULES:

1. ✅ EACH keyword must:
   - Be a **real, active business or service in {country_name}**
   - Match **the core business activity** of the category "{category.name}"
   - Be a merchant users actually pay money to — appears in bank statements

2. ❌ DO NOT include:
   - Businesses **outside the category** context (e.g., banks in hobbies, restaurants in tech)
   - Public locations, parks, plazas, landmarks
   - Generic tags or activity types (e.g., "arte", "pasatiempos", "deportes")
   - Campaign names, store sections, product names (e.g., "saga falabella bicicletas" → ✘)
   - Merchants that do not operate in {country_name}

3. 🧹 CLEAN brand names:
   - Strip all descriptors, prefixes, and suffixes
   - Examples:
     - "Juguetería Tai Loy" → "tai loy"
     - "Phantom Music Store" → "phantom"
     - "Librería Crisol" → "crisol"
     - "Domino's Pizza" → "dominos" (core brand name only, remove "pizza")
     - "Real Plaza Cine" → ✘ — remove "cine"

4. 🧠 ONLY include businesses that users would **specifically associate** with the category "{category.name}":
   - Ask: "Would a user reasonably make a transaction at this merchant **because of their interest in {category.name}**?"

5. Include both international and local brands present in {country_name}.
6. Return {count} lowercase strings in a JSON array. No duplicates.

---

### GOAL:
The list must contain only valid merchant names a user would see in their bank transactions — and all of them must be clearly relevant to the category "{category.name}" based on their **main business purpose**.
        """
        
        try:
            response = self.ai_service.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a localization expert. Generate specific, location-aware business keywords for financial categorization. Respond ONLY with valid JSON arrays."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            if content:
                keywords = json.loads(content)
                if isinstance(keywords, list) and all(isinstance(k, str) for k in keywords):
                    # Clean and process keywords
                    cleaned_keywords = []
                    for keyword in keywords:
                        if keyword.strip():
                            # Remove country-specific suffixes
                            cleaned = keyword.lower().strip()
                            # Remove common country suffixes
                            cleaned = cleaned.replace(' peru', '').replace(' perú', '')
                            cleaned = cleaned.replace(' peru.', '').replace(' perú.', '')
                            cleaned = cleaned.replace(' peru-', '').replace(' perú-', '')
                            cleaned = cleaned.replace(' pe', '').replace(' pe.', '').replace(' pe-', '')
                            cleaned = cleaned.replace(' peruano', '').replace(' peruana', '')
                            
                            # Normalize apostrophes and spaces for better matching
                            # This handles cases where transactions might not have apostrophes or have different spacing
                            cleaned = cleaned.replace("'", "")
                            cleaned = cleaned.replace(" ", "")
                            
                            cleaned = cleaned.strip()
                            
                            # Only add if not empty after cleaning
                            if cleaned:
                                cleaned_keywords.append(cleaned)
                    
                    return cleaned_keywords
                else:
                    raise ValueError("Invalid response format from AI")
            else:
                raise ValueError("Empty response from AI")
                
        except Exception as e:
            # For background tasks, raise a regular exception instead of HTTPException
            raise ValueError(f"Failed to generate AI keywords: {str(e)}")
    
    def generate_and_add_keywords(
        self,
        user: User,
        category: Category,
        request: Request,
        clear_existing: bool = False,
        count: int = 20
    ) -> List[CategoryKeyword]:
        """Generate AI keywords and add them to the category"""
        
        # Check if user can generate AI keywords
        if not self.can_generate_ai_keywords(user):
            raise HTTPException(
                status_code=403,
                detail="AI keyword generation not available for your plan or monthly limit exceeded"
            )
        
        # Check if category already has AI-generated keywords
        if category.ai_seeded_at is not None:
            raise HTTPException(
                status_code=400,
                detail="AI keywords have already been generated for this category"
            )
        
        # Check if this is a default category (user should not seed default categories)
        if category.is_default:
            raise HTTPException(
                status_code=400,
                detail="Cannot generate AI keywords for default categories. Default categories already come with pre-defined keywords."
            )
        
        # Clear existing keywords if requested
        if clear_existing:
            from app.models.category_keyword import CategoryKeyword
            # Delete all existing keywords for this category
            try:
                self.db.query(CategoryKeyword).filter(
                    CategoryKeyword.category_id == str(category.id),
                    CategoryKeyword.user_id == str(user.id)
                ).delete()
                self.db.commit()
            except Exception as e:
                self.db.rollback()
                print(f"Error clearing existing keywords: {e}")
                # Continue without clearing rather than failing completely
        
        # Get client IP and country
        client_ip = self.get_client_ip(request)
        country_code = self.get_country_from_ip(client_ip)
        
        # Generate keywords
        try:
            keywords = self.generate_category_keywords(user, category, country_code, count)
            print(f"Generated {len(keywords)} keywords: {keywords}")
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate keywords: {str(e)}"
            )
        
        # Add keywords to category
        added_keywords = []
        for keyword_text in keywords:
            try:
                keyword = category.add_keyword(
                    keyword_text=keyword_text,
                    description=f"AI-generated keyword for {category.name}"
                )
                self.db.add(keyword)
                added_keywords.append(keyword)
            except ValueError:
                # Keyword already exists, skip
                continue
            except Exception as e:
                # Log any other errors for debugging
                print(f"Error adding keyword '{keyword_text}': {e}")
                continue
        
        # Update category and user usage
        from sqlalchemy import func
        category.ai_seeded_at = func.now()
        self.increment_ai_usage(user)
        
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to commit changes to database: {str(e)}"
            )
        
        return added_keywords
    
    def get_ai_usage_stats(self, user: User) -> Dict[str, Any]:
        """Get AI keyword usage statistics for user"""
        from sqlalchemy import func
        from datetime import datetime
        
        # Check if reset is needed - refresh user to get current database state
        self.db.refresh(user)
        
        # Use Python comparison for datetime objects
        needs_reset = (user.ai_keyword_reset_at is None or 
                      user.ai_keyword_reset_at.replace(tzinfo=None) < datetime.utcnow())
        
        if needs_reset:
            user.ai_keyword_usage_count = 0
            user.ai_keyword_reset_at = func.now() + func.make_interval(0, 0, 0, 30)
            self.db.commit()
        
        return {
            "current_usage": user.ai_keyword_usage_count,
            "monthly_limit": 30,
            "last_used": user.ai_keyword_last_used,
            "reset_at": user.ai_keyword_reset_at,
            "remaining": 30 - user.ai_keyword_usage_count,
            "plan_tier": user.plan_tier.value
        }