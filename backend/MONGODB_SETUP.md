# 🍃 Guía de MongoDB para IngresoUNAM

## Opción 1: MongoDB Atlas (Nube - Recomendado)

### Ventajas
- Gratis para siempre (hasta 512MB)
- No necesitas instalar nada
- Accesible desde cualquier lugar
- Backups automáticos

### Pasos

1. **Crear cuenta** en [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)

2. **Crear cluster gratuito:**
   - Elige M0 (FREE)
   - Selecciona tu región más cercana

3. **Configurar acceso:**
   - Crea un usuario de base de datos (guarda la contraseña)
   - Añade IP `0.0.0.0/0` (Allow access from anywhere)

4. **Obtener URL:**
   - Click en "Connect" → "Drivers" → "Python 4.5+"
   - Copia la connection string

5. **Configurar `.env`:**
   ```
   MONGO_URL=mongodb+srv://admin:TU_PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   DB_NAME=ingresounam
   ```

---

## Opción 2: MongoDB Local

### Windows
```powershell
# Descarga el instalador desde:
# https://www.mongodb.com/try/download/community

# O usa winget:
winget install MongoDB.Server

# Iniciar servicio
net start MongoDB
```

### macOS
```bash
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community
```

### Linux
```bash
# Ubuntu/Debian
sudo apt install mongodb
sudo systemctl start mongodb
```

### Configurar `.env` para local:
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=ingresounam
```

---

## 🧪 Verificar conexión

```bash
cd backend
python test_connection.py
```

---

## 🌱 Sembrar datos de prueba

Una vez conectado, ejecuta:

```bash
cd backend
# Primero asegúrate de tener las dependencias
pip install -r requirements.txt

# Luego inicia el servidor
uvicorn server:app --reload

# En otra terminal o con Postman/Insomnia:
curl -X POST http://localhost:8000/api/seed
```

Esto crea:
- 10 materias
- 300 preguntas de ejemplo
- 4 simuladores (uno por área)
- 1 usuario admin: `admin@ingresounam.com` / `admin123`

---

## ⚠️ Solución de problemas

### Error: "Authentication failed"
- Verifica que la contraseña sea correcta
- Si tiene caracteres especiales (`@`, `:`, `/`), codifícalos:
  - `@` → `%40`
  - `:` → `%3A`
  - `/` → `%2F`

### Error: "IP not whitelisted"
- Ve a MongoDB Atlas → Network Access
- Añade tu IP actual o `0.0.0.0/0`

### Error: "SSL/TLS connection failed"
- Añade a la URL: `&ssl=false` (solo para pruebas locales)
- O actualiza certificados: `pip install --upgrade certifi`

---

## 📚 Recursos útiles

- [MongoDB Atlas Docs](https://docs.atlas.mongodb.com/)
- [Motor (Async Python Driver)](https://motor.readthedocs.io/)
- [MongoDB Compass](https://www.mongodb.com/products/compass) - GUI para ver datos
