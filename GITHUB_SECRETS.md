# GitHub Secrets Configuration for Production Deployment

The CI/CD pipeline now automatically creates the `.env.prod` file on the production server using GitHub Secrets. This ensures sensitive credentials are never committed to the repository.

## Required GitHub Secrets

You need to configure the following secrets in your GitHub repository:

**Path:** `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

### PostgreSQL Credentials (Required)
- **`POSTGRES_DB`** - Database name (e.g., `tejara`)
- **`POSTGRES_USER`** - Database user (e.g., `tejara_user`)
- **`POSTGRES_PASSWORD`** - Strong database password

### Application Secrets (Required)
- **`RECAPTCHA_SITE_KEY`** - Google reCAPTCHA site key
- **`RECAPTCHA_SECRET_KEY`** - Google reCAPTCHA secret key
- **`SESSION_SECRET_KEY`** - Random string for session encryption
- **`SMS_API_KEY`** - Hadara SMS API key

### Cloudflare Configuration (Required)
- **`CLOUDFLARE_API_TOKEN`** - Cloudflare API token for DNS management
- **`CLOUDFLARE_ZONE_ID`** - Cloudflare zone ID for tejara.ps domain

### Webhook Authentication (Required)
- **`DOMAIN_SYNC_WEBHOOK_SECRET`** - Webhook authentication secret

### SSH Deployment (Already configured)
- **`DEPLOY_SSH_KEY`** - SSH private key for deploy@www.tejara.ps

## How It Works

1. When code is pushed to the `PROD` branch, GitHub Actions triggers
2. The workflow builds and pushes the Docker image
3. The deployment job SSH into the production server
4. It creates/updates `.env.prod` using the secrets from GitHub
5. It pulls the latest images and restarts containers

## Setting Up Secrets

### Example Values (Replace with your actual values)

```bash
POSTGRES_DB=tejara
POSTGRES_USER=tejara_user
POSTGRES_PASSWORD=SuperSecurePassword123!

RECAPTCHA_SITE_KEY=6Let6z4sAAAAAPsuti-q9JOTLaYOdsVchMGoHvz7
RECAPTCHA_SECRET_KEY=6Let6z4sAAAAANMtNTaaMgscktEdkZ5d4Kvd99gh

SESSION_SECRET_KEY=randomly-generated-secret-key-min-32-chars

SMS_API_KEY=452E815F906B6BD877B6C5F294F244F4

CLOUDFLARE_API_TOKEN=your_cloudflare_token_here
CLOUDFLARE_ZONE_ID=your_zone_id_here

DOMAIN_SYNC_WEBHOOK_SECRET=your_webhook_secret_here
```

## Security Benefits

✅ Credentials never stored in git repository  
✅ Automatic `.env.prod` creation on deployment  
✅ Easy credential rotation via GitHub UI  
✅ Different secrets per environment (dev/prod)  
✅ Audit trail of secret changes

## Next Steps

1. Add all required secrets to GitHub repository
2. Push changes to `PROD` branch
3. GitHub Actions will automatically deploy with the new configuration
4. Verify deployment in Actions tab

## Troubleshooting

If deployment fails with "variable is not set" errors:
- Check that all secrets are configured in GitHub
- Verify secret names match exactly (case-sensitive)
- Check GitHub Actions logs for specific missing variables
