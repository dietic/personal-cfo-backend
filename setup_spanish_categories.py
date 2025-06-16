#!/usr/bin/env python3

import requests
import json

def get_auth_token():
    """Get authentication token"""
    login_data = {
        "email": "dierios93@gmail.com",
        "password": "Lima2023$"
    }
    
    response = requests.post("http://localhost:8000/api/v1/auth/login", json=login_data)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Login failed: {response.text}")

def create_category(token, name, color):
    """Create a new category"""
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "name": name,
        "color": color,
        "is_active": True
    }
    
    response = requests.post("http://localhost:8000/api/v1/categories/", headers=headers, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to create category {name}: {response.text}")
        return None

def add_keywords_to_category(token, category_id, keywords):
    """Add multiple keywords to a category"""
    headers = {"Authorization": f"Bearer {token}"}
    
    for keyword in keywords:
        data = {
            "keyword": keyword,
            "category_id": category_id,
            "description": f"Palabra clave para categorización automática"
        }
        
        response = requests.post("http://localhost:8000/api/v1/keywords/", headers=headers, json=data)
        if response.status_code == 200:
            print(f"  ✓ Added keyword: {keyword}")
        else:
            print(f"  ✗ Failed to add keyword {keyword}: {response.text}")

def deactivate_old_categories(token):
    """Deactivate existing categories"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get current categories
    response = requests.get("http://localhost:8000/api/v1/categories/", headers=headers)
    if response.status_code == 200:
        categories = response.json()
        for category in categories:
            # Update category to inactive
            update_data = {"is_active": False}
            update_response = requests.put(
                f"http://localhost:8000/api/v1/categories/{category['id']}", 
                headers=headers, 
                json=update_data
            )
            if update_response.status_code == 200:
                print(f"  ✓ Deactivated: {category['name']}")

def main():
    """Replace English categories with Spanish ones"""
    
    print("Starting Spanish categories setup...")
    
    # Spanish categories with 15 keywords each
    spanish_categories = {
        'Alimentación': {
            'color': '#FF6B6B',
            'keywords': [
                'restaurante', 'comida', 'almuerzo', 'desayuno', 'cena', 'café', 'cafetería',
                'pizza', 'hamburguesa', 'supermercado', 'mercado', 'panadería', 'carnicería',
                'delivery', 'pedido'
            ]
        },
        'Transporte': {
            'color': '#4ECDC4',
            'keywords': [
                'gasolina', 'combustible', 'uber', 'taxi', 'bus', 'metro', 'tren',
                'estacionamiento', 'peaje', 'auto', 'coche', 'vehículo', 'transporte',
                'bicicleta', 'motocicleta'
            ]
        },
        'Compras': {
            'color': '#45B7D1',
            'keywords': [
                'tienda', 'centro comercial', 'compra', 'retail', 'ropa', 'vestimenta',
                'amazon', 'mercadolibre', 'shopping', 'boutique', 'outlet', 'farmacia',
                'droguería', 'librería', 'juguetería'
            ]
        },
        'Entretenimiento': {
            'color': '#96CEB4',
            'keywords': [
                'cine', 'película', 'teatro', 'concierto', 'juego', 'spotify', 'netflix',
                'entretenimiento', 'diversión', 'ocio', 'youtube', 'streaming', 'música',
                'deporte', 'gimnasio'
            ]
        },
        'Servicios Públicos': {
            'color': '#FFEAA7',
            'keywords': [
                'electricidad', 'luz', 'agua', 'gas', 'internet', 'teléfono', 'móvil',
                'celular', 'servicio', 'factura', 'cable', 'wifi', 'calefacción',
                'basura', 'alcantarillado'
            ]
        },
        'Salud': {
            'color': '#DDA0DD',
            'keywords': [
                'doctor', 'médico', 'hospital', 'clínica', 'farmacia', 'medicina',
                'dentista', 'consulta', 'receta', 'seguro médico', 'copago',
                'urgencias', 'cirugía', 'terapia', 'laboratorio'
            ]
        },
        'Vivienda': {
            'color': '#F39C12',
            'keywords': [
                'alquiler', 'arriendo', 'hipoteca', 'casa', 'apartamento', 'propiedad',
                'mantenimiento', 'reparación', 'seguro hogar', 'administración',
                'inquilino', 'propietario', 'inmobiliaria', 'mudanza', 'muebles'
            ]
        },
        'Educación': {
            'color': '#9B59B6',
            'keywords': [
                'colegio', 'escuela', 'universidad', 'instituto', 'curso', 'clase',
                'matrícula', 'pensión', 'libros', 'material escolar', 'uniforme',
                'transporte escolar', 'profesor', 'tutor', 'capacitación'
            ]
        },
        'Finanzas': {
            'color': '#E74C3C',
            'keywords': [
                'banco', 'transferencia', 'comisión', 'tarjeta crédito', 'préstamo',
                'inversión', 'ahorro', 'interés', 'cuota', 'pago', 'débito',
                'cajero', 'atm', 'financiamiento', 'crédito'
            ]
        },
        'Impuestos y Legal': {
            'color': '#34495E',
            'keywords': [
                'impuesto', 'tax', 'renta', 'iva', 'patente', 'permiso',
                'notario', 'abogado', 'legal', 'multa', 'infracción',
                'registro', 'trámite', 'gobierno', 'municipal'
            ]
        }
    }
    
    try:
        print("Getting authentication token...")
        token = get_auth_token()
        print("Token obtained successfully")
        
        print("Deactivating old categories...")
        deactivate_old_categories(token)
        
        print("Creating Spanish categories...")
        for category_name, category_info in spanish_categories.items():
            print(f"\nCreating category: {category_name}")
            category = create_category(token, category_name, category_info['color'])
            
            if category:
                print(f"  Adding {len(category_info['keywords'])} keywords...")
                add_keywords_to_category(token, category['id'], category_info['keywords'])
            else:
                print(f"  Failed to create category {category_name}")
        
        print("\n✅ Spanish categories setup completed!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
