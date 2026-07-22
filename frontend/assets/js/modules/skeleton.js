/**
 * skeleton.js
 * Affiche un état de chargement squelette pendant un délai simulé,
 * puis révèle le contenu réel. À utiliser avec deux blocs frères
 * portant [data-skeleton] et [data-skeleton-content].
 */

import { qsa } from './utils.js';

/**
 * @param {number} minDelay - délai minimal avant révélation (ms)
 */
export function initSkeletonLoaders(minDelay = 500) {
  const skeletons = qsa('[data-skeleton]');
  if (skeletons.length === 0) return;

  skeletons.forEach((skeleton) => {
    const content = skeleton.nextElementSibling;
    if (!content || !content.hasAttribute('data-skeleton-content')) return;

    const delay = minDelay + Math.random() * 400;
    setTimeout(() => {
      skeleton.style.display = 'none';
      content.hidden = false;
      content.classList.add('animate-fade-in');
    }, delay);
  });
}
