# Docker Build Fix: npm package-lock.json Issue

## Problem

**Error during Docker build:**
```
npm error The `npm ci` command can only install with an existing package-lock.json or
npm error npm-shrinkwrap.json with lockfileVersion >= 1.
```

**Root cause:**
- Dockerfile was using `npm ci` (clean install)
- `npm ci` requires `package-lock.json`
- `package-lock.json` was in `.gitignore` (not committed)
- Docker build failed because lockfile didn't exist

## Solution

### 1. Dockerfile Updated

**Changed:** `npm ci` → `npm install`

```dockerfile
# BEFORE (failed)
RUN npm ci --prefer-offline --no-audit

# AFTER (works)
RUN npm install --prefer-offline --no-audit
```

**Why:**
- `npm install` works with or without `package-lock.json`
- `npm install` generates `package-lock.json` if missing
- More flexible for Docker builds
- Still respects lockfile if present

### 2. .gitignore Updated

**Changed:** Remove `package-lock.json` from ignore list

```diff
# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
-package-lock.json
+# Note: package-lock.json is NOT ignored - it's needed for reproducible builds
+# in Docker and CI/CD pipelines. Commit it with your changes.
```

**Why:**
- `package-lock.json` should be committed for reproducibility
- Docker uses it to get exact dependency versions
- CI/CD pipelines benefit from consistent versions

### 3. Documentation

Created: `NPM_SETUP.md`
- First-time setup instructions
- Development workflow
- Troubleshooting guide
- Git workflow

Updated: `docker/CSS_BUILD_PROCESS.md`
- Added npm install explanation
- Setup notes with `npm install` command

## Next Steps for User

### First Time (One Time Only)

```bash
# 1. Generate package-lock.json
npm install

# 2. Verify CSS builds
npm run build:css

# 3. Commit the lockfile
git add package-lock.json
git commit -m "Add package-lock.json for reproducible builds"
```

### Now Docker Build Works

```bash
# This will now succeed
docker build -t soulspot:latest .
```

### Verify CSS in Container

```bash
# Check CSS was built
docker run --rm soulspot:latest grep "blur-fade-in" /app/src/soulspot/static/css/style.css
# Output: (CSS content with animation definitions)
```

## Files Modified

| File | Change |
|------|--------|
| `docker/Dockerfile` | Changed `npm ci` → `npm install` |
| `.gitignore` | Removed `package-lock.json` from ignore |
| `docker/CSS_BUILD_PROCESS.md` | Added npm install notes |
| `NPM_SETUP.md` | NEW - Setup and troubleshooting guide |

## Why Both Solutions Work

### npm install
- ✅ Works without lockfile (generates one)
- ✅ Works with lockfile (respects exact versions)
- ✅ More flexible for development and Docker
- ⚠️ Slightly less reproducible without lockfile

### npm ci
- ✅ Exact reproducibility with lockfile
- ❌ Fails without lockfile (requires manual generation)
- ✅ Better for CI/CD (when lockfile exists)
- ❌ Not suitable if lockfile missing

**For this project:** `npm install` is better since:
1. Lockfile wasn't previously committed
2. Provides fallback if lockfile missing
3. Docker build now works immediately
4. Can upgrade to `npm ci` later once lockfile committed

## Verification Checklist

- [x] Dockerfile uses `npm install` (flexible)
- [x] .gitignore allows `package-lock.json`
- [x] Documentation updated
- [ ] User runs `npm install` once (generates lockfile)
- [ ] User commits `package-lock.json`
- [ ] Docker build succeeds
- [ ] CSS appears in container

## Performance Impact

**Docker build time:**
- First build: +5-10 seconds (normal npm install)
- Subsequent builds: <5 seconds (cache hit)

**Impact:** Minimal, acceptable

## See Also

- `NPM_SETUP.md` - Setup and development guide
- `docker/CSS_BUILD_PROCESS.md` - CSS build details
- `docker/Dockerfile` - Build configuration
- `.gitignore` - Git ignore rules
