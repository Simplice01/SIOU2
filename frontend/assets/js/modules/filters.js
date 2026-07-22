/**
 * filters.js
 * Filtres par catégorie (puces cliquables) appliqués à une liste d'items.
 * Usage HTML :
 *   <div data-filter-group data-filter-target=".doc-list" data-filter-item=".doc-card">
 *     <button data-filter-value="all" class="is-active">Tout</button>
 *     <button data-filter-value="guide">Guides</button>
 *   </div>
 * Chaque item doit porter data-filter-category="guide" (une ou plusieurs valeurs séparées par un espace).
 */

import { qs, qsa } from './utils.js';

export function initFilters() {
  qsa('[data-filter-group]').forEach((group) => {
    const container = qs(group.dataset.filterTarget);
    const itemSelector = group.dataset.filterItem;
    const buttons = qsa('[data-filter-value]', group);

    buttons.forEach((btn) => {
      btn.addEventListener('click', () => {
        buttons.forEach((b) => b.classList.remove('is-active'));
        btn.classList.add('is-active');

        const value = btn.dataset.filterValue;
        qsa(itemSelector, container).forEach((item) => {
          const categories = (item.dataset.filterCategory || '').split(' ');
          item.hidden = value !== 'all' && !categories.includes(value);
        });
      });
    });
  });
}
