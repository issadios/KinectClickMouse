"""
╔══════════════════════════════════════════════════════════════════╗
║                    CONTROLADOR DEL MOUSE                         ║
║                                                                  ║
║  Mapea las coordenadas de la mano a coordenadas de pantalla      ║
║  aplicando:                                                      ║
║    1. Recorte a la zona activa                                    ║
║    2. Normalización [0,1]                                        ║
║    3. Filtro de suavizado exponencial                            ║
║    4. Zona muerta (dead zone) para eliminar temblor              ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import pyautogui

log = logging.getLogger("MouseController")


class MouseController:
    """
    Convierte la posición normalizada de la mano en movimientos reales
    del cursor del ratón.
    """

    def __init__(self, cfg):
        self.cfg  = cfg

        # Posición suavizada actual (en píxeles de pantalla)
        pos = pyautogui.position()
        self._smooth_x = float(pos.x)
        self._smooth_y = float(pos.y)

    def move(self, palm_position):
        """
        Mueve el cursor a partir de la posición normalizada de la palma.

        Args:
            palm_position: (x_norm, y_norm) en [0.0, 1.0]
                           donde (0,0) es la esquina superior izquierda
                           del frame del Kinect.
        """
        x_norm, y_norm = palm_position

        # ── 1. Recortar a la zona activa ──────────────────────────────────────
        #  Si la mano está fuera de la zona activa, se ancla al borde.
        x_clamped = max(self.cfg.ACTIVE_ZONE_X_MIN,
                        min(self.cfg.ACTIVE_ZONE_X_MAX, x_norm))
        y_clamped = max(self.cfg.ACTIVE_ZONE_Y_MIN,
                        min(self.cfg.ACTIVE_ZONE_Y_MAX, y_norm))

        # ── 2. Remap a [0,1] dentro de la zona activa ────────────────────────
        zone_w = self.cfg.ACTIVE_ZONE_X_MAX - self.cfg.ACTIVE_ZONE_X_MIN
        zone_h = self.cfg.ACTIVE_ZONE_Y_MAX - self.cfg.ACTIVE_ZONE_Y_MIN

        x_mapped = (x_clamped - self.cfg.ACTIVE_ZONE_X_MIN) / zone_w
        y_mapped = (y_clamped - self.cfg.ACTIVE_ZONE_Y_MIN) / zone_h

        # ── 3. Convertir a píxeles de pantalla ───────────────────────────────
        target_x = x_mapped * self.cfg.SCREEN_W
        target_y = y_mapped * self.cfg.SCREEN_H

        # ── 4. Filtro de suavizado exponencial (EMA) ──────────────────────────
        #
        #  new_smooth = alpha * target + (1 - alpha) * prev_smooth
        #
        #  Con alpha=0.25:  el cursor "persigue" la mano gradualmente,
        #  eliminando el temblor de alta frecuencia pero sin perder
        #  demasiada responsividad.
        alpha = self.cfg.SMOOTHING_ALPHA
        self._smooth_x = alpha * target_x + (1 - alpha) * self._smooth_x
        self._smooth_y = alpha * target_y + (1 - alpha) * self._smooth_y

        # ── 5. Zona muerta ────────────────────────────────────────────────────
        #  Solo mueve el cursor si el desplazamiento supera el umbral.
        #  Evita micro-movimientos cuando la mano está "quieta".
        cur_pos = pyautogui.position()
        dx = abs(self._smooth_x - cur_pos.x)
        dy = abs(self._smooth_y - cur_pos.y)

        if dx > self.cfg.DEAD_ZONE_PX or dy > self.cfg.DEAD_ZONE_PX:
            # moveTo con duration=0 es la forma más rápida
            pyautogui.moveTo(
                int(self._smooth_x),
                int(self._smooth_y),
                duration=0,
                _pause=False,
            )

    def force_position(self, x_px, y_px):
        """Fuerza el cursor a una posición exacta (útil para pruebas)."""
        self._smooth_x = float(x_px)
        self._smooth_y = float(y_px)
        pyautogui.moveTo(x_px, y_px, duration=0, _pause=False)

    def reset_smooth(self):
        """Resetea el estado del suavizado a la posición actual del cursor."""
        pos = pyautogui.position()
        self._smooth_x = float(pos.x)
        self._smooth_y = float(pos.y)
