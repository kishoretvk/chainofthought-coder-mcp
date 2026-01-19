# Cline Marketplace Publication Guide

This guide walks you through publishing ChainOfThought Coder V2 to the Cline MCP Hub.

## Prerequisites

### 1. Cline Developer Account
- Sign up at: https://developer.cline.ai
- Verify your email address
- Complete developer profile

### 2. API Key Acquisition
```bash
# 1. Navigate to Developer Portal
# 2. Click "Create New App"
# 3. Fill in:
#    - App Name: "ChainOfThought Coder V2"
#    - Description: "Enhanced memory system for step-by-step problem solving"
#    - Category: "Developer Tools"
#    - Website: (your repository URL)
# 4. Click "Generate API Key"
# 5. Copy the API key (format: cline_api_xxxxxxxxxxxxxxxx)
```

### 3. Required Files
Ensure these files exist in your project:
- ✅ `memory_store_v2/mcp-manifest.json`
- ✅ `memory_store_v2/CHANGELOG.md`
- ✅ `README.md`
- ✅ `requirements.txt`

## Step-by-Step Publication Process

### Phase 1: Pre-Publication Checks

#### 1.1 Security Audit
```bash
# Run Cline security scanner
cline security scan --level production

# Expected output:
# ✅ No critical vulnerabilities
# ✅ No high-severity issues
# ✅ All dependencies up to date
```

#### 1.2 Compatibility Validation
```bash
# Validate manifest against Cline standards
cline compatibility validate --manifest memory_store_v2/mcp-manifest.json

# Expected output:
# ✅ Manifest format valid
# ✅ All required fields present
# ✅ Dependencies compatible
```

#### 1.3 Performance Benchmark
```bash
# Run load tests
python tests_v2/load_test.py --users 1000 --duration 300

# Expected metrics:
# - Response time < 100ms (95th percentile)
# - Error rate < 0.1%
# - Memory usage < 500MB
```

#### 1.4 Dependency Audit
```bash
# Check for vulnerabilities
pip-audit -r requirements.txt

# Expected output:
# ✅ No known vulnerabilities
```

### Phase 2: Package Preparation

#### 2.1 Update Version Numbers
```bash
# Update __init__.py
sed -i 's/__version__ = "2.3.0"/__version__ = "2.4.0"/' memory_store_v2/__init__.py

# Update manifest
sed -i 's/"version": "2.3.0"/"version": "2.4.0"/' memory_store_v2/mcp-manifest.json
```

#### 2.2 Clean Development Artifacts
```bash
# Remove test databases
rm -f demo_storage/memory.db
rm -f memory_store_v2/memory.db

# Remove cache files
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Remove temporary files
rm -f *.log
rm -f *.tmp
```

#### 2.3 Create Distribution Package
```bash
# Create release directory
mkdir -p release

# Package all required files
zip -r release/chainofthought-coder-v2.4.0.zip \
  memory_store_v2/ \
  tests_v2/ \
  mcp-manifest.json \
  CHANGELOG.md \
  README.md \
  requirements.txt \
  SETUP_COMPLETE.md

# Verify package contents
unzip -l release/chainofthought-coder-v2.4.0.zip | head -20
```

#### 2.4 Generate Documentation
```bash
# Install pdoc3
pip install pdoc3

# Generate API docs
pdoc3 --html -o docs memory_store_v2

# Create demo GIF (optional)
# Use screen recording tool to capture demo
# Save as docs/demo.gif
```

### Phase 3: Publication

#### 3.1 Set Environment Variables
```bash
# Windows (PowerShell)
$env:CLINE_API_KEY="cline_api_xxxxxxxxxxxxxxxx"

# Windows (CMD)
set CLINE_API_KEY=cline_api_xxxxxxxxxxxxxxxx

# Linux/macOS
export CLINE_API_KEY="cline_api_xxxxxxxxxxxxxxxx"
```

