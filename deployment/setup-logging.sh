#!/bin/bash
# PersonalCFO Logging Setup Script

APP_USER="personalcfo"
LOG_DIR="/var/log/personalcfo"

echo "📝 Setting up logging for PersonalCFO..."

# Create log directory
sudo mkdir -p $LOG_DIR
sudo chown $APP_USER:$APP_USER $LOG_DIR
sudo chmod 755 $LOG_DIR

# Create log rotation configuration
sudo tee /etc/logrotate.d/personalcfo > /dev/null <<EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $APP_USER $APP_USER
    postrotate
        systemctl reload personalcfo > /dev/null 2>&1 || true
        systemctl reload personalcfo-celery > /dev/null 2>&1 || true
    endscript
}
EOF

# Create rsyslog configuration for structured logging
sudo tee /etc/rsyslog.d/50-personalcfo.conf > /dev/null <<EOF
# PersonalCFO application logs
:programname,isequal,"personalcfo" $LOG_DIR/app.log
:programname,isequal,"personalcfo-celery" $LOG_DIR/celery.log

# Audit logs (separate file for security events)
:msg,contains,"AUDIT:" $LOG_DIR/audit.log
& stop
EOF

# Restart rsyslog
sudo systemctl restart rsyslog

echo "✅ Logging configuration completed!"
echo "📁 Log files will be stored in: $LOG_DIR"
echo "🔄 Log rotation configured for 30 days"
EOF