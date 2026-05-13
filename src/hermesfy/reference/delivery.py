"""Delivery — descarga imágenes de Fal.ai y prepara para entrega vía MEDIA.

Fase 4 del pipeline VRH:
  image_url (Fal.ai) → download → save → MEDIA path → Telegram
"""

from __future__ import annotations

import logging
import os
import ipaddress
import socket
import requests
import time
from pathlib import Path
from tempfile import gettempdir
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger("hermesfy.reference.delivery")


class Delivery:
    """Maneja la descarga y entrega de imágenes generadas."""

    # Los outputs de Fal.ai expiran — descargar inmediatamente
    DEFAULT_OUTPUT_DIR = os.path.join(gettempdir(), "hermesfy_outputs")

    @staticmethod
    def _is_public_http_url(image_url: str) -> bool:
        try:
            parsed = urlparse(image_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                return False
            host = parsed.hostname
            for _family, _socktype, _proto, _canonname, sockaddr in socket.getaddrinfo(host, None):
                ip = ipaddress.ip_address(sockaddr[0])
                if (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_multicast
                    or ip.is_reserved
                    or ip.is_unspecified
                ):
                    return False
            return True
        except Exception:
            return False

    def __init__(self, output_dir: str | None = None):
        self.output_dir = output_dir or self.DEFAULT_OUTPUT_DIR
        os.makedirs(self.output_dir, exist_ok=True)
        self._last_path: str | None = None

    def download(self, image_url: str, filename: str | None = None) -> str:
        """Descargar imagen desde URL de Fal.ai.

        Args:
            image_url: URL pública de la imagen generada (Fal.ai).
            filename: Nombre opcional del archivo. Si no se provee, se genera.

        Returns:
            Ruta absoluta al archivo descargado.
        """
        if not self._is_public_http_url(image_url):
            raise ValueError("Blocked non-public or invalid URL for image download")

        if not filename:
            timestamp = int(time.time())
            filename = f"hermesfy_vrh_{timestamp}.png"

        output_path = os.path.join(self.output_dir, filename)

        logger.info("Downloading image from %s → %s", image_url[:60], output_path)

        try:
            resp = requests.get(image_url, timeout=60)
            resp.raise_for_status()

            with open(output_path, "wb") as f:
                f.write(resp.content)

            self._last_path = output_path
            logger.info("Downloaded %d bytes to %s", len(resp.content), output_path)
            return output_path

        except requests.RequestException as e:
            logger.error("Failed to download image: %s", e)
            raise

    @property
    def last_media_path(self) -> str | None:
        """Obtener la ruta del último archivo descargado (para enviar como MEDIA)."""
        return self._last_path

    @staticmethod
    def get_media_tag(filepath: str) -> str:
        """Obtener tag MEDIA para inyectar en respuesta de Telegram."""
        return f"MEDIA:{filepath}"

    @staticmethod
    def extract_url_from_fal_response(fal_response: dict) -> str | None:
        """Extraer URL de imagen desde respuesta de Fal.ai.

        Fal.ai puede devolver el resultado en distintos formatos:
        - {"images": [{"url": "..."}]}
        - {"image": {"url": "..."}}
        - {"output": "https://..."}
        - {"url": "..."}
        """
        # Formato más común: images[].url
        if "images" in fal_response and isinstance(fal_response["images"], list):
            for img in fal_response["images"]:
                if isinstance(img, dict) and "url" in img:
                    return img["url"]

        # Formato: image.url
        if "image" in fal_response and isinstance(fal_response["image"], dict):
            return fal_response["image"].get("url")

        # Formato: output como string directo
        if "output" in fal_response and isinstance(fal_response["output"], str):
            return fal_response["output"]

        # Formato: url directo
        if "url" in fal_response:
            return fal_response["url"]

        logger.warning("Could not extract image URL from Fal.ai response: keys=%s",
                       list(fal_response.keys()))
        return None
