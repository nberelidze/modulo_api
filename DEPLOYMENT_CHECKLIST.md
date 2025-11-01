# Django LIMS Proxy API - Production Deployment Checklist

## 📋 Pre-Deployment Preparation

### 🔧 Environment Setup
- [ ] **Python Version**: Ensure Python 3.12+ is installed on production server
- [ ] **Virtual Environment**: Create and activate virtual environment
  ```bash
  python3 -m venv /path/to/venv
  source /path/to/venv/bin/activate
  ```
- [ ] **Dependencies**: Install all requirements
  ```bash
  uv sync  # or pip install -r requirements.txt
  ```

### 🗄️ Database Configuration
- [ ] **PostgreSQL Installation**: Install PostgreSQL 14+ on production server
- [ ] **Database Creation**: Create production database
  ```sql
  CREATE DATABASE modulo_api_prod;
  CREATE USER modulo_api_user WITH PASSWORD 'secure_password';
  GRANT ALL PRIVILEGES ON DATABASE modulo_api_prod TO modulo_api_user;
  ```
- [ ] **Environment Variables**: Configure `.env` files with production values
  - Database credentials
  - Secret key (generate new one)
  - Odoo/ERP connection details

### 🔐 Security Configuration
- [ ] **SECRET_KEY**: Generate new, secure Django secret key
  ```python
  python -c "import secrets; print(secrets.token_urlsafe(50))"
  ```
- [ ] **DEBUG**: Set `DEBUG = False` in production settings
- [ ] **ALLOWED_HOSTS**: Configure with production domain(s)
- [ ] **HTTPS**: Ensure SSL/TLS certificates are configured
- [ ] **Environment Variables**: Never commit real secrets to version control

## 🚀 Deployment Steps

### 📦 Application Deployment
- [ ] **Code Deployment**: Clone repository on production server
  ```bash
  git clone https://github.com/nberelidze/modulo_api.git
  cd modulo_api
  ```
- [ ] **Database Migration**: Run migrations
  ```bash
  python manage.py migrate
  ```
- [ ] **Static Files**: Collect and serve static files
  ```bash
  python manage.py collectstatic --noinput
  ```
- [ ] **Create Superuser**: Create admin user for Django admin
  ```bash
  python manage.py createsuperuser
  ```

### 🌐 Web Server Configuration

#### Option A: Nginx + Gunicorn (Recommended)
- [ ] **Gunicorn Installation**: Install Gunicorn
  ```bash
  pip install gunicorn
  ```
- [ ] **Gunicorn Configuration**: Create systemd service
  ```ini
  # /etc/systemd/system/gunicorn.service
  [Unit]
  Description=gunicorn daemon
  After=network.target

  [Service]
  User=www-data
  Group=www-data
  WorkingDirectory=/path/to/modulo_api
  ExecStart=/path/to/venv/bin/gunicorn --access-logfile - --workers 3 --bind unix:/run/gunicorn.sock config.wsgi:application

  [Install]
  WantedBy=multi-user.target
  ```
- [ ] **Nginx Installation**: Install and configure Nginx
  ```nginx
  # /etc/nginx/sites-available/modulo_api
  server {
      listen 80;
      server_name your-domain.com;

      location = /favicon.ico { access_log off; log_not_found off; }

      location /static/ {
          alias /path/to/modulo_api/staticfiles/;
      }

      location / {
          include proxy_params;
          proxy_pass http://unix:/run/gunicorn.sock;
      }
  }
  ```
- [ ] **SSL Certificate**: Configure HTTPS with Let's Encrypt
  ```bash
  certbot --nginx -d your-domain.com
  ```

#### Option B: Docker Deployment
- [ ] **Dockerfile**: Create production Dockerfile
- [ ] **Docker Compose**: Set up docker-compose.yml for app + database
- [ ] **Environment**: Configure production environment variables
- [ ] **Volumes**: Set up persistent volumes for static files and database

## 🔍 Testing & Validation

### 🧪 Application Testing
- [ ] **Unit Tests**: Run test suite
  ```bash
  python manage.py test
  ```
- [ ] **Database Connectivity**: Verify database connections work
- [ ] **API Endpoints**: Test all API endpoints manually
- [ ] **Admin Interface**: Verify Django admin is accessible
- [ ] **Static Files**: Confirm CSS/JS/images load correctly

### 🔗 Integration Testing
- [ ] **Odoo/ERP Connection**: Test integration with external systems
- [ ] **Authentication**: Verify JWT token generation and validation
- [ ] **File Uploads**: Test PDF/result file handling
- [ ] **Email Notifications**: If implemented, test email sending

