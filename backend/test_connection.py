"""
Script para probar la conexion a MongoDB Atlas
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import MONGO_URL, DB_NAME
from utils.database import client, db


async def test_connection():
    """Test MongoDB connection"""
    print("=" * 50)
    print("PROBANDO CONEXION A MONGODB")
    print("=" * 50)
    print(f"\nURL: {MONGO_URL[:60]}...")
    print(f"Base de datos: {DB_NAME}")
    
    try:
        # Test connection
        await client.admin.command('ping')
        print("\n[OK] Conexion exitosa a MongoDB!")
        
        # List collections
        collections = await db.list_collection_names()
        print(f"\nColecciones en '{DB_NAME}':")
        if collections:
            for coll in collections:
                count = await db[coll].count_documents({})
                print(f"   - {coll}: {count} documentos")
        else:
            print("   (ninguna - la base esta vacia)")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Error de conexion: {e}")
        print("\nSoluciones comunes:")
        print("   1. Verifica que MONGO_URL este correcto en backend/.env")
        print("   2. Asegurate de que la contrasena no tenga caracteres especiales")
        print("   3. Verifica que tu IP este en la lista blanca de MongoDB Atlas")
        print("   4. Revisa que el cluster este activo")
        return False
    finally:
        client.close()


if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
