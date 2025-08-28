# PersonalCFO Backend Deployment Guide

This directory contains all the necessary files to deploy the PersonalCFO backend to an EC2 instance.

## Quick Start

1. **Launch EC2 Instance**
   - Ubuntu 22.04 LTS
   - t3.small or larger
   - Security groups configured for HTTP/HTTPS

2. **Deploy Application**
   ```bash
   # On your EC2 instance
   cd /tmp
   git clone https://github.com/your-username/personal-cfo-backend.git
   cd personal-cfo-backend/deployment
   sudo ./deploy.sh
   ```

3. **Configure Environment**
   ```bash
   sudo nano /opt/personalcfo/.env
   # Update all production values (DATABASE_URL, REDIS_URL, API keys, etc.)
   ```

4. **Initialize Database**
   ```bash
   sudo -u personalcfo /opt/personalcfo/deployment/init-database.sh
   ```

5. **Restart Services**
   ```bash
   sudo systemctl restart personalcfo personalcfo-celery nginx
   ```

## Files Included

- `deploy.sh` - Main deployment script
- `personalcfo.service` - SystemD service for FastAPI backend
- `personalcfo-celery.service` - SystemD service for Celery workers
- `nginx.conf` - Nginx reverse proxy configuration
- `setup-logging.sh` - Logging configuration script
- `init-database.sh` - Database initialization script
- `.env.production` - Production environment template

## Service Management

```bash
# Check status
sudo systemctl status personalcfo personalcfo-celery nginx

# View logs
sudo journalctl -u personalcfo -f
sudo journalctl -u personalcfo-celery -f

# Restart services
sudo systemctl restart personalcfo
sudo systemctl restart personalcfo-celery
sudo systemctl reload nginx
```

## SSL Setup (Recommended)

After deployment, set up SSL with Let's Encrypt:

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d api.personal-cfo.io

# Update DNS record to point to your EC2 instance
# Enable HTTPS configuration in nginx.conf
```

## Monitoring

- Application logs: `/var/log/personalcfo/`
- Nginx logs: `/var/log/nginx/`
- System logs: `sudo journalctl -u personalcfo`

## Troubleshooting

1. **Service won't start**
   - Check environment variables in `/opt/personalcfo/.env`
   - Verify database connectivity
   - Check logs: `sudo journalctl -u personalcfo -n 50`

2. **Database connection issues**
   - Verify RDS security groups allow connections
   - Test connection manually: `psql -h your-rds-endpoint -U personalcfo -d personalcfo`

3. **Redis connection issues**
   - Verify ElastiCache security groups
   - Test connection: `redis-cli -h your-elasticache-endpoint ping`

## Performance Tuning

For production workloads, consider:
- Increasing Uvicorn workers in `personalcfo.service`
- Scaling Celery workers based on load
- Using a larger EC2 instance type
- Setting up auto-scaling groups
- Implementing CloudWatch monitoring