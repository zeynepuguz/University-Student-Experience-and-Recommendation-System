// Prod'da .env.production içindeki VITE_API_URL kullanılır.
// Yoksa yerel backend'e düşer.
export const API_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
