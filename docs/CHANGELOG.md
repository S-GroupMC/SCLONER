# Changelog

## v2.1.0 (2026-04-01)

### Critical Bug Fix
- **reject-regex `.*t.co.*` blocking legitimate domains** - Pattern `.*t.co.*` matched `ibighit.com` as substring. Refactored entire domain blocking system:
  - `BLOCKED_DOMAINS` now uses exact/suffix matching (never substring)
  - Added `BLOCKED_DOMAIN_PREFIXES` for `ads.`, `tracking.`, `pixel.` etc.
  - Added `BLOCKED_URL_PATHS` for path-based blocking (`/tr?`, `/px?`)
  - New `is_domain_blocked()` function with proper boundary checks
  - Fixed reject-regex generation: `(://|\.)domain(/|$)` instead of `.*domain.*`
  - Fixed httrack blocked domain patterns

### Bug Fixes
- **cleanup deleting downloaded folders** - `cleanup_external_domains` now logs every KEEP/REMOVE decision
- **update_job_stats counting wrong files** - Excluded `vue-app/`, `_wcloner/`, `node_modules/` from file count
- **check_domain_downloaded** false positives fixed

### Server Management
- Unique server ports starting from 5600 (was 3000)
- Port registry in `_wcloner/ports.json` per site
- Server registry in `_wcloner_servers.json`

### UI Improvements
- Port badge next to running server status
- Stop button in server modal
- Vite restart button

### Vite / Vue Wrapper
- Subdomain support in `vite.config.js`
- `mainDomain` read from `_wcloner/landing.json` (single source of truth)
- Removed white iframe border

### Download Engine
- Disabled `-k` (convert links) in wget2
- Exit code 8 partial success handling
- Auto html_cleaner after download

### Other
- `.gitignore`: exclude runtime files (`jobs.json`, `_wcloner_servers.json`)

## v2.0.0

- Initial FastAPI version
- Vue 3 frontend
- wget2 / httrack / puppeteer engines
- Domain filtering and cleanup
