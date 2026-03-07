# AgentPier Backup Procedures

## Git Repository Backup

### Remotes
- **Primary**: `origin` → https://github.com/gatewaybuddy/agentpier.git (public components)
- **Private**: `private` → https://github.com/gatewaybuddy/agentpier-private.git (sensitive configs)

### Backup Frequency
- **After major features**: API changes, V-Token updates, business model changes
- **Before deployments**: Production releases, infrastructure changes
- **Weekly**: Routine development progress

### Critical Files
- `/src/` - Core V-Token verification system
- `/docs/` - API reference and integration guides  
- `/config/` - Business model and pricing configuration
- `package.json` - Dependencies and scripts
- `README.md` - Setup and usage documentation

### Backup Commands
```bash
# Check backup status
git status
git log --oneline origin/master..master

# Backup routine
git add .
git commit -m "descriptive message"
git push origin master
git push private master  # if sensitive changes
```

### Recovery Testing
- Clone from remote monthly
- Verify API examples in README work
- Test V-Token verification with sample data

### Monitoring
- Check `git status` for uncommitted work daily
- Verify push status before major releases
- Document significant architectural changes

## Current Status
- **Last Verified**: 2026-03-07 02:25 AM
- **Backup Gap**: 18 commits + 2 modified files need push
- **Risk Level**: HIGH - Recent V-Token work not backed up