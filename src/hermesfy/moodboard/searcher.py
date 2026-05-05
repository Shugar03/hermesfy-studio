"""Searcher — Pinterest scraper para moodboards.

Multiples fuentes con fallback:
1. Pinterest (Playwright headless) — principal
2. Brave Image Search — fallback si Pinterest falla
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from hermesfy.moodboard.templates.search_templates import (
    generate_queries,
    score_image,
)

logger = logging.getLogger("hermesfy.moodboard.searcher")

PINTEREST_PROFILE = Path.home() / ".cache" / "pinterest-profile"
BROWSER_TIMEOUT = 20000


class PinterestSearcher:
    """Scraper de Pinterest vía Playwright."""

    def __init__(self):
        self._playwright = None
        self._context = None
        self._page = None

    def _ensure_browser(self):
        """Lanza el browser si no está iniciado."""
        if self._page is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            # Usar xvfb-run si estamos en headless
            self._context = self._pw.firefox.launch_persistent_context(
                user_data_dir=str(PINTEREST_PROFILE),
                headless=False,  # xvfb-run lo maneja
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
            )
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()

    def _close_browser(self):
        if self._context:
            self._context.close()
        if self._pw:
            self._pw.stop()
        self._page = None
        self._context = None
        self._pw = None

    def _extract_images(self, page) -> list[dict]:
        """Extrae imágenes del DOM de Pinterest y las convierte a 736px."""
        results = page.evaluate("""() => {
            const imgs = document.querySelectorAll('img[src*="pinimg"]');
            const seen = new Set();
            const out = [];
            for (const img of imgs) {
                let s = img.src || '';
                if (!s.includes('pinimg')) continue;
                const parts = s.split('/');
                for (let i = 0; i < parts.length; i++) {
                    if (/^\\d+x\\d*$/.test(parts[i]) && i > 2) {
                        parts[i] = '736x';
                        break;
                    }
                }
                s = parts.join('/');
                if (!seen.has(s) && s.includes('736x')) {
                    seen.add(s);
                    out.push({ url: s, alt: img.alt || '' });
                }
            }
            return out;
        }""")
        return results

    def search_pinterest(
        self,
        queries: list[str],
        scrolls: int = 4,
        max_images: int = 50,
    ) -> list[dict]:
        """Busca imágenes en Pinterest a partir de queries."""
        self._ensure_browser()
        page = self._page
        all_results = []
        seen_urls = set()

        for q_idx, query in enumerate(queries):
            logger.info("Search [%d/%d]: %s", q_idx + 1, len(queries), query)
            try:
                page.goto(
                    f"https://www.pinterest.com/search/pins/?q={quote(query)}",
                    wait_until="domcontentloaded",
                    timeout=BROWSER_TIMEOUT,
                )
                page.wait_for_timeout(3000)

                for _ in range(scrolls):
                    page.evaluate("window.scrollBy(0, 900)")
                    page.wait_for_timeout(1000)

                results = self._extract_images(page)
                for r in results:
                    if r["url"] not in seen_urls:
                        seen_urls.add(r["url"])
                        all_results.append(r)

                logger.debug("  → +%d nuevas (total: %d)", len(results), len(all_results))
            except Exception as e:
                logger.warning("  Query '%s' failed: %s", query, e)
                continue

        return all_results[:max_images]

    def scrape_board(self, board_url: str, max_images: int = 30) -> list[dict]:
        """Scrapea un board completo de Pinterest."""
        self._ensure_browser()
        logger.info("Scraping board: %s", board_url)
        try:
            resp = self._page.goto(
                board_url,
                wait_until="domcontentloaded",
                timeout=BROWSER_TIMEOUT,
            )
            self._page.wait_for_timeout(4000)

            # Scroll para cargar todos los pins
            for _ in range(6):
                self._page.evaluate("window.scrollBy(0, 900)")
                self._page.wait_for_timeout(1000)

            results = self._extract_images(self._page)
            logger.info("Board scraped: %d images", len(results))
            return results[:max_images]
        except Exception as e:
            logger.error("Board scrape failed: %s", e)
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._close_browser()


def search_moodboard_sources(
    concept: str,
    format: str = "default",
    source: str = "pinterest_search",
    source_url: str | None = None,
    max_images: int = 50,
) -> list[dict]:
    """Punto de entrada unificado: busca imágenes para moodboard.

    Args:
        concept: Concepto del usuario ("hotel lujo selva")
        format: Categoría de formato (advertising, editorial, social_media, ...)
        source: Fuente de imágenes
        source_url: URL de board si source='pinterest_board'
        max_images: Máximo de imágenes a devolver

    Returns:
        Lista de dicts con {url, alt}
    """
    concept_keywords = concept.lower().split()

    if source == "pinterest_board" and source_url:
        # Scrapear board
        with PinterestSearcher() as searcher:
            results = searcher.scrape_board(source_url, max_images)
            for r in results:
                r["score"] = score_image(r["alt"], concept_keywords)
            results.sort(key=lambda x: x["score"], reverse=True)
            return results

    elif source in ("pinterest_search", "search", "pinterest"):
        # Búsqueda por queries
        queries = generate_queries(concept, format)
        with PinterestSearcher() as searcher:
            results = searcher.search_pinterest(queries, max_images=max_images)
            for r in results:
                r["score"] = score_image(r["alt"], concept_keywords)
            results.sort(key=lambda x: x["score"], reverse=True)
            return results

    elif source == "uploads":
        # Imágenes subidas por usuario (no necesitan búsqueda)
        return []

    else:
        logger.warning("Unknown source '%s', falling back to pinterest_search", source)
        return search_moodboard_sources(concept, format, "pinterest_search", None, max_images)
