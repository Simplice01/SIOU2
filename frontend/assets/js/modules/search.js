/**
 * search.js
 * Filtrage instantané côté client d'une liste d'éléments,
 * générique et réutilisable sur plusieurs pages (historique, documents...).
 *
 * Usage HTML :
 *   <input data-search-input data-search-target=".doc-list" data-search-item=".doc-card">
 * Chaque item filtrable doit exposer son texte de recherche via [data-search-text]
 * ou, à défaut, son propre textContent est utilisé.
 */

import { debounce, qs, qsa } from './utils.js';

function normalize(str) {
  return str
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, ''); // retire les accents pour une recherche tolérante
}

export function initInstantSearch() {
  qsa('[data-search-input]').forEach((input) => {
    const targetSelector = input.dataset.searchTarget;
    const itemSelector = input.dataset.searchItem;
    const container = targetSelector ? qs(targetSelector) : document;
    const emptyState = qs('[data-search-empty]', container?.parentElement || document);

    const runFilter = debounce(() => {
      const query = normalize(input.value.trim());
      const items = qsa(itemSelector, container);
      let visibleCount = 0;

      items.forEach((item) => {
        const text = normalize(item.dataset.searchText || item.textContent);
        const matches = query === '' || text.includes(query);
        item.hidden = !matches;
        if (matches) visibleCount += 1;
      });

      if (emptyState) emptyState.hidden = visibleCount !== 0;
    }, 180);

    input.addEventListener('input', runFilter);
  });
}
