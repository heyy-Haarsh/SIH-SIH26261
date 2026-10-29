/**
 * Product walkthrough / pitch video shown on the home page.
 *
 * Prefer env (frontend/.env):
 *   VITE_PROTOTYPE_VIDEO_URL=https://…
 *
 * Or paste a YouTube / Drive / Loom URL into FALLBACK below for local demos.
 */
const FALLBACK_PROTOTYPE_VIDEO_URL =
  '' // e.g. 'https://www.youtube.com/watch?v=…' or a Google Drive share link

export const PROTOTYPE_VIDEO_URL =
  (import.meta.env.VITE_PROTOTYPE_VIDEO_URL as string | undefined)?.trim() ||
  FALLBACK_PROTOTYPE_VIDEO_URL.trim() ||
  '#video-prototype'
