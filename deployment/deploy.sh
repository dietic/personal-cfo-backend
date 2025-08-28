#!/bin/bash
set -e

# PersonalCFO Backend Deployment Script for EC2
# This script deploys the backend application to a production EC2 instance

# Configuration
APP_NAME="personalcfo"
APP_USER="personalcfo"
APP_DIR="/opt/personalcfo"
REPO_URL="https://github.com/your-username/personal-cfo-backend.git"
PYTHON_VERSION="3.12"

echo "🚀 Starting PersonalCFO Backend Deployment..."

# Update system packages
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install required system packages
echo "📦 Installing system dependencies..."
sudo apt install -y \
    python3.12 \
    python3.12-venv \
    python3-pip \
    postgresql-client \
    redis-tools \
    nginx \
    git \
    curl \
    supervisor \
    htop

# Create application user if it doesn't exist
if ! id "$APP_USER" &>/dev/null; then
    echo "👤 Creating application user: $APP_USER"
    sudo useradd --system --home-dir $APP_DIR --shell /bin/bash $APP_USER
fi

# Create application directory
echo "📁 Setting up application directory..."
sudo mkdir -p $APP_DIR
sudo chown $APP_USER:$APP_USER $APP_DIR

# Clone or update repository
echo "📥 Deploying application code..."
if [ -d "$APP_DIR/.git" ]; then
    echo "📥 Updating existing repository..."
    sudo -u $APP_USER git -C $APP_DIR pull origin main
else
    echo "📥 Cloning repository..."
    sudo -u $APP_USER git clone $REPO_URL $APP_DIR
fi

# Create Python virtual environment
echo "🐍 Setting up Python virtual environment..."
sudo -u $APP_USER python3.12 -m venv $APP_DIR/venv

# Install Python dependencies
echo "📦 Installing Python dependencies..."
sudo -u $APP_USER $APP_DIR/venv/bin/pip install --upgrade pip
sudo -u $APP_USER $APP_DIR/venv/bin/pip install -r $APP_DIR/requirements.txt

# Create uploads directory
echo "📁 Creating uploads directory..."
sudo -u $APP_USER mkdir -p $APP_DIR/uploads

# Copy environment configuration
if [ ! -f "$APP_DIR/.env" ]; then
    echo "⚙️ Setting up environment configuration..."
    sudo -u $APP_USER cp $APP_DIR/.env.production $APP_DIR/.env
    echo "❗ IMPORTANT: Edit $APP_DIR/.env with your production values!"
fi

# Create log directory
echo "📝 Setting up logging..."
sudo mkdir -p /var/log/personalcfo
sudo chown $APP_USER:$APP_USER /var/log/personalcfo

# Run database migrations
echo "🗄️ Running database migrations..."
cd $APP_DIR
sudo -u $APP_USER $APP_DIR/venv/bin/alembic upgrade head

# Install and configure systemd services
echo "🔧 Installing systemd services..."
sudo cp $APP_DIR/deployment/personalcfo.service /etc/systemd/system/
sudo cp $APP_DIR/deployment/personalcfo-celery.service /etc/systemd/system/

# Reload systemd and enable services
sudo systemctl daemon-reload
sudo systemctl enable personalcfo
sudo systemctl enable personalcfo-celery

# Install Nginx configuration
echo "🌐 Configuring Nginx..."
sudo cp $APP_DIR/deployment/nginx.conf /etc/nginx/sites-available/personalcfo
sudo ln -sf /etc/nginx/sites-available/personalcfo /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Restart services
echo "🔄 Starting services..."
sudo systemctl restart personalcfo
sudo systemctl restart personalcfo-celery
sudo systemctl reload nginx

# Check service status
echo "✅ Checking service status..."
sudo systemctl status personalcfo --no-pager
sudo systemctl status personalcfo-celery --no-pager
sudo systemctl status nginx --no-pager

echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "📝 Next steps:"
echo "1. Edit $APP_DIR/.env with your production configuration"
echo "2. Restart services: sudo systemctl restart personalcfo personalcfo-celery"
echo "3. Check logs: sudo journalctl -u personalcfo -f"
echo "4. Set up SSL certificate with certbot (recommended)"
echo ""
echo "🔗 Your API will be available at: http://your-domain.com/api/v1"
echo "📊 API docs available at: http://your-domain.com/docs"