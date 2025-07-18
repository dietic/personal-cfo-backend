"""
Service for managing category keywords for users.
Provides CRUD operations for user-defined keywords that categorize transactions.
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.category_keyword import CategoryKeyword
from app.models.category import Category
from app.models.user import User


class KeywordService:
    """Service for managing category keywords"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def get_user_keywords(self, user_id: str) -> List[CategoryKeyword]:
        """Get all keywords for a user"""
        return self.db.query(CategoryKeyword).filter(
            CategoryKeyword.user_id == user_id
        ).all()
    
    def get_keywords_by_category(self, user_id: str, category_id: str) -> List[CategoryKeyword]:
        """Get all keywords for a specific category"""
        return self.db.query(CategoryKeyword).filter(
            and_(
                CategoryKeyword.user_id == user_id,
                CategoryKeyword.category_id == category_id
            )
        ).all()
    
    def add_keyword(self, user_id: str, category_id: str, keyword: str, description: str = None) -> CategoryKeyword:
        """Add a new keyword to a category"""
        # Check if keyword already exists for this user and category
        existing = self.db.query(CategoryKeyword).filter(
            and_(
                CategoryKeyword.user_id == user_id,
                CategoryKeyword.category_id == category_id,
                CategoryKeyword.keyword == keyword.lower().strip()
            )
        ).first()
        
        if existing:
            raise ValueError(f"Keyword '{keyword}' already exists for this category")
        
        # Verify category belongs to user
        category = self.db.query(Category).filter(
            and_(
                Category.id == category_id,
                Category.user_id == user_id
            )
        ).first()
        
        if not category:
            raise ValueError("Category not found or doesn't belong to user")
        
        new_keyword = CategoryKeyword(
            user_id=user_id,
            category_id=category_id,
            keyword=keyword.lower().strip(),
            description=description
        )
        
        self.db.add(new_keyword)
        self.db.commit()
        self.db.refresh(new_keyword)
        
        return new_keyword
    
    def remove_keyword(self, user_id: str, keyword_id: str) -> bool:
        """Remove a keyword by ID"""
        keyword = self.db.query(CategoryKeyword).filter(
            and_(
                CategoryKeyword.id == keyword_id,
                CategoryKeyword.user_id == user_id
            )
        ).first()
        
        if not keyword:
            return False
        
        self.db.delete(keyword)
        self.db.commit()
        return True
    
    def update_keyword(self, user_id: str, keyword_id: str, keyword_text: str = None, description: str = None) -> Optional[CategoryKeyword]:
        """Update a keyword"""
        keyword = self.db.query(CategoryKeyword).filter(
            and_(
                CategoryKeyword.id == keyword_id,
                CategoryKeyword.user_id == user_id
            )
        ).first()
        
        if not keyword:
            return None
        
        if keyword_text is not None:
            # Check if new keyword text conflicts with existing keywords
            existing = self.db.query(CategoryKeyword).filter(
                and_(
                    CategoryKeyword.user_id == user_id,
                    CategoryKeyword.category_id == keyword.category_id,
                    CategoryKeyword.keyword == keyword_text.lower().strip(),
                    CategoryKeyword.id != keyword_id
                )
            ).first()
            
            if existing:
                raise ValueError(f"Keyword '{keyword_text}' already exists for this category")
            
            keyword.keyword = keyword_text.lower().strip()
        
        if description is not None:
            keyword.description = description
        
        self.db.commit()
        self.db.refresh(keyword)
        
        return keyword
    
    def get_keyword_by_id(self, user_id: str, keyword_id: str) -> Optional[CategoryKeyword]:
        """Get a specific keyword by ID"""
        return self.db.query(CategoryKeyword).filter(
            and_(
                CategoryKeyword.id == keyword_id,
                CategoryKeyword.user_id == user_id
            )
        ).first()
    
    def categorize_transaction(self, user_id: str, transaction_description: str) -> Optional[str]:
        """
        Categorize a transaction based on user's keywords.
        Returns category_id if a match is found, None otherwise.
        """
        # Get all user keywords
        keywords = self.get_user_keywords(user_id)
        
        if not keywords:
            return None
        
        transaction_desc_lower = transaction_description.lower()
        
        # Simple keyword matching - check if any keyword appears in transaction description
        for keyword_obj in keywords:
            if keyword_obj.keyword in transaction_desc_lower:
                return keyword_obj.category_id
        
        return None
    
    def get_keywords_summary(self, user_id: str) -> Dict[str, Any]:
        """Get a summary of keywords grouped by categories"""
        keywords = self.get_user_keywords(user_id)
        
        # Group by category
        summary = {}
        for keyword in keywords:
            category_name = keyword.category.name if keyword.category else "Unknown"
            if category_name not in summary:
                summary[category_name] = {
                    'category_id': keyword.category_id,
                    'category_name': category_name,
                    'keywords': []
                }
            
            summary[category_name]['keywords'].append({
                'id': keyword.id,
                'keyword': keyword.keyword,
                'description': keyword.description,
                'created_at': keyword.created_at
            })
        
        return summary
    
    def seed_default_keywords(self, user_id: str) -> None:
        """Seed default keywords for a new user with 15 keywords per category"""
        # Get user's categories
        categories = self.db.query(Category).filter(Category.user_id == user_id).all()
        
        # Default keywords mapping - 15 keywords per category in Spanish
        default_keywords = {
            'Alimentación': [
                'restaurante', 'comida', 'almuerzo', 'desayuno', 'cena', 'café', 'cafetería',
                'pizza', 'hamburguesa', 'supermercado', 'mercado', 'panadería', 'carnicería',
                'delivery', 'pedido'
            ],
            'Transporte': [
                'gasolina', 'combustible', 'uber', 'taxi', 'bus', 'metro', 'tren',
                'estacionamiento', 'peaje', 'auto', 'coche', 'vehículo', 'transporte',
                'bicicleta', 'motocicleta'
            ],
            'Compras': [
                'tienda', 'centro comercial', 'compra', 'retail', 'ropa', 'vestimenta',
                'amazon', 'mercadolibre', 'shopping', 'boutique', 'outlet', 'farmacia',
                'droguería', 'librería', 'juguetería'
            ],
            'Entretenimiento': [
                'cine', 'película', 'teatro', 'concierto', 'juego', 'spotify', 'netflix',
                'entretenimiento', 'diversión', 'ocio', 'youtube', 'streaming', 'música',
                'deporte', 'gimnasio'
            ],
            'Servicios Públicos': [
                'electricidad', 'luz', 'agua', 'gas', 'internet', 'teléfono', 'móvil',
                'celular', 'servicio', 'factura', 'cable', 'wifi', 'calefacción',
                'basura', 'alcantarillado'
            ],
            'Salud': [
                'doctor', 'médico', 'hospital', 'clínica', 'farmacia', 'medicina',
                'dentista', 'consulta', 'receta', 'seguro médico', 'copago',
                'urgencias', 'cirugía', 'terapia', 'laboratorio'
            ],
            'Vivienda': [
                'alquiler', 'arriendo', 'hipoteca', 'casa', 'apartamento', 'propiedad',
                'mantenimiento', 'reparación', 'seguro hogar', 'administración',
                'inquilino', 'propietario', 'inmobiliaria', 'mudanza', 'muebles'
            ]
        }
        
        for category in categories:
            if category.name in default_keywords:
                keywords_to_add = default_keywords[category.name]
                
                for keyword_text in keywords_to_add:
                    try:
                        self.add_keyword(
                            user_id=user_id,
                            category_id=str(category.id),
                            keyword=keyword_text,
                            description=f"Palabra clave por defecto para {category.name}"
                        )
                    except ValueError:
                        # Keyword already exists, skip
                        continue
