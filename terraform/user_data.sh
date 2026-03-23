#!/bin/bash
set -e
exec > >(tee /var/log/user-data.log | logger -t user-data -s 2>/dev/console) 2>&1

echo "=== Booting at $(date) ==="

# System update
apt-get update -y && apt-get upgrade -y

# Install Docker
apt-get install -y ca-certificates curl gnupg nginx
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable docker && systemctl start docker
usermod -aG docker ubuntu

# App directory
mkdir -p /opt/rental
chown ubuntu:ubuntu /opt/rental

# Write docker-compose with injected secrets
cat > /opt/rental/docker-compose.yml << COMPOSE_EOF
version: '3.8'

services:
  postgres:
    image: postgres:15
    restart: unless-stopped
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${db_password}
      POSTGRES_DB: rental_platform
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init-db.sql
    networks:
      - rental-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d rental_platform"]
      interval: 10s
      timeout: 5s
      retries: 5

  api-gateway:
    build: ./api-gateway
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - USERS_SERVICE_URL=http://users-service:5001
      - LISTINGS_SERVICE_URL=http://listings-service:5002
      - BOOKINGS_SERVICE_URL=http://bookings-service:5003
      - PAYMENTS_SERVICE_URL=http://payments-service:5004
      - REVIEWS_SERVICE_URL=http://reviews-service:5005
    depends_on: [users-service, listings-service, bookings-service, payments-service, reviews-service]
    networks:
      - rental-network

  users-service:
    build: ./users-service
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://postgres:${db_password}@postgres:5432/users_db
      - JWT_SECRET=${jwt_secret}
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - rental-network

  listings-service:
    build: ./listings-service
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://postgres:${db_password}@postgres:5432/listings_db
      - JWT_SECRET=${jwt_secret}
      - USERS_SERVICE_URL=http://users-service:5001
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - rental-network

  bookings-service:
    build: ./bookings-service
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://postgres:${db_password}@postgres:5432/bookings_db
      - JWT_SECRET=${jwt_secret}
      - LISTINGS_SERVICE_URL=http://listings-service:5002
      - PAYMENTS_SERVICE_URL=http://payments-service:5004
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - rental-network

  payments-service:
    build: ./payments-service
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://postgres:${db_password}@postgres:5432/payments_db
      - JWT_SECRET=${jwt_secret}
      - BOOKINGS_SERVICE_URL=http://bookings-service:5003
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - rental-network

  reviews-service:
    build: ./reviews-service
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://postgres:${db_password}@postgres:5432/reviews_db
      - JWT_SECRET=${jwt_secret}
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - rental-network

networks:
  rental-network:
    driver: bridge

volumes:
  postgres-data:
COMPOSE_EOF

# Deploy script for future re-deploys
cat > /opt/rental/deploy.sh << 'DEPLOY_EOF'
#!/bin/bash
set -e
cd /opt/rental
docker compose down --remove-orphans || true
docker compose build --no-cache
docker compose up -d
docker compose ps
DEPLOY_EOF
chmod +x /opt/rental/deploy.sh

# Nginx — serve frontend + proxy API
cat > /etc/nginx/sites-available/rental << 'NGINX_EOF'
server {
    listen 80;
    server_name _;

    root /opt/rental/frontend;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
NGINX_EOF

ln -sf /etc/nginx/sites-available/rental /etc/nginx/sites-enabled/rental
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx && systemctl enable nginx

# Systemd — auto-start on reboot
cat > /etc/systemd/system/rental-platform.service << 'SERVICE_EOF'
[Unit]
Description=Rental Platform
Requires=docker.service
After=docker.service network.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/rental
ExecStart=/usr/bin/docker compose up -d --build
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl daemon-reload
systemctl enable rental-platform

echo "=== Setup complete at $(date) ==="