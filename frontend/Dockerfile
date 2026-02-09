# Build stage
FROM node:18-alpine AS build

WORKDIR /app

# Copiar package files primero para caché
COPY package*.json ./

# Instalar dependencias
RUN npm ci --only=production

# Copiar código fuente
COPY . .

# Construir la aplicación
RUN npm run build

# Production stage
FROM nginx:alpine

# Copiar build desde stage anterior
COPY --from=build /app/build /usr/share/nginx/html

# Copiar configuración de nginx
COPY nginx.conf /etc/nginx/nginx.conf

# Exponer puerto
EXPOSE 80

# Iniciar nginx
CMD ["nginx", "-g", "daemon off;"]