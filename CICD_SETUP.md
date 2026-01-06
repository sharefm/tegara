# GitHub Actions CI/CD Setup

This document explains the GitHub Actions CI/CD pipelines for the Tegara project.

## Overview

The project has two automated CI/CD pipelines:
- **DEV Pipeline**: Builds and deploys development images
- **PROD Pipeline**: Builds and deploys production images

Both pipelines automatically build and push Docker images to Docker Hub.

## Pipeline Files

| Branch | Workflow File | Purpose |
|--------|--------------|---------|
| DEV | `.github/workflows/cicd-dev.yaml` | Development builds |
| PROD | `.github/workflows/cicd-prod.yaml` | Production builds |

## DEV Pipeline

### Trigger Events
- Push to DEV branch
- Pull request to DEV branch

### Image Tags
- `sharefdnskube/tejara:latest`
- `sharefdnskube/tejara:YYYYMMDDHHmm` (e.g., `202601061545`)

### Usage
```bash
# Pull latest dev build
docker pull sharefdnskube/tejara:latest

# Pull specific dev version
docker pull sharefdnskube/tejara:202601061545
```

## PROD Pipeline

### Trigger Events
- Push to PROD branch
- Pull request to PROD branch

### Image Tags
- `sharefdnskube/tejara:prod`
- `sharefdnskube/tejara:prod-YYYYMMDDHHmm` (e.g., `prod-202601061545`)

### Usage
```bash
# Pull latest prod build
docker pull sharefdnskube/tejara:prod

# Pull specific prod version
docker pull sharefdnskube/tejara:prod-202601061545
```

## Docker Hub Repository

- **Username**: `sharefdnskube`
- **Repository**: `sharefdnskube/tejara`
- **All Tags**:
  - `latest` - Latest DEV build
  - `YYYYMMDDHHmm` - Timestamped DEV builds
  - `prod` - Latest PROD build
  - `prod-YYYYMMDDHHmm` - Timestamped PROD builds

## GitHub Secrets Required

Configure this secret in your GitHub repository settings:

### Setting Up the Secret

1. Go to: `https://github.com/sharefm/tegara/settings/secrets/actions`
2. Click **New repository secret**
3. Add:
   - **Name**: `DOCKER_SECRET`
   - **Value**: Your Docker Hub password/token for user `sharefdnskube`

### How to Get Docker Hub Token

1. Log in to [Docker Hub](https://hub.docker.com/)
2. Go to **Account Settings** → **Security**
3. Click **New Access Token**
4. Name it (e.g., "GitHub Actions")
5. Copy the token and add it as `DOCKER_SECRET` in GitHub

## Pipeline Features

### Build Caching

Both pipelines use Docker layer caching:
- **DEV cache**: `sharefdnskube/tejara:buildcache`
- **PROD cache**: `sharefdnskube/tejara:buildcache-prod`

This significantly reduces build times for subsequent runs.

### Automatic Tagging

Every successful build creates two tags:

**DEV Branch:**
- `latest` - Always the newest dev build
- `YYYYMMDDHHmm` - Immutable timestamp version

**PROD Branch:**
- `prod` - Always the newest prod build
- `prod-YYYYMMDDHHmm` - Immutable timestamp version

## Deployment Workflow

### Development Deployment

1. Make changes in DEV branch
2. Push to GitHub
3. Pipeline automatically builds and pushes
4. Deploy using:
   ```bash
   docker pull sharefdnskube/tejara:latest
   docker run -d -p 8000:8000 sharefdnskube/tejara:latest
   ```

### Production Deployment

1. Merge DEV to PROD when ready
2. Push PROD branch to GitHub
3. Pipeline automatically builds and pushes
4. Deploy using:
   ```bash
   docker pull sharefdnskube/tejara:prod
   docker run -d -p 8000:8000 sharefdnskube/tejara:prod
   ```

## Using with docker-compose

### Development

Update `docker-compose.dev.yml`:
```yaml
services:
  web:
    image: sharefdnskube/tejara:latest
    # Remove 'build' section
    container_name: tegara-dev
    # ... rest of configuration
```

### Production

Update `docker-compose.prod.yml`:
```yaml
services:
  web:
    image: sharefdnskube/tejara:prod
    # Remove 'build' section
    container_name: tegara-prod
    # ... rest of configuration
```

## Monitoring Pipelines

### View Pipeline Status

1. Go to: `https://github.com/sharefm/tegara/actions`
2. See all workflow runs for both DEV and PROD

### Build Status Badges

Add to README.md:

```markdown
![CI/CD DEV](https://github.com/sharefm/tegara/actions/workflows/cicd-dev.yaml/badge.svg?branch=DEV)
![CI/CD PROD](https://github.com/sharefm/tegara/actions/workflows/cicd-prod.yaml/badge.svg?branch=PROD)
```

## Troubleshooting

### Pipeline Fails to Push

**Issue**: Authentication error with Docker Hub

**Solution**: 
1. Verify `DOCKER_SECRET` is set correctly in GitHub secrets
2. Ensure the Docker Hub token hasn't expired
3. Check that username `sharefdnskube` is correct

### Build Fails

**Issue**: Docker build errors

**Solution**:
1. Check the Actions tab for detailed error logs
2. Verify Dockerfile syntax
3. Ensure all dependencies are in requirements.txt
4. Test build locally: `docker build -t test .`

### Wrong Image Pulled

**Issue**: Getting DEV image instead of PROD

**Solution**:
- Use explicit tags: `prod` for production, `latest` for development
- Check which branch triggered the build in Actions tab

## Best Practices

### Development
1. Use `latest` tag for development and testing
2. Review Actions log after each push
3. Test locally before pushing

### Production
1. **Always use `prod` tag** for production deployments
2. **Use timestamped tags** (e.g., `prod-202601061545`) for specific versions
3. **Never use `latest`** in production
4. Keep track of deployed versions
5. Test in DEV before merging to PROD

### Rollback Strategy

If production deployment fails:

```bash
# Find previous working version in Actions history
docker pull sharefdnskube/tejara:prod-202601061530

# Deploy the previous version
docker run -d -p 8000:8000 sharefdnskube/tejara:prod-202601061530
```

## Summary

✅ **Two automated pipelines** (DEV and PROD)  
✅ **Automatic builds** on every push  
✅ **Docker Hub integration** with environment-specific tagging  
✅ **Build caching** for faster builds  
✅ **Version tracking** with timestamps  
✅ **Easy rollbacks** with immutable tags  

Your CI/CD pipelines are now active for both DEV and PROD branches!
