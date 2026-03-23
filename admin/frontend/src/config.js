/**
 * Application configuration
 * Values loaded from environment variables (VITE_*) with fallback defaults
 */
export const config = {
  // Artists API
  artistsApiUrl: import.meta.env.VITE_ARTISTS_API_URL || '',
  artistsApiKey: import.meta.env.VITE_ARTISTS_API_KEY || '',
  artistsPerPage: parseInt(import.meta.env.VITE_ARTISTS_PER_PAGE) || 20,

  // Polling interval (ms)
  pollInterval: parseInt(import.meta.env.VITE_POLL_INTERVAL) || 3000,

  // Download defaults
  defaultScanMaxPages: parseInt(import.meta.env.VITE_DEFAULT_SCAN_MAX_PAGES) || 30,
  defaultDownloadDepth: parseInt(import.meta.env.VITE_DEFAULT_DOWNLOAD_DEPTH) || 5,
  defaultServerPort: parseInt(import.meta.env.VITE_DEFAULT_SERVER_PORT) || 3000,
  defaultBackendPort: parseInt(import.meta.env.VITE_DEFAULT_BACKEND_PORT) || 3001,
}
