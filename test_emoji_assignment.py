#!/usr/bin/env python3
"""
Test script to verify emoji assignment functionality
"""

import sys
sys.path.append('.')

from app.services.category_service import _get_emoji_for_category

def test_emoji_assignment():
    """Test various category names to ensure appropriate emoji assignment"""
    
    test_cases = [
        # Default categories
        ("Alimentación", "🍕"),
        ("Comida", "🍕"),
        ("Restaurante", "🍕"),
        ("Salud", "🏥"),
        ("Hospital", "🏥"),
        ("Transporte", "🚗"),
        ("Auto", "🚗"),
        ("Vivienda", "🏠"),
        ("Casa", "🏠"),
        ("Otros", "📦"),
        
        # Additional categories
        ("Compras", "🛍️"),
        ("Shopping", "🛍️"),
        ("Entretenimiento", "🎬"),
        ("Cine", "🎬"),
        ("Servicios Públicos", "💡"),
        ("Electricidad", "💡"),
        
        # Common expense types
        ("Educación", "🎓"),
        ("Universidad", "🎓"),
        ("Viajes", "✈️"),
        ("Vacaciones", "✈️"),
        ("Deporte", "⚽"),
        ("Gimnasio", "⚽"),
        ("Tecnología", "💻"),
        ("Computadora", "💻"),
        ("Ropa", "👕"),
        ("Moda", "👕"),
        ("Bebidas", "🍷"),
        ("Café", "☕"),
        
        # Edge cases
        ("Sin categoría", "❓"),
        ("Unknown Category", "📋"),
        ("Random Name", "📋"),
    ]
    
    print("Testing emoji assignment for various category names:")
    print("=" * 60)
    
    all_passed = True
    
    for category_name, expected_emoji in test_cases:
        actual_emoji = _get_emoji_for_category(category_name)
        status = "✅" if actual_emoji == expected_emoji else "❌"
        
        if actual_emoji != expected_emoji:
            all_passed = False
            
        print(f"{status} '{category_name}' -> {actual_emoji} (expected: {expected_emoji})")
    
    print("=" * 60)
    if all_passed:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
    
    return all_passed

if __name__ == "__main__":
    test_emoji_assignment()