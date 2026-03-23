/**
 * Wrapper around fetch() with automatic response.ok check and error handling
 *
 * @param {string} url - URL to fetch
 * @param {RequestInit} [options] - fetch options
 * @returns {Promise<Response>} - response object (only if ok)
 * @throws {Error} - with server error message
 */
export async function fetchApi(url, options = {}) {
  const response = await fetch(url, options)

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}`
    try {
      const data = await response.json()
      errorMessage = data.error || data.detail?.error || data.detail || data.message || errorMessage
    } catch {
      // response body is not JSON
      try {
        const text = await response.text()
        if (text) errorMessage = text.substring(0, 200)
      } catch {
        // ignore
      }
    }
    throw new Error(errorMessage)
  }

  return response
}

/**
 * fetchApi + parse JSON response
 *
 * @param {string} url - URL to fetch
 * @param {RequestInit} [options] - fetch options
 * @returns {Promise<any>} - parsed JSON data
 */
export async function fetchJson(url, options = {}) {
  const response = await fetchApi(url, options)
  return response.json()
}
