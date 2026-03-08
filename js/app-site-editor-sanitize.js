(function initSiteEditorSanitizer() {
  const BLOCKED_TAGS = new Set(['script', 'style', 'iframe', 'object', 'embed', 'link', 'meta', 'base']);
  const ALLOWED_TAGS = new Set([
    'a', 'abbr', 'b', 'blockquote', 'br', 'code', 'div', 'em', 'figcaption', 'figure',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'li', 'ol', 'p', 'pre',
    'small', 'span', 'strong', 'sub', 'sup', 'u', 'ul'
  ]);
  const ALLOWED_ATTR = new Set(['href', 'src', 'alt', 'title', 'target', 'rel', 'class', 'aria-label']);

  function sanitizeUrlValue(name, value) {
    const text = String(value || '').trim();
    if (!text) return '';
    if (name === 'href') {
      if (/^https?:\/\//i.test(text) || text.startsWith('/') || text.startsWith('#') || text.startsWith('mailto:')) {
        return text;
      }
      return '#';
    }
    if (name === 'src') {
      if (/^https?:\/\//i.test(text) || text.startsWith('/') || text.startsWith('data:image/')) {
        return text;
      }
      return '';
    }
    return text;
  }

  window.weaveSanitizeSiteEditableHtml = function weaveSanitizeSiteEditableHtml(value) {
    const html = String(value || '');
    const parser = new DOMParser();
    const doc = parser.parseFromString(`<div>${html}</div>`, 'text/html');
    const root = doc.body.firstElementChild;
    if (!root) return '';

    const walker = doc.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
    const removeQueue = [];
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const tag = String(node.tagName || '').toLowerCase();
      if (BLOCKED_TAGS.has(tag) || !ALLOWED_TAGS.has(tag)) {
        removeQueue.push(node);
        continue;
      }
      Array.from(node.attributes).forEach((attr) => {
        const name = String(attr.name || '').toLowerCase();
        if (name.startsWith('on') || !ALLOWED_ATTR.has(name)) {
          node.removeAttribute(attr.name);
          return;
        }
        if (name === 'href' || name === 'src') {
          const next = sanitizeUrlValue(name, attr.value);
          if (!next) {
            node.removeAttribute(attr.name);
          } else {
            node.setAttribute(attr.name, next);
          }
          if (name === 'href' && node.getAttribute('target') === '_blank' && !node.getAttribute('rel')) {
            node.setAttribute('rel', 'noopener noreferrer');
          }
        }
      });
    }

    removeQueue.forEach((node) => {
      node.replaceWith(...Array.from(node.childNodes));
    });

    return root.innerHTML;
  };
})();
