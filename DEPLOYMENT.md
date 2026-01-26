# Tegara Deployment Guide

This guide covers how to deploy the Tegara application using Docker and docker-compose for both development and production environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Development Environment](#development-environment)
- [Production Environment](#production-environment)
- [Portainer Container Management](#portainer-container-management)
- [Environment Variables](#environment-variables)
- [Common Operations](#common-operations)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before deploying, ensure you have the following installed:

- **Docker** (version 20.10 or higher)
- **Docker Compose** (version 2.0 or higher)
- **Git** (for cloning the repository)

### Installing Docker

**Ubuntu/Debian:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

**macOS:**
Download and install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop)

**Windows:**
Download and install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)

## Development Environment

The development environment includes live code reloading and debug features.

### Setup

1. **Clone the repository:**
   ```bash
   git clone git@github.com:sharefm/tegara.git
   cd tegara
   ```

2. **Environment variables are already configured** in `.env.dev` for development.

3. **Build and start the containers:**
   ```bash
   docker-compose up -d
   ```

4. **View logs:**
   ```bash
   docker-compose logs -f
   ```

5. **Access the application:**
   - Application: http://localhost:8000
   - Portainer: https://localhost:9443 or http://localhost:9000

### Development Features

- **Live Reload**: Code changes are automatically detected and the server reloads
- **Volume Mounts**: Source code is mounted, so changes are reflected immediately
- **Debug Mode**: Detailed error messages and stack traces

### Stopping Development Environment

```bash
# Stop containers
docker-compose down

# Stop and remove volumes (WARNING: This deletes the database!)
docker-compose down -v
```

## Production Environment

The production environment is optimized for performance and security.

### Setup

1. **Clone the repository on your production server:**
   ```bash
   git clone git@github.com:sharefm/tegara.git
   cd tegara
   ```

2. **Create production environment file:**
   ```bash
   cp .env.prod.example .env.prod
   ```

3. **Edit `.env.prod` with your production values:**
   ```bash
   nano .env.prod
   ```

   **Required changes:**
   - `RECAPTCHA_SITE_KEY`: Your production reCAPTCHA site key
   - `RECAPTCHA_SECRET_KEY`: Your production reCAPTCHA secret key
   - `SESSION_SECRET_KEY`: Generate a strong random secret (see below)

   **Generate a secure session secret:**
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

4. **Build and start the production containers:**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d --build
   ```

5. **Verify the deployment:**
   ```bash
   # Check container status
   docker-compose -f docker-compose.prod.yml ps
   
   # View logs
   docker-compose -f docker-compose.prod.yml logs -f
   
   # Test health endpoint
   curl http://localhost:8080/health
   ```

6. **Access the application:**
   - Application: http://localhost:8080
   - Portainer: https://localhost:9443 or http://localhost:9000
   - If you have a domain, point it to your server's IP address

### Production Features

- **No Live Reload**: Optimized for performance
- **Restart Policy**: Containers automatically restart on failure
- **Health Checks**: Docker monitors application health
- **Security**: Runs as non-root user inside container

### Updating Production

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart containers
docker-compose -f docker-compose.prod.yml up -d --build

# View logs to ensure successful restart
docker-compose -f docker-compose.prod.yml logs -f
```

## Portainer Container Management

Both development and production environments include Portainer, a web-based container management UI.

### Accessing Portainer

**Development:**
- HTTPS: https://localhost:9443 (recommended)
- HTTP: http://localhost:9000

**Production:**
- HTTPS: https://your-server-ip:9443 (recommended)
- HTTP: http://your-server-ip:9000

### First-Time Setup

1. Navigate to Portainer URL (HTTPS recommended)
2. Create an admin account on first visit
3. Choose "Docker" as the environment type
4. Connect to the local Docker environment

### Features

- **Container Management**: Start, stop, restart, and view logs
- **Image Management**: View, pull, and remove Docker images
- **Volume Management**: Manage Docker volumes and backups
- **Network Management**: View and manage Docker networks
- **Real-time Monitoring**: CPU, memory, and network usage
- **Console Access**: Execute commands in running containers

### Security Notes

- Portainer is accessible on ports 9443 (HTTPS) and 9000 (HTTP)
- Always use HTTPS (port 9443) in production
- Set a strong admin password
- Consider restricting access via firewall rules in production

## Environment Variables

### Development (.env.dev)

Already configured with development defaults. You can modify if needed.

### Production (.env.prod)

**Critical variables to set:**

| Variable | Description | Example |
|----------|-------------|---------|
| `RECAPTCHA_SITE_KEY` | Google reCAPTCHA v3 site key | `6LeXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX` |
| `RECAPTCHA_SECRET_KEY` | Google reCAPTCHA v3 secret key | `6LeXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX` |
| `SESSION_SECRET_KEY` | Strong random secret for sessions | `your_random_secret_here` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@db:5432/tejara_db` |
| `ENVIRONMENT` | Environment name | `production` |
| `DEBUG` | Enable debug mode | `false` |

### Getting reCAPTCHA Keys

1. Go to [Google reCAPTCHA Admin](https://www.google.com/recaptcha/admin)
2. Create a new site (reCAPTCHA v3)
3. Add your domain(s)
4. Copy the Site Key and Secret Key to your `.env.prod` file

## Common Operations

### View Logs

**Development:**
```bash
docker-compose logs -f
```

**Production:**
```bash
docker-compose -f docker-compose.prod.yml logs -f
```

### Restart Containers

**Development:**
```bash
docker-compose restart
```

**Production:**
```bash
docker-compose -f docker-compose.prod.yml restart
```

### Access Container Shell

**Development:**
```bash
docker-compose exec web bash
```

**Production:**
```bash
docker-compose -f docker-compose.prod.yml exec web bash
```

### Database Backup

```bash
# Create backup directory
mkdir -p backups

# Backup PostgreSQL database (development)
docker-compose exec db pg_dump -U tejara_user tejara_db > ./backups/tejara-$(date +%Y%m%d-%H%M%S).sql

# Backup PostgreSQL database (production)
docker-compose -f docker-compose.prod.yml exec db pg_dump -U tejara_user tejara_db > ./backups/tejara-$(date +%Y%m%d-%H%M%S).sql
```

### Database Restore

```bash
# Restore database (development)
docker-compose exec -T db psql -U tejara_user tejara_db < ./backups/tejara-YYYYMMDD-HHMMSS.sql

# Restore database (production)
docker-compose -f docker-compose.prod.yml exec -T db psql -U tejara_user tejara_db < ./backups/tejara-YYYYMMDD-HHMMSS.sql
```

### Clean Up

```bash
# Remove stopped containers
docker-compose down

# Remove containers and volumes (WARNING: Deletes database!)
docker-compose down -v

# Remove unused images
docker image prune -a
```

## Troubleshooting

### Container Won't Start

1. **Check logs:**
   ```bash
   docker-compose logs
   ```

2. **Verify environment variables:**
   ```bash
   docker-compose config
   ```

3. **Check if port is already in use:**
   ```bash
   sudo lsof -i :8000  # for dev app
   sudo lsof -i :8080  # for prod app
   sudo lsof -i :9443  # for Portainer HTTPS
   sudo lsof -i :9000  # for Portainer HTTP
   ```

### Database Issues

1. **Database connection error:**
   - Ensure PostgreSQL container is running: `docker-compose ps`
   - Check database logs: `docker-compose logs db`
   - Restart the containers: `docker-compose restart`

2. **Database not persisting:**
   - Check volume mounts: `docker-compose config`
   - Verify `./postgres_data` directory exists and has proper permissions

### Permission Errors

```bash
# Fix postgres data directory permissions
sudo chown -R 999:999 ./postgres_data
```

### reCAPTCHA Not Working

1. **Verify keys are correct** in `.env.dev` or `.env.prod`
2. **Check domain configuration** in Google reCAPTCHA admin
3. **For localhost testing**, add `localhost` to allowed domains in reCAPTCHA settings

### Health Check Failing

```bash
# Test health endpoint manually
curl http://localhost:8000/health

# Check if application is running
docker-compose ps
```

### Rebuilding from Scratch

```bash
# Stop everything
docker-compose down -v

# Remove images
docker rmi tegara:latest

# Rebuild and start
docker-compose up -d --build
```

## Security Best Practices

1. **Never commit `.env.prod`** to version control
2. **Use strong session secrets** (at least 32 characters)
3. **Keep Docker and dependencies updated**
4. **Use HTTPS in production** (consider using nginx as reverse proxy with Let's Encrypt)
5. **Regularly backup your database**
6. **Monitor logs for suspicious activity**

## Production Checklist

Before going live, ensure:

- [ ] Production reCAPTCHA keys are configured
- [ ] Strong session secret is set
- [ ] `.env.prod` is not committed to git
- [ ] Database backups are configured
- [ ] HTTPS is configured (if applicable)
- [ ] Domain DNS is pointing to server
- [ ] Firewall rules are configured
- [ ] Health checks are passing
- [ ] Application is accessible from external network

## Support

For issues or questions:
- Check the [GitHub Issues](https://github.com/sharefm/tegara/issues)
- Review application logs
- Consult Docker documentation
