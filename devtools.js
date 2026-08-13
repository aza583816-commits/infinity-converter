// =====================================================================================
// devtools.js — أدوات المطورين: Base64 / URL / JSON / Minify / Hash / Timestamp
// =====================================================================================

const crypto = require('crypto');
let terser, CleanCSS;
try {
  terser = require('terser');
} catch (e) {
  /* optional dependency */
}
try {
  CleanCSS = require('clean-css');
} catch (e) {
  /* optional dependency */
}

const handlers = {
  async 'base64-tool'({ res, text }) {
    let result;
    try {
      const decoded = Buffer.from(text, 'base64').toString('utf-8');
      const reEncoded = Buffer.from(decoded, 'utf-8').toString('base64');
      result =
        reEncoded.replace(/=+$/, '') === text.trim().replace(/=+$/, '')
          ? decoded
          : Buffer.from(text, 'utf-8').toString('base64');
    } catch (e) {
      result = Buffer.from(text, 'utf-8').toString('base64');
    }
    return res.status(200).json({ result });
  },

  async 'url-encoder'({ res, text }) {
    let result;
    try {
      const decoded = decodeURIComponent(text);
      result = decoded !== text ? decoded : encodeURIComponent(text);
    } catch (e) {
      result = encodeURIComponent(text);
    }
    return res.status(200).json({ result });
  },

  async 'json-beautifier'({ res, text }) {
    return res.status(200).json({ result: JSON.stringify(JSON.parse(text), null, 4) });
  },

  async 'css-js-minifier'({ res, text }) {
    let result = null;
    const looksLikeCss = /\{[^{}]*:[^{}]*;?[^{}]*\}/.test(text) && !/function|=>|const |let |var /.test(text);
    if (looksLikeCss && CleanCSS) {
      try {
        result = new CleanCSS({}).minify(text).styles;
      } catch (e) {
        /* fallthrough */
      }
    }
    if (!result && terser) {
      try {
        const out = await terser.minify(text);
        if (out.code) result = out.code;
      } catch (e) {
        /* fallthrough */
      }
    }
    if (!result) result = text.replace(/\/\*[\s\S]*?\*\/|\/\/.*/g, '').replace(/\s+/g, ' ').trim();
    return res.status(200).json({ result });
  },

  async 'html-entity'({ res, text }) {
    const result = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
    return res.status(200).json({ result });
  },

  async 'hash-generator'({ res, text }) {
    const md5 = crypto.createHash('md5').update(text).digest('hex');
    const sha1 = crypto.createHash('sha1').update(text).digest('hex');
    const sha256 = crypto.createHash('sha256').update(text).digest('hex');
    const sha512 = crypto.createHash('sha512').update(text).digest('hex');
    return res.status(200).json({ result: `MD5: ${md5}\nSHA-1: ${sha1}\nSHA-256: ${sha256}\nSHA-512: ${sha512}` });
  },

  async 'timestamp-converter'({ res, text }) {
    return res.status(200).json({ result: new Date(parseInt(text.trim(), 10) * 1000).toUTCString() });
  },

  async 'clean-text'({ res, text }) {
    return res.status(200).json({ result: text.replace(/<[^>]*>?/gm, '').replace(/&nbsp;/g, ' ').trim() });
  },
};

module.exports = { handlers };