#### 3.2 Execute Publication
```bash
# Publish to Cline Marketplace
cline marketplace publish \
  --name "ChainOfThought Coder V2" \
  --package release/chainofthought-coder-v2.4.0.zip \
  --category "developer-tools" \
  --description "Enhanced memory system for step-by-step problem solving with hierarchical task management and dual-tier memory" \
  --api-key $CLINE_API_KEY
```

#### 3.3 Monitor Publication Status
```bash
# Check publication status
cline marketplace status --name "ChainOfThought Coder V2"

# Expected timeline:
# - Review: 1-3 business days
# - Approval: 3-5 business days
# - Live: 5-7 business days total
```

### Phase 4: Post-Publication

#### 4.1 Update Repository
```bash
# Create GitHub release
gh release create v2.4.0 \
  --title "ChainOfThought Coder V2.4.0 - Cline Marketplace Release" \
  --notes-file CHANGELOG.md \
  --attach release/chainofthought-coder-v2.4.0.zip

# Update README with marketplace link
# Add: [![Cline Marketplace](https://img.shields.io/badge/Cline-Marketplace-blue)](https://marketplace.cline.ai/...)
```

#### 4.2 Monitor Metrics
```bash
# Check download statistics
cline marketplace stats --name "ChainOfThought Coder V2"

# Track user feedback
# Monitor GitHub issues
# Watch for bug reports
```

#### 4.3 Prepare Patch Releases
```bash
# For bug fixes (patch version)
# 1. Fix issue in code
# 2. Update CHANGELOG.md
# 3. Bump version to 2.4.1
# 4. Repeat packaging process
```

## Troubleshooting

### Issue: "API Key Invalid"
**Solution:**
```bash
# Regenerate API key in developer portal
# Ensure no extra whitespace
export CLINE_API_KEY=$(echo $CLINE_API_KEY | tr -d ' ')
```

### Issue: "Package Too Large"
**Solution:**
```bash
# Check package size
du -h release/chainofthought-coder-v2.4.0.zip

# If > 50MB, exclude test files
zip -r release/chainofthought-coder-v2.4.0.zip \
  memory_store_v2/ \
  mcp-manifest.json \
  CHANGELOG.md \
  README.md \
  requirements.txt
```

### Issue: "Manifest Validation Failed"
**Solution:**
```bash
# Validate JSON syntax
python -m json.tool memory_store_v2/mcp-manifest.json

# Check required fields
# - name, version, entry_point, capabilities
# - dependencies, permissions
```

### Issue: "Security Scan Failed"
**Solution:**
```bash
# Check specific vulnerabilities
cline security scan --level production --detailed

# Update vulnerable dependencies
pip install --upgrade <package-name>
```

## Quick Reference

### Commands Summary
```bash
# 1. Security check
cline security scan --level production

# 2. Compatibility check
cline compatibility validate --manifest memory_store_v2/mcp-manifest.json

# 3. Package
zip -r release/chainofthought-coder-v2.4.0.zip memory_store_v2/ mcp-manifest.json CHANGELOG.md README.md requirements.txt

# 4. Publish
cline marketplace publish --name "ChainOfThought Coder V2" --package release/chainofthought-coder-v2.4.0.zip --category "developer-tools" --api-key $CLINE_API_KEY
```

### Timeline
- **Day 1**: Pre-publication checks, packaging
- **Day 2-3**: Review process
- **Day 4-5**: Approval and publication
- **Day 6-7**: Live on marketplace

### Success Criteria
- ✅ No security vulnerabilities
- ✅ All tests passing
- ✅ Manifest validation passed
- ✅ Package size < 50MB
- ✅ Documentation complete
- ✅ API key valid

## Next Steps After Publication

1. **Marketing**
   - Share on social media
   - Post in developer communities
   - Update portfolio

2. **Support**
   - Monitor GitHub issues
   - Respond to user feedback
   - Create FAQ documentation

3. **Updates**
   - Plan regular releases (2-4 weeks)
   - Track feature requests
   - Maintain security updates

## Contact & Support

- **Cline Support**: https://support.cline.ai
- **Developer Forum**: https://forum.cline.ai
- **Documentation**: https://docs.cline.ai

---

**Ready to publish?** Follow this guide step-by-step for a successful marketplace launch!
