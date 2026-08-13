const ALLOWED_ORIGINS = [
  'https://www.infinityconverter.com',
  'https://infinityconverter.com',
];

function isAllowedOrigin(origin) {
  if (!origin) return false;
  if (ALLOWED_ORIGINS.includes(origin)) return true;
  if (/^https:\/\/[a-z0-9-]+\.vercel\.app$/.test(origin)) return true;
  return false;
}

function applyCors(req, res) {
  const origin = req.headers.origin;
  if (isAllowedOrigin(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin);
  }
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Access-Control-Max-Age', '86400');

  if (req.method === 'OPTIONS') {
    res.status(204).end();
    return true;
  }

  if (origin && !isAllowedOrigin(origin)) {
    res.status(403).json({ error: 'Forbidden: origin not allowed' });
    return true;
  }
  return false;
}

module.exports = { applyCors };
