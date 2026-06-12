"""
╔══════════════════════════════════════════════════════════════════╗
║                    CAPTURA DEL KINECT V1                         ║
║                                                                  ║
║  Soporta dos backends:                                           ║
║    1. freenect  → libfreenect + freenect2 Python bindings        ║
║       (recomendado para Kinect Xbox 360 / v1)                    ║
║    2. opencv    → VideoCapture estándar (fallback simple,        ║
║       sin profundidad)                                           ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import numpy as np
import cv2

log = logging.getLogger("KinectCapture")


class KinectCapture:
    """
    Abstrae la captura de color + profundidad del Kinect v1.
    Elige el backend según cfg.CAPTURE_BACKEND.
    """

    def __init__(self, cfg):
        self.cfg     = cfg
        self.backend = cfg.CAPTURE_BACKEND
        self._ctx    = None   # Contexto freenect
        self._dev    = None   # Dispositivo freenect
        self._cap    = None   # VideoCapture de OpenCV (backend opencv)

        # Buffers de los últimos frames recibidos
        self._last_color = None
        self._last_depth = None

        # Callbacks de freenect se ejecutan en hilo separado
        # usamos un lock para acceso seguro
        import threading
        self._lock = threading.Lock()

    # ─────────────────────────────────────────────────────────────────────────
    #  ABRIR DISPOSITIVO
    # ─────────────────────────────────────────────────────────────────────────
    def open(self) -> bool:
        if self.backend == "freenect":
            return self._open_freenect()
        elif self.backend == "opencv":
            return self._open_opencv()
        else:
            log.error(f"Backend desconocido: {self.backend}")
            return False

    def _open_freenect(self) -> bool:
        """
        Abre el Kinect usando la librería freenect (libfreenect).
        Requiere: pip install freenect  (y los drivers Kinect instalados)

        Si los bindings de Python fallan, el error más común es que
        freenect.dll no está en el PATH. Instala OpenKinect y agrega
        la carpeta bin/ al PATH del sistema.
        """
        try:
            import freenect
            self._fn = freenect

            # Abrir contexto
            self._ctx = freenect.init()
            if self._ctx is None:
                log.error("freenect.init() devolvió None. ¿Kinect conectado?")
                return False

            self._dev = freenect.open_device(
                self._ctx, self.cfg.KINECT_DEVICE_INDEX
            )
            if self._dev is None:
                log.error("No se pudo abrir el dispositivo Kinect.")
                return False

            # Configurar modo de video (RGB 640×480)
            freenect.set_video_mode(
                self._dev,
                freenect.RESOLUTION_MEDIUM,  # 640×480
                freenect.VIDEO_RGB,
            )

            # Configurar modo de profundidad (11-bit, 320×240 después del resize)
            freenect.set_depth_mode(
                self._dev,
                freenect.RESOLUTION_MEDIUM,
                freenect.DEPTH_11BIT,
            )

            # Callbacks
            freenect.set_video_callback(self._dev, self._video_callback)
            freenect.set_depth_callback(self._dev, self._depth_callback)

            # Iniciar streams
            freenect.start_video(self._dev)
            freenect.start_depth(self._dev)

            # Hilo de eventos de freenect
            import threading
            self._fn_thread = threading.Thread(
                target=self._freenect_event_loop, daemon=True
            )
            self._fn_thread.start()

            log.info("Kinect abierto con backend freenect.")
            return True

        except ImportError:
            log.warning(
                "freenect no instalado. Prueba: pip install freenect\n"
                "  o instala los bindings de OpenKinect para Windows.\n"
                "  Cayendo en backend opencv..."
            )
            self.backend = "opencv"
            return self._open_opencv()
        except Exception as e:
            log.error(f"Error al abrir Kinect con freenect: {e}")
            return False

    def _freenect_event_loop(self):
        """Procesa eventos de freenect en bucle (hilo daemon)."""
        import freenect
        try:
            while True:
                freenect.process_events(self._ctx)
        except Exception as e:
            log.warning(f"Evento freenect detenido: {e}")

    def _video_callback(self, dev, data, timestamp):
        """Llamado por freenect cuando hay un frame de color nuevo."""
        # data llega como uint8 RGB, lo convertimos a BGR para OpenCV
        frame_bgr = cv2.cvtColor(data, cv2.COLOR_RGB2BGR)
        with self._lock:
            self._last_color = frame_bgr

    def _depth_callback(self, dev, data, timestamp):
        """Llamado por freenect cuando hay un frame de profundidad nuevo."""
        # data es uint16 con valores de 0 a 2047 (11 bits)
        with self._lock:
            self._last_depth = data.astype(np.uint16)

    def _open_opencv(self) -> bool:
        """
        Fallback: abre el Kinect como una cámara USB estándar con OpenCV.
        Solo captura color (sin datos de profundidad).
        La detección de gestos funcionará igual con MediaPipe.
        """
        try:
            # DirectShow backend en Windows para evitar demoras de init
            self._cap = cv2.VideoCapture(
                self.cfg.KINECT_DEVICE_INDEX, cv2.CAP_DSHOW
            )
            if not self._cap.isOpened():
                # Intentar sin especificar backend
                self._cap = cv2.VideoCapture(self.cfg.KINECT_DEVICE_INDEX)
            if not self._cap.isOpened():
                log.error("OpenCV no puede abrir la cámara Kinect.")
                return False

            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.cfg.KINECT_COLOR_W)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.KINECT_COLOR_H)
            self._cap.set(cv2.CAP_PROP_FPS, self.cfg.KINECT_FPS)
            log.info(
                f"Kinect abierto con OpenCV (sin profundidad). "
                f"Res: {int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
                f"{int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}"
            )
            return True
        except Exception as e:
            log.error(f"Error al abrir cámara con OpenCV: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    #  OBTENER FRAMES
    # ─────────────────────────────────────────────────────────────────────────
    def get_frames(self):
        """
        Retorna (color_frame, depth_frame).
        color_frame: np.ndarray BGR uint8 640×480
        depth_frame: np.ndarray uint16 640×480 (o None si no hay profundidad)
        """
        if self.backend == "freenect":
            with self._lock:
                color = (
                    self._last_color.copy()
                    if self._last_color is not None
                    else None
                )
                depth = (
                    self._last_depth.copy()
                    if self._last_depth is not None
                    else None
                )

            # Redimensionar depth a tamaño color si es necesario
            if depth is not None and color is not None:
                if depth.shape[:2] != color.shape[:2]:
                    depth = cv2.resize(
                        depth,
                        (color.shape[1], color.shape[0]),
                        interpolation=cv2.INTER_NEAREST,
                    )
            return color, depth

        elif self.backend == "opencv":
            ret, frame = self._cap.read()
            if not ret:
                return None, None
            # Espejear horizontalmente para que sea intuitivo
            frame = cv2.flip(frame, 1)
            return frame, None

    # ─────────────────────────────────────────────────────────────────────────
    #  CERRAR
    # ─────────────────────────────────────────────────────────────────────────
    def close(self):
        try:
            if self.backend == "freenect" and self._dev is not None:
                import freenect
                freenect.stop_video(self._dev)
                freenect.stop_depth(self._dev)
                freenect.close_device(self._dev)
                freenect.shutdown(self._ctx)
                log.info("Kinect (freenect) cerrado.")
            elif self._cap is not None:
                self._cap.release()
                log.info("Kinect (OpenCV) cerrado.")
        except Exception as e:
            log.warning(f"Error al cerrar Kinect: {e}")
