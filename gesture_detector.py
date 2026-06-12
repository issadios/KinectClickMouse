"""
╔══════════════════════════════════════════════════════════════════╗
║                     DETECTOR DE GESTOS                           ║
║                                                                  ║
║  Gestos implementados:                                           ║
║    PINCH        → Clic izquierdo (índice + pulgar juntos)        ║
║    FIST         → Inicio de Drag & Drop (puño cerrado)           ║
║    OPEN_HAND    → Soltar drag / confirmar pausa                  ║
║    TWO_FINGERS  → Scroll (índice + medio extendidos)             ║
║    SWIPE_RIGHT  → Alt+Tab  (movimiento rápido derecha)           ║
║    SWIPE_LEFT   → Alt+Shift+Tab (movimiento rápido izquierda)    ║
║    STOP_TOGGLE  → Activa / desactiva el modo pausa               ║
║    RIGHT_CLICK  → Clic derecho (puño rápido y suelto)            ║
╚══════════════════════════════════════════════════════════════════╝
"""

import time
import logging
from collections import deque

log = logging.getLogger("GestureDetector")


class GestureDetector:
    """
    Recibe un objeto HandData en cada frame y decide qué gesto
    está ejecutando el usuario.

    Mecanismo de confirmación:
        Para evitar gestos accidentales, cada gesto debe mantenerse
        durante GESTURE_CONFIRM_FRAMES frames consecutivos antes de
        dispararse. Los swipes y la pausa tienen su propia lógica.
    """

    def __init__(self, cfg):
        self.cfg = cfg

        # ── Cooldowns por gesto (evita disparos repetidos) ────────────────────
        # { nombre_gesto: timestamp_hasta_cuando_está_bloqueado }
        self._cooldowns: dict[str, float] = {}

        # ── Historial de gestos (para confirmación) ───────────────────────────
        # Últimos N gestos candidatos detectados frame a frame
        self._history: deque[str] = deque(
            maxlen=max(cfg.GESTURE_CONFIRM_FRAMES, cfg.STOP_GESTURE_FRAMES) + 2
        )

        # ── Estado del scroll ────────────────────────────────────────────────
        self._scroll_ref_y: float | None = None   # Posición Y de referencia
        self._scroll_delta: float        = 0.0    # Delta acumulado por frame

        # ── Estado del swipe ──────────────────────────────────────────────────
        # Historial de posición X de la palma (últimos 12 frames)
        self._palm_x_history: deque[float] = deque(maxlen=12)

        # ── Contador para gesto STOP ──────────────────────────────────────────
        self._stop_counter: int = 0

        log.info("GestureDetector inicializado.")

    # ─────────────────────────────────────────────────────────────────────────
    #  MÉTODO PRINCIPAL
    # ─────────────────────────────────────────────────────────────────────────

    def detect(self, hand_data) -> str | None:
        """
        Analiza el HandData del frame actual y retorna el nombre del
        gesto confirmado, o None si no hay gesto activo.

        Args:
            hand_data: objeto HandData de hand_tracker.py

        Returns:
            str con el nombre del gesto, o None
        """
        if hand_data is None:
            self._reset_scroll()
            self._stop_counter = 0
            return None

        # Actualizar historial de posición X para swipes
        px, py = hand_data.palm_position
        self._palm_x_history.append(px)

        # ── 1. Detectar candidato de gesto en este frame ──────────────────────
        candidate = self._classify_frame(hand_data)
        self._history.append(candidate or "NONE")

        # ── 2. Gesto STOP (tiene prioridad máxima) ────────────────────────────
        stop_result = self._check_stop_gesture(candidate, hand_data)
        if stop_result:
            return stop_result

        # ── 3. Swipes (basados en velocidad, no en confirmación de frames) ────
        swipe = self._check_swipe(hand_data)
        if swipe:
            return swipe

        # ── 4. Scroll continuo (se actualiza cada frame) ─────────────────────
        if candidate == "TWO_FINGERS_UP":
            self._update_scroll(hand_data)
        else:
            self._reset_scroll()

        # ── 5. Confirmar el resto de gestos ───────────────────────────────────
        return self._confirm_gesture(candidate)

    # ─────────────────────────────────────────────────────────────────────────
    #  CLASIFICACIÓN POR FRAME
    # ─────────────────────────────────────────────────────────────────────────

    def _classify_frame(self, hd) -> str | None:
        """
        Revisa el HandData de UN frame y devuelve el nombre del gesto
        que más se parece, sin confirmar todavía.
        """
        cfg = self.cfg

        # ── PINCH: punta índice cerca de punta pulgar ─────────────────────────
        if hd.pinch_distance < cfg.PINCH_THRESHOLD:
            return "PINCH"

        # ── FIST: mano muy cerrada ────────────────────────────────────────────
        if hd.openness < cfg.FIST_THRESHOLD:
            return "FIST"

        # ── TWO_FINGERS: índice + medio extendidos, resto doblados ────────────
        #   finger_states = [thumb, index, middle, ring, pinky]
        fs = hd.finger_states
        if fs is not None:
            index_up  = fs[1]
            middle_up = fs[2]
            ring_down = not fs[3]
            pinky_down= not fs[4]
            if index_up and middle_up and ring_down and pinky_down:
                return "TWO_FINGERS_UP"

        # ── OPEN_HAND: mano abierta ───────────────────────────────────────────
        if hd.openness > cfg.OPEN_HAND_THRESHOLD:
            return "OPEN_HAND"

        # ── RIGHT_CLICK: puño rápido suelto ──────────────────────────────────
        #   Se detecta en _confirm_gesture con la secuencia FIST→OPEN_HAND
        #   Aquí solo lo etiquetamos como FIST

        return None

    # ─────────────────────────────────────────────────────────────────────────
    #  CONFIRMACIÓN DE GESTOS
    # ─────────────────────────────────────────────────────────────────────────

    def _confirm_gesture(self, candidate: str | None) -> str | None:
        """
        Comprueba que el gesto candidato lleva al menos
        GESTURE_CONFIRM_FRAMES frames consecutivos.
        También detecta RIGHT_CLICK como secuencia FIST→OPEN_HAND rápida.
        """
        n = self.cfg.GESTURE_CONFIRM_FRAMES

        # Contar cuántos de los últimos N frames tienen el mismo candidato
        recent = list(self._history)[-n:]
        if len(recent) < n:
            return None

        if all(g == candidate for g in recent) and candidate is not None:
            return candidate

        # ── Detectar RIGHT_CLICK: FIST seguido rápidamente de OPEN_HAND ──────
        #   Ventana de búsqueda: 10 frames (~330ms a 30fps)
        window = list(self._history)[-10:]
        if len(window) >= 4:
            has_fist = "FIST" in window[:-2]
            ends_open = window[-1] == "OPEN_HAND" and window[-2] in ("OPEN_HAND", "FIST")
            if has_fist and ends_open:
                # Solo si el puño duró poco (gesto rápido, no drag)
                fist_count = sum(1 for g in window if g == "FIST")
                if 1 <= fist_count <= 5 and not self.is_on_cooldown("RIGHT_CLICK"):
                    return "RIGHT_CLICK"

        return None

    # ─────────────────────────────────────────────────────────────────────────
    #  GESTO STOP (PAUSA)
    # ─────────────────────────────────────────────────────────────────────────

    def _check_stop_gesture(self, candidate: str | None, hd) -> str | None:
        """
        Activa STOP_TOGGLE si la palma abierta se mantiene quieta durante
        STOP_GESTURE_FRAMES frames.

        Condiciones:
          - Gesto candidato = OPEN_HAND
          - Los cinco dedos extendidos
          - Velocidad de la palma < 8 px/frame (mano quieta)
        """
        cfg = self.cfg

        if candidate != "OPEN_HAND":
            self._stop_counter = 0
            return None

        # Todos los dedos extendidos
        fs = hd.finger_states
        all_extended = fs is not None and all(fs)

        # Mano quieta
        vx, vy = hd.palm_velocity
        speed = (vx**2 + vy**2) ** 0.5
        hand_still = speed < 8.0

        if all_extended and hand_still:
            self._stop_counter += 1
        else:
            self._stop_counter = 0

        if self._stop_counter >= cfg.STOP_GESTURE_FRAMES:
            self._stop_counter = 0   # Resetear para siguiente toggle
            log.info("Gesto STOP detectado → toggle pausa")
            return "STOP_TOGGLE"

        return None

    # ─────────────────────────────────────────────────────────────────────────
    #  SWIPES
    # ─────────────────────────────────────────────────────────────────────────

    def _check_swipe(self, hd) -> str | None:
        """
        Detecta un movimiento rápido horizontal de la mano.

        Calcula la diferencia entre la posición X actual y la de
        hace ~8 frames. Si supera SWIPE_VELOCITY_THRESHOLD (en px
        de frame normalizado → convertimos a píxeles reales),
        se dispara el swipe.
        """
        if len(self._palm_x_history) < 8:
            return None

        # Diferencia entre posición actual y de hace 8 frames
        # palm_position está en [0,1], escalamos al ancho del frame (640px)
        x_now  = self._palm_x_history[-1]  * self.cfg.KINECT_COLOR_W
        x_prev = self._palm_x_history[-8]  * self.cfg.KINECT_COLOR_W
        delta_x = x_now - x_prev

        threshold = self.cfg.SWIPE_VELOCITY_THRESHOLD

        if delta_x > threshold and not self.is_on_cooldown("SWIPE"):
            log.debug(f"SWIPE_RIGHT detectado (Δx={delta_x:.1f}px)")
            return "SWIPE_RIGHT"

        if delta_x < -threshold and not self.is_on_cooldown("SWIPE"):
            log.debug(f"SWIPE_LEFT detectado (Δx={delta_x:.1f}px)")
            return "SWIPE_LEFT"

        return None

    # ─────────────────────────────────────────────────────────────────────────
    #  SCROLL
    # ─────────────────────────────────────────────────────────────────────────

    def _update_scroll(self, hd):
        """
        Calcula el delta de scroll basado en el movimiento vertical
        de la palma respecto al punto de referencia.

        Positivo = scroll hacia arriba, Negativo = scroll hacia abajo.
        """
        _, y = hd.palm_position

        if self._scroll_ref_y is None:
            # Primer frame con dos dedos: establecer referencia
            self._scroll_ref_y = y
            self._scroll_delta  = 0.0
            return

        dy = self._scroll_ref_y - y   # Invertir: mano sube → scroll arriba

        if abs(dy) > self.cfg.SCROLL_DEAD_ZONE:
            # Escalar a unidades de scroll (~3 unidades = un "tick de rueda")
            self._scroll_delta = dy * self.cfg.SCROLL_SPEED_FACTOR * 30
            # Actualizar referencia gradualmente para scroll continuo suave
            self._scroll_ref_y = (
                0.95 * self._scroll_ref_y + 0.05 * y
            )
        else:
            self._scroll_delta = 0.0

    def _reset_scroll(self):
        self._scroll_ref_y = None
        self._scroll_delta  = 0.0

    def get_scroll_delta(self) -> float:
        """Retorna el delta de scroll calculado en el último frame."""
        return self._scroll_delta

    # ─────────────────────────────────────────────────────────────────────────
    #  COOLDOWNS
    # ─────────────────────────────────────────────────────────────────────────

    def set_cooldown(self, gesture_name: str, seconds: float):
        """
        Bloquea el gesto durante `seconds` segundos para evitar
        disparos repetidos.

        Ejemplo: set_cooldown("PINCH", 0.4) → no se puede hacer
                 otro clic izquierdo durante 400ms.
        """
        self._cooldowns[gesture_name] = time.monotonic() + seconds

    def is_on_cooldown(self, gesture_name: str) -> bool:
        """Retorna True si el gesto está bloqueado por cooldown."""
        until = self._cooldowns.get(gesture_name, 0.0)
        return time.monotonic() < until
