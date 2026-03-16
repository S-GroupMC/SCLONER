# Все артисты (первые 100)
curl -H "X-API-Key: sk-stickets-public-2026" \
  "https://adminzone.space/api/v1/public/artists"

# Только с лендингами
curl -H "X-API-Key: sk-stickets-public-2026" \
  "https://adminzone.space/api/v1/public/artists?has_landing=true"

# Поиск
curl -H "X-API-Key: sk-stickets-public-2026" \
  "https://adminzone.space/api/v1/public/artists?search=ariana"

# Один артист
curl -H "X-API-Key: sk-stickets-public-2026" \
  "https://adminzone.space/api/v1/public/artists/K8vZ9172Qo7"

  API ключ sk-stickets-public-2026 - дефолтный. Можно переопределить через PUBLIC_API_KEY в env.