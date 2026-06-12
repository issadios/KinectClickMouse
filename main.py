"""
╔══════════════════════════════════════════════════════════════════╗
║           KINECT MOUSE - Controlador de PC con Kinect v1         ║
║                     Xbox 360 (Windows)                           ║
╚══════════════════════════════════════════════════════════════════╝

Punto de entrada principal. Inicializa el Kinect, el detector de
gestos y el controlador del mouse. Orquesta el bucle principal.

Autor: IssaTech 3D
"""

import sys
import threading
import time
import logging

import cv2
import pyautogui

from core.kinect_capture import KinectCapture
from core.hand_tracker import HandTracker
from core.mouse_controller import MouseController
from gestures.gesture_detector import GestureDetector
from utils.config import Config
from utils.overlay import OverlayWindow

# ─── Configuración de logging ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("kinect_mouse.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("KinectMouse")

# PyAutoGUI: desactiva el failsafe de esquina para no interrumpir flujo
# (puedes reactivarlo en config.py si lo prefieres)
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0  # Sin pausa entre comandos para máxima fluidez


def main():
    log.info("═══ Iniciando KinectMouse ═══")
    cfg = Config()

    # ── 1. Inicializar captura del Kinect ─────────────────────────────────────
    log.info("Abriendo conexión con Kinect v1...")
    kinect = KinectCapture(cfg)
    if not kinect.open():
        log.error("No se pudo abrir el Kinect. Verifica drivers y conexión USB.")
        sys.exit(1)
    log.info("Kinect conectado correctamente.")

    # ── 2. Inicializar subsistemas ────────────────────────────────────────────
    hand_tracker   = HandTracker(cfg)
    mouse_ctrl     = MouseController(cfg)
    gesture_det    = GestureDetector(cfg)
    overlay        = OverlayWindow(cfg)

    # Estado global compartido entre hilos
    state = {
        "running":     True,
        "paused":      False,   # Modo pausa activado con gesto "STOP"
        "drag_active": False,
    }

    log.info("Todo inicializado. Bucle principal arrancando.")
    log.info("Presiona [Q] en la ventana de depuración para salir.")
    log.info("Levanta la palma abierta para activar/desactivar el modo PAUSA.")

    # ── 3. Bucle principal ────────────────────────────────────────────────────
    try:
        while state["running"]:
            # 3a. Obtener frame de color + profundidad
            color_frame, depth_frame = kinect.get_frames()
            if color_frame is None:
                time.sleep(0.005)
                continue

            # 3b. Detectar mano y landmarks
            hand_data = hand_tracker.process(color_frame, depth_frame)

            # 3c. Dibujar overlay de depuración
            debug_frame = overlay.draw(color_frame.copy(), hand_data, state)

            # 3d. Si no hay mano detectada, no hacer nada
            if hand_data is None:
                _show_debug(debug_frame, cfg)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    state["running"] = False
                continue

            # 3e. Detectar gestos
            gesture = gesture_det.detect(hand_data)

            # Notificar al overlay para que muestre el nombre del gesto
            overlay.update_gesture(gesture)

            # ── Gesto STOP: activa/desactiva modo pausa ───────────────────────
            if gesture == "STOP_TOGGLE":
                state["paused"] = not state["paused"]
                log.info(f"Modo pausa: {'ON' if state['paused'] else 'OFF'}")
                time.sleep(0.6)  # Debounce para evitar múltiples toggles
                continue

            if state["paused"]:
                # Redibujar con estado actualizado para mostrar banner de pausa
                debug_frame = overlay.draw(color_frame.copy(), hand_data, state)
                _show_debug(debug_frame, cfg)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    state["running"] = False
                continue

            # ── Mover cursor ──────────────────────────────────────────────────
            mouse_ctrl.move(hand_data.palm_position)

            # ── Ejecutar acción según gesto ───────────────────────────────────
            _handle_gesture(gesture, mouse_ctrl, gesture_det, state, log)

            # ── Redibujar con gesto actualizado y mostrar ─────────────────────
            debug_frame = overlay.draw(color_frame.copy(), hand_data, state)
            _show_debug(debug_frame, cfg)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                state["running"] = False

    except KeyboardInterrupt:
        log.info("Interrumpido por teclado.")
    finally:
        log.info("Cerrando recursos...")
        kinect.close()
        cv2.destroyAllWindows()
        log.info("KinectMouse cerrado correctamente.")


def _handle_gesture(gesture, mouse_ctrl, gesture_det, state, log):
    """Despacha la acción de ratón/sistema según el gesto detectado."""

    if gesture == "PINCH":
        # ── Clic izquierdo (pellizco índice + pulgar) ─────────────────────────
        if not gesture_det.is_on_cooldown("PINCH"):
            log.debug("Gesto: PINCH → left click")
            pyautogui.click()
            gesture_det.set_cooldown("PINCH", 0.4)

    elif gesture == "FIST":
        # ── Drag & Drop: cerrar puño = agarrar, abrir = soltar ───────────────
        if not state["drag_active"]:
            log.debug("Gesto: FIST → mouseDown (inicio drag)")
            pyautogui.mouseDown()
            state["drag_active"] = True
        # El mouse se mueve continuamente mientras el puño está cerrado

    elif gesture == "OPEN_HAND" and state["drag_active"]:
        # ── Soltar drag ───────────────────────────────────────────────────────
        log.debug("Gesto: OPEN_HAND tras drag → mouseUp")
        pyautogui.mouseUp()
        state["drag_active"] = False

    elif gesture == "TWO_FINGERS_UP":
        # ── Scroll: dos dedos extendidos + movimiento vertical ────────────────
        # El delta de scroll se calcula en gesture_detector
        scroll_delta = gesture_det.get_scroll_delta()
        if abs(scroll_delta) > 0:
            pyautogui.scroll(int(scroll_delta * 3))

    elif gesture == "SWIPE_RIGHT":
        # ── Swipe derecha: Alt+Tab (siguiente ventana) ────────────────────────
        if not gesture_det.is_on_cooldown("SWIPE"):
            log.debug("Gesto: SWIPE_RIGHT → Alt+Tab")
            pyautogui.hotkey("alt", "tab")
            gesture_det.set_cooldown("SWIPE", 1.0)

    elif gesture == "SWIPE_LEFT":
        # ── Swipe izquierda: Alt+Shift+Tab (ventana anterior) ────────────────
        if not gesture_det.is_on_cooldown("SWIPE"):
            log.debug("Gesto: SWIPE_LEFT → Alt+Shift+Tab")
            pyautogui.hotkey("alt", "shift", "tab")
            gesture_det.set_cooldown("SWIPE", 1.0)

    elif gesture == "RIGHT_CLICK":
        # ── Clic derecho: puño cerrado rápido y suelto ────────────────────────
        if not gesture_det.is_on_cooldown("RIGHT_CLICK"):
            log.debug("Gesto: RIGHT_CLICK → right click")
            pyautogui.rightClick()
            gesture_det.set_cooldown("RIGHT_CLICK", 0.5)


def _show_debug(frame, cfg):
    """Muestra la ventana de depuración redimensionada si está habilitada."""
    if cfg.SHOW_DEBUG_WINDOW:
        display = cv2.resize(frame, (cfg.DEBUG_WINDOW_WIDTH, cfg.DEBUG_WINDOW_HEIGHT))
        cv2.imshow("KinectMouse - Debug (Q para salir)", display)


if __name__ == "__main__":
    main()