## 📊 Monitoring & Logging

### 📝 Logging Configuration
- [ ] **Log Files**: Configure proper log rotation
  ```bash
  # /etc/logrotate.d/modulo_api
  /path/to/modulo_api/logs/*.log {
      daily
      missingok
      rotate 52
      compress
      delaycompress
      notifempty
      create 644 www-data www-data
  }
  ```
- [ ] **Error Monitoring**: Set up error tracking (Sentry, Rollbar, etc.)
- [ ] **API Logging**: Configure drf-api-logger for request/response logging

### 📈 Performance Monitoring
- [ ] **Application Monitoring**: Set up APM (New Relic, DataDog, etc.)
- [ ] **Database Monitoring**: Monitor query performance and connections
- [ ] **Server Monitoring**: CPU, memory, disk usage monitoring

## 🔄 Backup & Recovery

### 💾 Database Backups
- [ ] **Automated Backups**: Set up daily database backups
  ```bash
  # /etc/cron.daily/db_backup
  #!/bin/bash
  pg_dump modulo_api_prod > /backup/modulo_api_$(date +\%Y\%m\%d).sql
  ```
- [ ] **Backup Retention**: Configure backup rotation (keep 30 days)
- [ ] **Offsite Storage**: Store backups in cloud storage (S3, etc.)

### 🛡️ Disaster Recovery
- [ ] **Recovery Testing**: Test backup restoration procedure
- [ ] **Failover Plan**: Document steps for server failure recovery
- [ ] **Data Integrity**: Regular integrity checks on backups

## 🔒 Security Hardening

### 🛡️ Server Security
- [ ] **Firewall**: Configure UFW/firewalld rules
  ```bash
  ufw allow 80
  ufw allow 443
  ufw enable
  ```
- [ ] **SSH Hardening**: Disable root login, use key-based auth
- [ ] **Updates**: Keep system packages updated
- [ ] **Fail2Ban**: Install and configure for brute force protection

### 🔐 Application Security
- [ ] **Security Headers**: Configure security middleware
- [ ] **CORS**: Configure CORS settings for API access
- [ ] **Rate Limiting**: Implement API rate limiting
- [ ] **Input Validation**: Ensure all inputs are properly validated

## 📚 Documentation

### 📖 Deployment Documentation
- [ ] **README**: Update README with deployment instructions
- [ ] **Environment Setup**: Document all required environment variables
- [ ] **API Documentation**: Ensure Swagger/OpenAPI docs are accessible
- [ ] **Troubleshooting**: Common issues and solutions

### 🔄 Maintenance Procedures
- [ ] **Update Process**: Document how to deploy updates
- [ ] **Rollback Plan**: Steps to rollback failed deployments
- [ ] **Monitoring Alerts**: What alerts to set up and respond to

## ✅ Final Validation

### 🚀 Go-Live Checklist
- [ ] **Load Testing**: Perform load testing with expected traffic
- [ ] **Security Audit**: Run security scan (OWASP ZAP, etc.)
- [ ] **Performance Baseline**: Establish performance benchmarks
- [ ] **Stakeholder Approval**: Get approval from stakeholders
- [ ] **Go-Live**: Deploy to production and monitor closely

### 📞 Post-Deployment
- [ ] **Monitoring**: Monitor application for 24-48 hours
- [ ] **User Feedback**: Collect feedback from initial users
- [ ] **Performance Tuning**: Optimize based on real usage patterns
- [ ] **Documentation Updates**: Update docs based on deployment experience

---

## 🎯 Quick Deployment Commands

```bash
# 1. Server setup
sudo apt update && sudo apt upgrade
sudo apt install postgresql nginx python3-venv

# 2. Application setup
git clone https://github.com/nberelidze/modulo_api.git
cd modulo_api
python3 -m venv venv
source venv/bin/activate
uv sync

# 3. Database setup
sudo -u postgres createdb modulo_api_prod
sudo -u postgres createuser modulo_api_user
sudo -u postgres psql -c "ALTER USER modulo_api_user PASSWORD 'secure_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE modulo_api_prod TO modulo_api_user;"

# 4. Environment setup
cp .env/django.env.example .env/django.env
cp .env/oerp.env.example .env/oerp.env
# Edit .env files with production values

# 5. Application setup
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser

# 6. Services setup
sudo systemctl enable gunicorn
sudo systemctl start gunicorn
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl start nginx
```

This checklist ensures a secure, reliable production deployment of your Django LIMS Proxy API! 🚀