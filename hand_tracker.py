"""
╔══════════════════════════════════════════════════════════════════╗
║                    SEGUIMIENTO DE MANO                           ║
║                                                                  ║
║  Usa MediaPipe Hands para detectar los 21 landmarks de la mano  ║
║  y calcula métricas adicionales (extensión dedos, posición       ║
║  de palma, etc.) que usan los detectores de gestos.             ║
╚══════════════════════════════════════════════════════════════════╝

Landmarks de MediaPipe (índices):
                   8   12  16  20
                   |   |   |   |
     4             7   11  15  19
     |    3        6   10  14  18
     2    |        5    9  13  17
     |    |        |    |   |   |
     1    |   0────┘    └───┘   |
          └─────────────────────┘
  Pulgar  Índice  Medio  Anular  Meñique
   (0-4)  (5-8) (9-12) (13-16) (17-20)

  0 = WRIST (muñeca)
"""

import logging
import numpy as np
import cv2

log = logging.getLogger("HandTracker")

# Intentar importar MediaPipe
try:
    import mediapipe as mp
    MP_AVAILABLE = True
except ImportError:
    MP_AVAILABLE = False
    log.warning("MediaPipe no instalado. Instala: pip install mediapipe")


# ─── Indices de landmarks de MediaPipe ────────────────────────────────────────
WRIST          = 0
THUMB_CMC      = 1
THUMB_MCP      = 2
THUMB_IP       = 3
THUMB_TIP      = 4

INDEX_MCP      = 5
INDEX_PIP      = 6
INDEX_DIP      = 7
INDEX_TIP      = 8

MIDDLE_MCP     = 9
MIDDLE_PIP     = 10
MIDDLE_DIP     = 11
MIDDLE_TIP     = 12

RING_MCP       = 13
RING_PIP       = 14
RING_DIP       = 15
RING_TIP       = 16

PINKY_MCP      = 17
PINKY_PIP      = 18
PINKY_DIP      = 19
PINKY_TIP      = 20


class HandData:
    """
    Contenedor con toda la información de la mano detectada.
    Se pasa entre módulos para evitar recalcular.
    """
    def __init__(self):
        self.landmarks        = None   # Lista de 21 puntos (x,y,z) normalizados
        self.landmarks_px     = None   # Landmarks en píxeles del frame
        self.palm_position    = None   # (x_norm, y_norm) posición de la palma
        self.finger_states    = None   # [thumb, index, middle, ring, pinky] → True=extendido
        self.openness         = 0.0    # 0.0=puño cerrado, 1.0=mano abierta
        self.pinch_distance   = 1.0    # Distancia normalizada índice–pulgar
        self.palm_velocity    = (0, 0) # Velocidad de la palma en px/frame
        self.hand_label       = ""     # "Left" o "Right"
        self.confidence       = 0.0    # Confianza de la detección


