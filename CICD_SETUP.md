# GitHub Actions CI/CD Setup

This document explains the GitHub Actions CI/CD pipeline for the Tegara project.

## Overview

The CI/CD pipeline automatically builds and deploys Docker images to Docker Hub whenever code is pushed to the DEV branch.

## Pipeline File

**Location**: `.github/workflows/cicd-dev.yaml`

## Workflow Details

### Trigger Events

The pipeline runs on:
- **Push** to DEV branch
- **Pull Request** to DEV branch

### What It Does

1. **Checkout Code**: Retrieves the latest code from the repository
2. **Set up Docker Buildx**: Configures advanced Docker build features
3. **Login to Docker Hub**: Authenticates using GitHub secrets
4. **Generate Timestamp**: Creates a timestamp in format `YYYYMMDDHHmm`
5. **Build Docker Image**: Builds the image using the Dockerfile
6. **Push to Docker Hub**: Pushes with two tags:
   - `sharefdnskube/tejara:latest` - Always points to the latest build
   - `sharefdnskube/tejara:YYYYMMDDHHmm` - Specific timestamp version

### Docker Hub Repository

- **Username**: `sharefdnskube`
- **Repository**: `sharefdnskube/tejara`
- **Tags**: 
  - `latest` - Latest build from DEV branch
  - `YYYYMMDDHHmm` - Timestamped versions (e.g., `202601061545`)

## GitHub Secrets Required

You need to configure the following secret in your GitHub repository:

### Setting Up the Secret

1. Go to your GitHub repository: `https://github.com/sharefm/tegara`
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add the following secret:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `DOCKER_SECRET` | Your Docker Hub password/token | Used to authenticate with Docker Hub |

### How to Get Docker Hub Token

1. Log in to [Docker Hub](https://hub.docker.com/)
2. Go to **Account Settings** → **Security**
3. Click **New Access Token**
4. Name it (e.g., "GitHub Actions")
5. Copy the token and add it as `DOCKER_SECRET` in GitHub

## Pipeline Features

### Build Caching

The pipeline uses Docker layer caching to speed up builds:
- **Cache source**: `sharefdnskube/tejara:buildcache`
- **Cache mode**: `max` (caches all layers)

This significantly reduces build times for subsequent runs.

### Image Tags

Every successful build creates two tags:

1. **latest**: 
   - Always overwritten with the newest build
   - Use for development/testing
   - Pull with: `docker pull sharefdnskube/tejara:latest`

2. **Timestamp** (e.g., `202601061545`):
   - Immutable version for that specific build
   - Use for rollbacks or specific versions
   - Pull with: `docker pull sharefdnskube/tejara:202601061545`

## Usage Examples

### Pull Latest Image

```bash
docker pull sharefdnskube/tejara:latest
```

### Pull Specific Version

```bash
docker pull sharefdnskube/tejara:202601061545
```

### Run Container from Docker Hub

```bash
# Using latest
docker run -d -p 8000:8000 sharefdnskube/tejara:latest

# Using specific version
docker run -d -p 8000:8000 sharefdnskube/tejara:202601061545
```

### Update docker-compose to Use Docker Hub Image

Instead of building locally, you can use the pre-built image:

```yaml
services:
  web:
    image: sharefdnskube/tejara:latest  # or specific timestamp
    # Remove 'build' section
    container_name: tegara-dev
    ports:
      - "8000:8000"
    # ... rest of configuration
```

## Monitoring Pipeline

### View Pipeline Status

1. Go to your repository on GitHub
2. Click on the **Actions** tab
3. You'll see all workflow runs

### Pipeline Runs On

- Every push to DEV branch
- Every pull request to DEV branch

### Build Status Badge (Optional)

Add this to your README.md to show build status:

```markdown
![CI/CD DEV](https://github.com/sharefm/tegara/actions/workflows/cicd-dev.yaml/badge.svg?branch=DEV)
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

### Image Not Found on Docker Hub

**Issue**: Can't pull the image

**Solution**:
1. Check if the pipeline completed successfully
2. Verify the repository is public or you're logged in
3. Wait a few minutes for Docker Hub to sync

## Best Practices

1. **Always review the Actions log** after pushing to ensure the build succeeded
2. **Use timestamp tags** for production deployments (immutable)
3. **Use latest tag** for development and testing only
4. **Keep secrets secure** - never commit Docker Hub credentials
5. **Monitor build times** - optimize Dockerfile if builds are slow

## Next Steps

### For Production Branch

Consider creating a similar pipeline for the PROD branch:
- File: `.github/workflows/cicd-prod.yaml`
- Trigger: Push to PROD branch
- Tag: `sharefdnskube/tejara:prod-YYYYMMDDHHmm`
- Additional: Manual approval step before deployment

### Enhancements

- Add automated testing before build
- Add security scanning (Trivy, Snyk)
- Add notifications (Slack, Discord)
- Add deployment to Kubernetes/cloud platform
- Add rollback mechanism

## Summary

✅ **Automated builds** on every DEV push  
✅ **Docker Hub integration** with dual tagging  
✅ **Build caching** for faster builds  
✅ **Version tracking** with timestamps  
✅ **Easy rollbacks** with immutable tags  

Your CI/CD pipeline is now active and will automatically build and push images whenever you push to the DEV branch!
