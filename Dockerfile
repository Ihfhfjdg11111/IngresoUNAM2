# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Copiar package.json
COPY package*.json ./
RUN npm ci --only=production

# Copiar código y compilar
COPY . .
RUN npm run build

# Production stage con Nginx
FROM nginx:alpine

# Copiar build de React
COPY --from=builder /app/build /usr/share/nginx/html

# Copiar configuración de Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
