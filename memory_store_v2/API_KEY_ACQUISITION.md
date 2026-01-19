# Cline API Key Acquisition Guide

This guide walks you through obtaining your Cline API key for marketplace publication.

## Step-by-Step Process

### 1. Visit Cline Developer Portal

**URL**: https://developer.cline.ai

**What you'll see:**
- Welcome screen
- Sign in / Sign up options
- Developer resources

### 2. Create Developer Account

#### Option A: New User
1. Click **"Sign Up"** or **"Create Account"**
2. Fill in required information:
   - Email address
   - Password
   - Full name
   - Company (optional)
3. Verify email address (check inbox for verification link)
4. Complete developer profile:
   - Developer type (Individual/Organization)
   - Primary use case
   - Expected usage volume

#### Option B: Existing User
1. Click **"Sign In"**
2. Enter credentials
3. Navigate to Developer Dashboard

### 3. Access Developer Dashboard

Once logged in:
1. Look for **"Developer Portal"** or **"My Apps"** in navigation
2. Click to access dashboard
3. You should see:
   - App management section
   - API key section
   - Usage statistics
   - Documentation links

### 4. Create New Application

1. Click **"Create New App"** or **"New Application"**
2. Fill in application details:

   **Required Fields:**
   - **App Name**: `ChainOfThought Coder V2`
   - **Description**: `Enhanced memory system for step-by-step problem solving with hierarchical task management and dual-tier memory`
   - **Category**: `Developer Tools`
   - **Website**: (Your repository URL, e.g., `https://github.com/your-org/chainofthought-coder`)

   **Optional Fields:**
   - **Logo**: Upload app icon (512x512 PNG recommended)
   - **Screenshots**: Add demo images
   - **Tags**: `memory`, `task-management`, `mcp`, `thinking-tool`
   - **Support Email**: Your contact email
   - **Privacy Policy**: Link to privacy policy
   - **Terms of Service**: Link to terms

3. Click **"Create Application"** or **"Save"**

### 5. Generate API Key

1. In your application dashboard, find **"API Keys"** section
2. Click **"Generate New Key"** or **"Create API Key"**
3. Configure key settings:
   - **Key Name**: `Production Key` or `Release v2.4.0`
   - **Permissions**: 
     - ✅ Publish to Marketplace
     - ✅ Manage Applications
     - ✅ View Analytics
   - **Rate Limit**: Select appropriate tier (Start with "Standard")
4. Click **"Generate"** or **"Create"**

### 6. Copy and Secure API Key

**Important**: API keys are shown only once!

1. Copy the API key immediately
2. Format: `cline_api_xxxxxxxxxxxxxxxx`
3. Store securely:
   - Password manager (recommended)
   - Environment variable
   - Secure note

**Example formats:**
```
cline_api_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
```

### 7. Verify API Key

Test your API key with a simple command:

```bash
# Set environment variable
export CLINE_API_KEY="cline_api_xxxxxxxxxxxxxxxx"

# Test connection
cline marketplace status --api-key $CLINE_API_KEY
```

Expected output:
```
✅ API key valid
✅ Account active
✅ Permissions: publish, manage, analytics
```

## Security Best Practices

### Do's ✅
- Store in environment variables
- Use password manager
- Rotate keys regularly (every 6-12 months)
- Use different keys for development/production
- Monitor key usage in dashboard

### Don'ts ❌
- Never commit to git repository
- Never share publicly
- Never hardcode in source files
- Never use in client-side code
- Never log to console/files

## Troubleshooting

### Issue: "Account not verified"
**Solution:**
- Check email for verification link
- Check spam folder
- Request new verification email
- Contact Cline support if issue persists

### Issue: "API key generation disabled"
**Solution:**
- Complete developer profile
- Verify email address
- Accept terms of service
- Contact support for account review

### Issue: "Key not working"
**Solution:**
- Verify no extra whitespace
- Check key format (should start with `cline_api_`)
- Ensure account is active
- Regenerate key if needed

### Issue: "Rate limit exceeded"
**Solution:**
- Upgrade to higher tier in dashboard
- Implement exponential backoff
- Contact support for limit increase

## API Key Management

### Viewing Active Keys
1. Go to Developer Dashboard
2. Navigate to **"API Keys"** section
3. View all active keys
4. See usage statistics

### Revoking Keys
1. Find key in dashboard
2. Click **"Revoke"** or **"Delete"**
3. Confirm action
4. Update applications using this key

### Rotating Keys
1. Generate new key
2. Update applications
3. Test new key
4. Revoke old key after 24-48 hours

## Dashboard Features

### Analytics
- API call counts
- Error rates
- Usage patterns
- Geographic distribution

### Billing
- Usage-based pricing
- Invoice history
- Payment methods
- Usage alerts

### Support
- Documentation
- Community forum
- Direct support tickets
- Status page

## Pricing

### Free Tier
- 1,000 API calls/month
- Basic analytics
- Community support
- Single application

### Paid Tiers (if applicable)
- **Starter**: $10/month - 10,000 calls
- **Professional**: $50/month - 100,000 calls
- **Enterprise**: Custom pricing

*Note: Check current pricing at developer.cline.ai*

## Next Steps After Getting API Key

1. **Store securely** in environment variable
2. **Test connection** with CLI tool
3. **Run pre-publication checks**
4. **Create distribution package**
5. **Execute publication command**

## Environment Setup Examples

### Windows (PowerShell)
```powershell
# Set environment variable
$env:CLINE_API_KEY="cline_api_xxxxxxxxxxxxxxxx"

# Verify
echo $env:CLINE_API_KEY

# Use in command
cline marketplace publish --api-key $env:CLINE_API_KEY
```

### Windows (CMD)
```cmd
set CLINE_API_KEY=cline_api_xxxxxxxxxxxxxxxx
echo %CLINE_API_KEY%
```

### Linux/macOS
```bash
# Temporary (current session)
export CLINE_API_KEY="cline_api_xxxxxxxxxxxxxxxx"

# Permanent (add to shell profile)
echo 'export CLINE_API_KEY="cline_api_xxxxxxxxxxxxxxxx"' >> ~/.bashrc
source ~/.bashrc

# Verify
echo $CLINE_API_KEY
```

### Python
```python
import os

# Set in code (not recommended for production)
os.environ['CLINE_API_KEY'] = 'cline_api_xxxxxxxxxxxxxxxx'

# Or use from environment
api_key = os.getenv('CLINE_API_KEY')
```

## Support Resources

- **Developer Portal**: https://developer.cline.ai
- **API Documentation**: https://docs.cline.ai/api
- **Support**: https://support.cline.ai
- **Community**: https://forum.cline.ai

## Quick Reference

### Key Information to Remember
- **API Key Format**: `cline_api_xxxxxxxxxxxxxxxx`
- **Dashboard URL**: https://developer.cline.ai
- **Key Location**: Developer Portal → My Apps → [Your App] → API Keys
- **Permissions Needed**: Publish to Marketplace

### Command Reference
```bash
# Test API key
cline marketplace status --api-key $CLINE_API_KEY

# Publish package
cline marketplace publish \
  --name "ChainOfThought Coder V2" \
  --package release/chainofthought-coder-v2.4.0.zip \
  --category "developer-tools" \
  --api-key $CLINE_API_KEY
```

---

**Ready to get your API key?** Visit https://developer.cline.ai and follow the steps above!
