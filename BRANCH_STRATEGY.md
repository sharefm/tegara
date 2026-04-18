# Branch Strategy

This repository uses a branch-based deployment strategy to separate development and production environments.

## Branch Structure

### DEV Branch
- **Purpose**: Development environment
- **Use Case**: Active development, testing, and experimentation
- **Deployment**: Development server
- **Docker Compose**: `docker-compose.dev.yml` (dev-only)
- **Environment**: `.env.dev` (dev-only)
- **Port**: 8080
- **Files**: Contains only development-related configuration

### PROD Branch
- **Purpose**: Production environment
- **Use Case**: Stable, production-ready code
- **Deployment**: Production server
- **Docker Compose**: `docker-compose.prod.yml` (prod-only)
- **Environment**: `.env.prod.example` (prod-only)
- **Port**: 8080
- **Files**: Contains only production-related configuration

### master Branch
- **Purpose**: Legacy/initial setup
- **Status**: Not actively used

## Workflow

### Development Workflow

1. **Work on DEV branch**:
   ```bash
   git checkout DEV
   git pull origin DEV
   ```

2. **Make changes and test locally**:
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   # Test at http://localhost:8080
   ```

3. **Commit and push to DEV**:
   ```bash
   git add .
   git commit -m "Description of changes"
   git push origin DEV
   ```

### Production Deployment Workflow

1. **Ensure DEV is stable and tested**

2. **Merge DEV into PROD**:
   ```bash
   git checkout PROD
   git pull origin PROD
   git merge DEV
   ```

3. **Test production configuration locally** (optional):
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   # Test at http://localhost:8080
   ```

4. **Push to PROD**:
   ```bash
   git push origin PROD
   ```

5. **Deploy on production server**:
   ```bash
   # On production server
   git checkout PROD
   git pull origin PROD
   docker-compose -f docker-compose.prod.yml up -d --build
   ```

## Environment Configuration

### Development (DEV branch)
- Environment file: `.env.dev` (tracked in git, dev branch only)
- Docker Compose: `docker-compose.dev.yml` (dev branch only)
- Configuration: Development reCAPTCHA keys, debug enabled
- Database: `data/tejara.db`

### Production (PROD branch)
- Environment file: `.env.prod` (NOT tracked in git)
- Environment template: `.env.prod.example` (prod branch only)
- Docker Compose: `docker-compose.prod.yml` (prod branch only)
- Configuration: Production reCAPTCHA keys, debug disabled
- Database: `data/tejara.db`
- **Important**: Create `.env.prod` from `.env.prod.example` on production server

> [!NOTE]
> Each branch contains only its own environment-specific files. DEV branch does not have production files, and PROD branch does not have development files.

## Quick Reference

| Branch | Port | Docker Compose File | Environment File | Files Included |
|--------|------|-------------------|------------------|----------------|
| DEV | 8080 | `docker-compose.dev.yml` | `.env.dev` | Dev files only |
| PROD | 8080 | `docker-compose.prod.yml` | `.env.prod.example` | Prod files only |

## Portainer Access

Both environments include Portainer for container management:
- **HTTPS**: https://localhost:9443 (recommended)
- **HTTP**: http://localhost:9000

## Best Practices

1. **Never commit `.env.prod`** - Contains production secrets
2. **Always test in DEV** before merging to PROD
3. **Use pull requests** for code review (optional but recommended)
4. **Tag releases** in PROD for version tracking
5. **Keep branches in sync** - Regularly merge DEV to PROD

## Hotfix Workflow

For urgent production fixes:

1. **Create hotfix from PROD**:
   ```bash
   git checkout PROD
   git checkout -b hotfix/description
   ```

2. **Make fix and test**

3. **Merge to PROD**:
   ```bash
   git checkout PROD
   git merge hotfix/description
   git push origin PROD
   ```

4. **Merge back to DEV**:
   ```bash
   git checkout DEV
   git merge hotfix/description
   git push origin DEV
   ```

## Additional Resources

- [DEPLOYMENT.md](DEPLOYMENT.md) - Comprehensive deployment guide
- [RECAPTCHA_SETUP.md](RECAPTCHA_SETUP.md) - reCAPTCHA configuration guide
