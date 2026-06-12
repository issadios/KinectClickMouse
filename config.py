"""
╔══════════════════════════════════════════════════════════════════╗
║                    CONFIGURACIÓN Y CALIBRACIÓN                   ║
║                                                                  ║
║  ESTE ES TU PANEL DE CALIBRACIÓN PRINCIPAL.                      ║
║  Ajusta estos valores hasta que el comportamiento sea fluido.    ║
╚══════════════════════════════════════════════════════════════════╝
"""

import pyautogui


class Config:

    # ═══════════════════════════════════════════════════════════════
    #  RESOLUCIÓN DE PANTALLA
    #  Se detecta automáticamente, pero puedes forzarla aquí.
    # ═══════════════════════════════════════════════════════════════
    SCREEN_W, SCREEN_H = pyautogui.size()

    # ═══════════════════════════════════════════════════════════════
    #  RESOLUCIÓN DEL KINECT V1
    #  Color: 640×480 @ 30fps  |  Profundidad: 320×240
    # ═══════════════════════════════════════════════════════════════
    KINECT_COLOR_W  = 640
    KINECT_COLOR_H  = 480
    KINECT_DEPTH_W  = 320
    KINECT_DEPTH_H  = 240
    KINECT_FPS      = 30

    # ═══════════════════════════════════════════════════════════════
    #  ZONA ACTIVA DE CAPTURA (BOUNDING BOX)
    #
    #  Define qué porción del frame del Kinect se mapea a la pantalla.
    #  Mueve la mano dentro de esta zona para controlar el cursor.
    #
    #  Valores normalizados [0.0 – 1.0] sobre el frame de color.
    #  Ejemplo: X_MIN=0.15 significa que empieza al 15% del ancho.
    #
    #  ┌─────────────────────────────────┐
    #  │  Frame 640×480 del Kinect       │
    #  │   ┌─────────────────────┐       │
    #  │   │  ZONA ACTIVA        │       │
    #  │   │  (mueve aquí        │       │
    #  │   │   la mano)          │       │
    #  │   └─────────────────────┘       │
    #  └─────────────────────────────────┘
    # ═══════════════════════════════════════════════════════════════
    ACTIVE_ZONE_X_MIN = 0.15   # Borde izquierdo de la zona activa
    ACTIVE_ZONE_X_MAX = 0.85   # Borde derecho
    ACTIVE_ZONE_Y_MIN = 0.10   # Borde superior
    ACTIVE_ZONE_Y_MAX = 0.85   # Borde inferior

    # ═══════════════════════════════════════════════════════════════
    #  SUAVIZADO DEL CURSOR (SMOOTHING)
    #
    #  Usa un filtro exponencial: pos = alpha*nueva + (1-alpha)*anterior
    #
    #  ALPHA = 1.0  → Sin suavizado (el cursor va exactamente donde
    #                  pones la mano, pero puede temblar mucho)
    #  ALPHA = 0.1  → Muy suavizado (lento pero estable)
    #  ALPHA = 0.25 → ✓ Punto de partida recomendado
    #  ALPHA = 0.40 → Más responsivo, algo de temblor
    # ═══════════════════════════════════════════════════════════════
    SMOOTHING_ALPHA = 0.25

    # Umbral mínimo de movimiento (píxeles) para mover el cursor.
    # Evita micro-movimientos cuando la mano está "quieta".
    # Sube este valor si el cursor se mueve solo.
    DEAD_ZONE_PX = 4

    # ═══════════════════════════════════════════════════════════════
    #  DETECCIÓN DE MANO (MediaPipe)
    # ═══════════════════════════════════════════════════════════════
    # Confianza mínima para considerar que se detectó una mano [0.0-1.0]
    # Bájala si pierdes el tracking frecuentemente (más falsos positivos)
    # Súbela si detecta cosas que no son manos
    MP_DETECTION_CONFIDENCE  = 0.7
    MP_TRACKING_CONFIDENCE   = 0.6

    # Qué mano controla el cursor: "Right" o "Left"
    # IMPORTANTE: MediaPipe detecta desde la perspectiva de la cámara,
    # así que si te ves en la pantalla como espejo, usa "Right" para
    # controlar con tu mano derecha.
    CONTROL_HAND = "Right"

    # ═══════════════════════════════════════════════════════════════
    #  UMBRALES DE GESTOS
    # ═══════════════════════════════════════════════════════════════

    # ── Pellizco (PINCH = clic izquierdo) ────────────────────────
    # Distancia normalizada entre punta de índice y pulgar.
    # Más pequeño = necesitas juntar más los dedos para hacer clic.
    PINCH_THRESHOLD = 0.06       # [0.02 – 0.12] Ajusta según tu mano

    # ── Puño cerrado (FIST = drag) ───────────────────────────────
    # Qué tan cerrado debe estar el puño [0.0 = totalmente cerrado,
    # 1.0 = mano abierta]. Mide distancia promedio puntas→palma.
    FIST_THRESHOLD = 0.35        # Baja si tu puño no se detecta

    # ── Mano abierta (OPEN_HAND = soltar drag / pausa) ───────────
    OPEN_HAND_THRESHOLD = 0.65   # Sube si se activa accidentalmente

    # ── Dos dedos (TWO_FINGERS = scroll) ─────────────────────────
    # Qué tan extendidos deben estar índice y medio, y el resto doblados
    TWO_FINGERS_EXTEND_THRESH = 0.6   # Extensión mínima [0.0-1.0]
    TWO_FINGERS_CURL_THRESH   = 0.4   # Máx extensión dedos doblados

    # ── Swipe (cambio de ventana) ─────────────────────────────────
    # Velocidad mínima horizontal (px/frame) para disparar el swipe
    SWIPE_VELOCITY_THRESHOLD = 35    # Sube si se activa solo

    # Cuántos frames consecutivos debe mantenerse el gesto para
    # que se confirme (evita falsos positivos)
    GESTURE_CONFIRM_FRAMES = 3

    # ── Pausa (gesto STOP) ────────────────────────────────────────
    # Cuántos frames con palma abierta y quieta para activar pausa
    STOP_GESTURE_FRAMES = 8

    # ═══════════════════════════════════════════════════════════════
    #  SCROLL
    # ═══════════════════════════════════════════════════════════════
    # Factor de velocidad del scroll (1.0 = normal, 2.0 = el doble)
    SCROLL_SPEED_FACTOR = 1.5

    # Movimiento mínimo vertical (px normalizados) para empezar scroll
    SCROLL_DEAD_ZONE = 0.015

    # ═══════════════════════════════════════════════════════════════
    #  BACKEND DE CAPTURA
    #
    #  "freenect"  → libfreenect (más estable con Kinect v1)
    #  "opencv"    → OpenCV VideoCapture (más simple, menos features)
    #  "pykinect2" → PyKinect2 (solo para Kinect v2, NO usar aquí)
    # ═══════════════════════════════════════════════════════════════
    CAPTURE_BACKEND = "freenect"   # Cambia a "opencv" si freenect da problemas

    # Índice de dispositivo si tienes múltiples cámaras (normalmente 0)
    KINECT_DEVICE_INDEX = 0

    # ═══════════════════════════════════════════════════════════════
    #  VENTANA DE DEPURACIÓN
    # ═══════════════════════════════════════════════════════════════
    SHOW_DEBUG_WINDOW  = True   # False para producción (ahorra CPU)
    DEBUG_WINDOW_WIDTH  = 640
    DEBUG_WINDOW_HEIGHT = 480

    # Mostrar landmarks de MediaPipe sobre la mano
    SHOW_HAND_LANDMARKS = True

    # Mostrar zona activa como rectángulo en la ventana de debug
    SHOW_ACTIVE_ZONE = True

    # Mostrar nombre del gesto detectado en pantalla
    SHOW_GESTURE_NAME = True

    # ═══════════════════════════════════════════════════════════════
    #  RENDIMIENTO
    # ═══════════════════════════════════════════════════════════════
    # Reducir resolución antes de pasar a MediaPipe (ahorra CPU)
    # 1.0 = resolución completa, 0.5 = mitad
    MEDIAPIPE_SCALE = 0.75

    # Saltar frames si la CPU no da abasto (0 = procesar todos)
    FRAME_SKIP = 0
