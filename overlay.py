"""
╔══════════════════════════════════════════════════════════════════╗
║                   VENTANA DE DEPURACIÓN (OVERLAY)               ║
║                                                                  ║
║  Dibuja sobre el frame de la cámara:                             ║
║    • Landmarks de la mano (21 puntos + conexiones)               ║
║    • Zona activa (rectángulo verde)                              ║
║    • Nombre del gesto detectado                                  ║
║    • Indicador de modo PAUSA                                     ║
║    • Métricas en tiempo real (openness, pinch, velocidad)        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import cv2
import numpy as np

log = logging.getLogger("OverlayWindow")

# ─── Paleta de colores (BGR) ───────────────────────────────────────────────────
COLOR_GREEN       = (0,   220,  80)
COLOR_RED         = (0,    50, 220)
COLOR_YELLOW      = (0,   210, 230)
COLOR_BLUE        = (220, 100,   0)
COLOR_WHITE       = (255, 255, 255)
COLOR_GRAY        = (160, 160, 160)
COLOR_ORANGE      = (0,   140, 255)
COLOR_PAUSE_BG    = (0,     0, 180)   # Fondo rojo para modo pausa
COLOR_LANDMARK    = (255, 180,   0)   # Cian para los puntos
COLOR_CONNECTION  = (200, 200, 200)   # Gris para las líneas

# Conexiones entre landmarks de MediaPipe (pares de índices)
MP_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),           # Pulgar
    (0,5),(5,6),(6,7),(7,8),           # Índice
    (0,9),(9,10),(10,11),(11,12),      # Medio
    (0,13),(13,14),(14,15),(15,16),    # Anular
    (0,17),(17,18),(18,19),(19,20),    # Meñique
    (5,9),(9,13),(13,17),              # Nudillos (palma)
]

# Mapeo gesto → color del texto
GESTURE_COLORS = {
    "PINCH":         COLOR_GREEN,
    "FIST":          COLOR_RED,
    "OPEN_HAND":     COLOR_WHITE,
    "TWO_FINGERS_UP":COLOR_BLUE,
    "SWIPE_RIGHT":   COLOR_ORANGE,
    "SWIPE_LEFT":    COLOR_ORANGE,
    "STOP_TOGGLE":   COLOR_YELLOW,
    "RIGHT_CLICK":   COLOR_RED,
}

# Etiquetas legibles para el usuario
GESTURE_LABELS = {
    "PINCH":          "CLIC IZQUIERDO",
    "FIST":           "DRAG (puño)",
    "OPEN_HAND":      "MANO ABIERTA",
    "TWO_FINGERS_UP": "SCROLL",
    "SWIPE_RIGHT":    "SWIPE → (Alt+Tab)",
    "SWIPE_LEFT":     "SWIPE ← (Alt+Shift+Tab)",
    "STOP_TOGGLE":    "⏸ PAUSA TOGGLE",
    "RIGHT_CLICK":    "CLIC DERECHO",
}


class OverlayWindow:
    """
    Dibuja información de depuración sobre el frame BGR de la cámara.
    Todas las operaciones son en memoria; no crea ventanas (eso lo hace main.py).
    """

    def __init__(self, cfg):
        self.cfg          = cfg
        self._last_gesture = None    # Para mantener el nombre unos frames
        self._gesture_ttl  = 0       # Frames restantes para mostrar el gesto

    def draw(self, frame: np.ndarray, hand_data, state: dict) -> np.ndarray:
        """
        Dibuja todos los elementos de depuración sobre `frame`.

        Args:
            frame:      np.ndarray BGR (se modifica in-place y se retorna)
            hand_data:  HandData o None
            state:      dict con claves "paused", "drag_active"

        Returns:
            frame modificado
        """
        h, w = frame.shape[:2]

        # ── Zona activa ───────────────────────────────────────────────────────
        if self.cfg.SHOW_ACTIVE_ZONE:
            self._draw_active_zone(frame, w, h)

        # ── Landmarks de la mano ──────────────────────────────────────────────
        if hand_data is not None and self.cfg.SHOW_HAND_LANDMARKS:
            self._draw_landmarks(frame, hand_data, w, h)
            self._draw_palm_crosshair(frame, hand_data, w, h)

        # ── Métricas numéricas ────────────────────────────────────────────────
        if hand_data is not None:
            self._draw_metrics(frame, hand_data)

        # ── Nombre del gesto ──────────────────────────────────────────────────
        if self.cfg.SHOW_GESTURE_NAME:
            self._draw_gesture_label(frame, w, h)

        # ── Modo PAUSA ────────────────────────────────────────────────────────
        if state.get("paused", False):
            self._draw_pause_banner(frame, w, h)

        # ── Drag activo ───────────────────────────────────────────────────────
        if state.get("drag_active", False):
            self._draw_drag_indicator(frame, w, h)

        # ── Instrucciones rápidas (esquina inferior derecha) ──────────────────
        self._draw_help(frame, w, h)

        return frame

    def update_gesture(self, gesture: str | None):
        """
        Notifica al overlay qué gesto se acaba de detectar.
        Lo muestra durante ~20 frames aunque el gesto ya no esté activo.
        """
        if gesture is not None:
            self._last_gesture = gesture
            self._gesture_ttl  = 20   # ~0.66s a 30fps
        elif self._gesture_ttl > 0:
            self._gesture_ttl -= 1
        else:
            self._last_gesture = None

    # ─────────────────────────────────────────────────────────────────────────
    #  MÉTODOS DE DIBUJO
    # ─────────────────────────────────────────────────────────────────────────

    def _draw_active_zone(self, frame, w, h):
        """Rectángulo de la zona activa en verde semitransparente."""
        cfg = self.cfg
        x1 = int(cfg.ACTIVE_ZONE_X_MIN * w)
        y1 = int(cfg.ACTIVE_ZONE_Y_MIN * h)
        x2 = int(cfg.ACTIVE_ZONE_X_MAX * w)
        y2 = int(cfg.ACTIVE_ZONE_Y_MAX * h)

        # Capa semitransparente
        overlay = frame.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, y2), COLOR_GREEN, -1)
        cv2.addWeighted(overlay, 0.05, frame, 0.95, 0, frame)

        # Borde sólido
        cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_GREEN, 1)

        # Etiqueta
        cv2.putText(
            frame, "ZONA ACTIVA",
            (x1 + 4, y1 + 14),
            cv2.FONT_HERSHEY_SIMPLEX, 0.38,
            COLOR_GREEN, 1, cv2.LINE_AA,
        )

    def _draw_landmarks(self, frame, hd, w, h):
        """Dibuja los 21 puntos y sus conexiones sobre la mano."""
        if hd.landmarks_px is None:
            return

        pts = hd.landmarks_px  # Lista de (x, y) en píxeles del frame original

        # Conexiones
        for a, b in MP_CONNECTIONS:
            if a < len(pts) and b < len(pts):
                cv2.line(frame, pts[a], pts[b], COLOR_CONNECTION, 1, cv2.LINE_AA)

        # Puntas de los dedos (índices 4, 8, 12, 16, 20) → círculo relleno mayor
        fingertips = {4, 8, 12, 16, 20}
        for i, pt in enumerate(pts):
            if i in fingertips:
                cv2.circle(frame, pt, 6, COLOR_LANDMARK, -1, cv2.LINE_AA)
                cv2.circle(frame, pt, 6, COLOR_WHITE, 1, cv2.LINE_AA)
            else:
                cv2.circle(frame, pt, 3, COLOR_LANDMARK, -1, cv2.LINE_AA)

    def _draw_palm_crosshair(self, frame, hd, w, h):
        """Cruz en el centroide de la palma (el punto que mueve el cursor)."""
        if hd.palm_position is None:
            return

        px = int(hd.palm_position[0] * w)
        py = int(hd.palm_position[1] * h)
        size = 10

        cv2.line(frame, (px - size, py), (px + size, py), COLOR_YELLOW, 2, cv2.LINE_AA)
        cv2.line(frame, (px, py - size), (px, py + size), COLOR_YELLOW, 2, cv2.LINE_AA)
        cv2.circle(frame, (px, py), 3, COLOR_YELLOW, -1, cv2.LINE_AA)

    def _draw_metrics(self, frame, hd):
        """Panel de métricas en la esquina superior izquierda."""
        metrics = [
            f"Apertura : {hd.openness:.2f}",
            f"Pellizco : {hd.pinch_distance:.3f}",
            f"Vel X    : {hd.palm_velocity[0]:+d} px",
            f"Vel Y    : {hd.palm_velocity[1]:+d} px",
            f"Mano     : {hd.hand_label} ({hd.confidence:.0%})",
        ]
        if hd.finger_states:
            names  = ["P", "I", "M", "A", "Me"]
            states = ["↑" if s else "↓" for s in hd.finger_states]
            metrics.append("Dedos  : " + " ".join(
                f"{n}{s}" for n, s in zip(names, states)
            ))

        x_start, y_start = 8, 18
        # Fondo negro semitransparente para legibilidad
        panel_h = len(metrics) * 16 + 8
        overlay = frame.copy()
        cv2.rectangle(overlay, (4, 4), (185, 4 + panel_h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

        for i, text in enumerate(metrics):
            cv2.putText(
                frame, text,
                (x_start, y_start + i * 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38,
                COLOR_GRAY, 1, cv2.LINE_AA,
            )

    def _draw_gesture_label(self, frame, w, h):
        """Nombre del gesto en grande en la parte inferior central."""
        # Actualizar TTL
        if self._gesture_ttl > 0:
            self._gesture_ttl -= 1
        else:
            self._last_gesture = None

        if self._last_gesture is None:
            return

        label  = GESTURE_LABELS.get(self._last_gesture, self._last_gesture)
        color  = GESTURE_COLORS.get(self._last_gesture, COLOR_WHITE)

        # Centrar texto
        font       = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 0.8
        thickness  = 2
        (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)

        tx = (w - tw) // 2
        ty = h - 20

        # Sombra para legibilidad sobre cualquier fondo
        cv2.putText(frame, label, (tx + 2, ty + 2), font, font_scale,
                    (0, 0, 0), thickness + 1, cv2.LINE_AA)
        cv2.putText(frame, label, (tx, ty), font, font_scale,
                    color, thickness, cv2.LINE_AA)

    def _draw_pause_banner(self, frame, w, h):
        """Banner rojo "⏸ MODO PAUSA" semitransparente."""
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h // 2 - 28), (w, h // 2 + 28),
                      COLOR_PAUSE_BG, -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        text = "  MODO PAUSA ACTIVO  (mantén palma abierta para reanudar)"
        font = cv2.FONT_HERSHEY_DUPLEX
        (tw, _), _ = cv2.getTextSize(text, font, 0.65, 2)
        tx = (w - tw) // 2
        cv2.putText(frame, text, (tx, h // 2 + 8), font, 0.65,
                    COLOR_YELLOW, 2, cv2.LINE_AA)

    def _draw_drag_indicator(self, frame, w, h):
        """Indicador pequeño "DRAG" en la esquina superior derecha."""
        cv2.putText(
            frame, "DRAG ACTIVO",
            (w - 130, 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5,
            COLOR_ORANGE, 2, cv2.LINE_AA,
        )
        # Icono de candado (círculo)
        cv2.circle(frame, (w - 18, 14), 7, COLOR_ORANGE, 2, cv2.LINE_AA)

    def _draw_help(self, frame, w, h):
        """Recordatorio de gestos en la esquina inferior derecha."""
        lines = [
            "PELLIZCO = Clic izq",
            "PUNO     = Drag",
            "2 DEDOS  = Scroll",
            "PALMA    = Pausa",
            "SWIPE    = Alt+Tab",
            "[Q]      = Salir",
        ]
        x_start = w - 170
        y_start = h - len(lines) * 15 - 8

        # Fondo
        overlay = frame.copy()
        cv2.rectangle(overlay,
                      (x_start - 4, y_start - 12),
                      (w - 2, h - 4),
                      (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)

        for i, line in enumerate(lines):
            cv2.putText(
                frame, line,
                (x_start, y_start + i * 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                COLOR_GRAY, 1, cv2.LINE_AA,
            )