class HandTracker:
    """
    Detecta y rastrea la mano usando MediaPipe Hands.
    Extrae métricas que el detector de gestos necesita.
    """

    def __init__(self, cfg):
        self.cfg   = cfg
        self._mp   = None
        self._prev_palm_px = None  # Para calcular velocidad

        if MP_AVAILABLE:
            self._mp_hands = mp.solutions.hands
            self._mp_draw  = mp.solutions.drawing_utils
            self._hands    = self._mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,           # Solo rastreamos 1 mano para rendimiento
                min_detection_confidence=cfg.MP_DETECTION_CONFIDENCE,
                min_tracking_confidence=cfg.MP_TRACKING_CONFIDENCE,
            )
            log.info(
                f"MediaPipe Hands iniciado. "
                f"Confianza detección: {cfg.MP_DETECTION_CONFIDENCE}, "
                f"tracking: {cfg.MP_TRACKING_CONFIDENCE}"
            )
        else:
            log.error("MediaPipe no disponible. El tracker no funcionará.")

    def process(self, color_frame, depth_frame=None) -> "HandData | None":
        """
        Procesa un frame de color y retorna HandData o None si no se
        detecta la mano de control.

        Args:
            color_frame: np.ndarray BGR (640×480)
            depth_frame: np.ndarray uint16 opcional (para profundidad)

        Returns:
            HandData o None
        """
        if not MP_AVAILABLE or self._hands is None:
            return None

        h, w = color_frame.shape[:2]

        # ── Escalar si está configurado (ahorra CPU) ──────────────────────────
        scale = self.cfg.MEDIAPIPE_SCALE
        if scale < 1.0:
            proc_w = int(w * scale)
            proc_h = int(h * scale)
            proc_frame = cv2.resize(color_frame, (proc_w, proc_h))
        else:
            proc_frame = color_frame
            proc_w, proc_h = w, h

        # ── MediaPipe trabaja con RGB ──────────────────────────────────────────
        rgb = cv2.cvtColor(proc_frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self._hands.process(rgb)
        rgb.flags.writeable = True

        if not results.multi_hand_landmarks:
            self._prev_palm_px = None
            return None

        # ── Buscar la mano de control ──────────────────────────────────────────
        target_hand = self.cfg.CONTROL_HAND  # "Right" o "Left"
        hand_lms    = None
        hand_label  = None
        confidence  = 0.0

        # results.multi_handedness tiene la clasificación Left/Right
        if results.multi_handedness:
            for idx, handedness in enumerate(results.multi_handedness):
                label = handedness.classification[0].label
                score = handedness.classification[0].score
                # MediaPipe desde perspectiva de cámara: invierte izq/der
                # si la imagen NO está espejada. Nosotros ya espejamos en
                # kinect_capture, así que "Right" en MediaPipe = tu mano derecha.
                if label == target_hand:
                    hand_lms   = results.multi_hand_landmarks[idx]
                    hand_label = label
                    confidence = score
                    break

        # Si no se encontró la mano específica, tomar la primera disponible
        if hand_lms is None and results.multi_hand_landmarks:
            hand_lms   = results.multi_hand_landmarks[0]
            hand_label = "Unknown"
            if results.multi_handedness:
                confidence = results.multi_handedness[0].classification[0].score

        if hand_lms is None:
            return None

        # ── Extraer landmarks normalizados y en píxeles ───────────────────────
        lms_norm = []   # coordenadas [0.0–1.0]
        lms_px   = []   # coordenadas en píxeles del frame ORIGINAL (no escalado)

        for lm in hand_lms.landmark:
            lms_norm.append((lm.x, lm.y, lm.z))
            # Escalar de vuelta al frame original
            px_x = int(lm.x * w)
            px_y = int(lm.y * h)
            lms_px.append((px_x, px_y))

        # ── Construir HandData ────────────────────────────────────────────────
        data = HandData()
        data.landmarks    = lms_norm
        data.landmarks_px = lms_px
        data.hand_label   = hand_label
        data.confidence   = confidence

        # Posición de la palma: promedio de muñeca + MCPs
        palm_pts = [WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]
        palm_x = np.mean([lms_norm[i][0] for i in palm_pts])
        palm_y = np.mean([lms_norm[i][1] for i in palm_pts])
        data.palm_position = (float(palm_x), float(palm_y))

        # Velocidad de la palma (px/frame)
        palm_px = (int(palm_x * w), int(palm_y * h))
        if self._prev_palm_px is not None:
            vx = palm_px[0] - self._prev_palm_px[0]
            vy = palm_px[1] - self._prev_palm_px[1]
            data.palm_velocity = (vx, vy)
        else:
            data.palm_velocity = (0, 0)
        self._prev_palm_px = palm_px

        # ── Estado de cada dedo (extendido/doblado) ───────────────────────────
        data.finger_states = self._compute_finger_states(lms_norm)

        # ── Apertura de la mano ───────────────────────────────────────────────
        data.openness = self._compute_openness(lms_norm)

        # ── Distancia de pellizco (índice–pulgar) ─────────────────────────────
        data.pinch_distance = self._compute_pinch_distance(lms_norm)

        return data

    # ─────────────────────────────────────────────────────────────────────────
    #  MÉTRICAS AUXILIARES
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_finger_states(self, lms):
        """
        Retorna [thumb, index, middle, ring, pinky] donde True = extendido.
        Método: compara si la punta está más lejos de la muñeca que el MCP.
        """
        wrist = np.array(lms[WRIST][:2])

        def dist(a, b):
            return np.linalg.norm(np.array(a[:2]) - np.array(b[:2]))

        states = []

        # Pulgar: usa eje X en lugar de distancia (anatomía diferente)
        thumb_extended = (
            dist(lms[THUMB_TIP], lms[THUMB_MCP])
            > dist(lms[THUMB_IP], lms[THUMB_MCP]) * 0.8
        )
        states.append(thumb_extended)

        # Resto de dedos: punta más lejos de muñeca que MCP
        finger_tips = [INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
        finger_mcps = [INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]

        for tip_idx, mcp_idx in zip(finger_tips, finger_mcps):
            tip_dist = dist(lms[tip_idx], wrist)
            mcp_dist = dist(lms[mcp_idx], wrist)
            states.append(tip_dist > mcp_dist * 0.85)

        return states  # [thumb, index, middle, ring, pinky]

    def _compute_openness(self, lms):
        """
        Calcula qué tan abierta está la mano [0.0=puño, 1.0=abierta].
        Promedia la distancia normalizada de cada punta al centro de la palma.
        """
        palm_center = np.array([
            np.mean([lms[i][0] for i in [WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]]),
            np.mean([lms[i][1] for i in [WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]]),
        ])

        # Distancia de referencia: muñeca a dedo corazón MCP
        ref_dist = np.linalg.norm(
            np.array(lms[MIDDLE_MCP][:2]) - np.array(lms[WRIST][:2])
        )
        if ref_dist < 1e-6:
            return 0.0

        tips = [INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
        dists = [
            np.linalg.norm(np.array(lms[t][:2]) - palm_center) / ref_dist
            for t in tips
        ]
        # Normalizar a ~[0,1]
        openness = np.clip(np.mean(dists) / 1.8, 0.0, 1.0)
        return float(openness)

    def _compute_pinch_distance(self, lms):
        """
        Distancia euclídea normalizada entre punta del índice y del pulgar.
        Normalizada por la longitud de la mano (muñeca → dedo corazón MCP).
        """
        tip_index = np.array(lms[INDEX_TIP][:2])
        tip_thumb = np.array(lms[THUMB_TIP][:2])
        dist_pinch = np.linalg.norm(tip_index - tip_thumb)

        # Normalizar
        ref = np.linalg.norm(
            np.array(lms[MIDDLE_MCP][:2]) - np.array(lms[WRIST][:2])
        )
        if ref < 1e-6:
            return 1.0

        return float(np.clip(dist_pinch / ref, 0.0, 1.5))
