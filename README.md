# ╔══════════════════════════════════════════════════════════════════╗
# ║        GUÍA DE INSTALACIÓN COMPLETA - KinectMouse               ║
# ║        Kinect v1 (Xbox 360) en Windows 10/11                    ║
# ╚══════════════════════════════════════════════════════════════════╝

## PASO 1 — Instalar Python (si no lo tienes)
  Descarga Python 3.10 o 3.11 (64-bit) desde https://python.org
   Marca "Add Python to PATH" durante la instalación
   Versión recomendada: 3.11 (mediapipe es más estable aquí)
---

## PASO 2 — Instalar dependencias Python
  Abre una terminal (CMD o PowerShell) en la carpeta del proyecto:

    pip install -r requirements.txt

---

## PASO 3 — Drivers del Kinect v1 en Windows

### Opción A: Kinect SDK v1.8 (más fácil, solo color y esqueleto)
  1. Descarga desde: https://www.microsoft.com/en-us/download/details.aspx?id=40278
  2. Instala KinectSDK-v1.8-Setup.exe
  3. Reinicia el PC
  4. Conecta el Kinect → Windows lo reconoce automáticamente
  ⚠️ Con este método usa CAPTURE_BACKEND = "opencv" en config.py
     No necesitas freenect.

### Opción B: OpenKinect / libfreenect (recomendado, con profundidad)
  1. Descarga el instalador de OpenKinect para Windows:
     https://github.com/OpenKinect/libfreenect/releases
     → Busca el archivo: libfreenect-win32.zip o similar

  2. Extrae y ejecuta el instalador. Anota la ruta de instalación
     (normalmente C:\Program Files\OpenKinect\)

  3. Agrega al PATH del sistema:
     C:\Program Files\OpenKinect\bin\

  4. Instala los bindings de Python para freenect:
     Descarga el wheel precompilado desde:
     https://github.com/OpenKinect/libfreenect/tree/master/wrappers/python

     O compila desde fuente (requiere Visual Studio Build Tools):
       git clone https://github.com/OpenKinect/libfreenect
       cd libfreenect
       mkdir build && cd build
       cmake .. -DBUILD_PYTHON3=ON
       cmake --build . --config Release

  5. Instala el .whl generado:
     pip install freenect-*.whl

### Opción C: Zadig (driver USB genérico, necesario para freenect)
  Si freenect no detecta el Kinect, reemplaza el driver USB:
  1. Descarga Zadig desde https://zadig.akeo.ie/
  2. Options → List All Devices
  3. Selecciona "Xbox NUI Motor" → instala WinUSB
  4. Selecciona "Xbox NUI Camera" → instala WinUSB
  5. Selecciona "Xbox NUI Audio" → instala WinUSB
   Esto reemplaza el driver de Microsoft. Para revertir,
     usa el Administrador de dispositivos → Actualizar driver.

---

## PASO 4 — Verificar instalación

  Abre Python y prueba:

    python -c "import cv2; print('OpenCV:', cv2.__version__)"
    python -c "import mediapipe; print('MediaPipe OK')"
    python -c "import pyautogui; print('PyAutoGUI OK')"

  Para verificar freenect:
    python -c "import freenect; print('freenect OK')"

  Para verificar que el Kinect se detecta:
    python -c "
    import freenect
    ctx = freenect.init()
    n = freenect.num_devices(ctx)
    print(f'Kinects detectados: {n}')
    freenect.shutdown(ctx)
    "

---

## PASO 5 — Ejecutar el proyecto

    python main.py

  Si freenect no funciona, edita utils/config.py y cambia:
    CAPTURE_BACKEND = "opencv"

---

## SOLUCIÓN DE PROBLEMAS FRECUENTES

   "No module named 'freenect'"
  → Instala freenect manualmente (Opción B arriba)
  → O usa CAPTURE_BACKEND = "opencv" en config.py

   "Cannot open camera index 0"
  → Prueba KINECT_DEVICE_INDEX = 1 en config.py
  → Verifica en Administrador de dispositivos que el Kinect aparece

   El cursor tiembla mucho
  → Aumenta SMOOTHING_ALPHA a 0.15 en config.py (más suavizado)
  → Aumenta DEAD_ZONE_PX a 8 en config.py

   Los gestos se detectan solos / falsos positivos
  → Aumenta GESTURE_CONFIRM_FRAMES a 5 en config.py
  → Ajusta los umbrales: FIST_THRESHOLD, OPEN_HAND_THRESHOLD

   MediaPipe muy lento
  → Baja MEDIAPIPE_SCALE a 0.5 en config.py
  → Activa FRAME_SKIP = 1 en config.py (procesa 1 de cada 2 frames)

   "DLL load failed" con freenect en Windows
  → Asegúrate de que C:\Program Files\OpenKinect\bin está en el PATH
  → Reinicia CMD/PowerShell después de modificar el PATH

---

## ESTRUCTURA DEL PROYECTO

  kinect_mouse/
  ├── main.py                   ← Punto de entrada
  ├── requirements.txt
  ├── INSTALL_KINECT.md         ← Esta guía
  ├── core/
  │   ├── kinect_capture.py     ← Captura de color + profundidad
  │   ├── hand_tracker.py       ← Detección de mano con MediaPipe
  │   └── mouse_controller.py   ← Mover cursor con suavizado
  ├── gestures/
  │   └── gesture_detector.py   ← Lógica de todos los gestos
  └── utils/
      ├── config.py             ← ⚙️  PANEL DE CALIBRACIÓN
      └── overlay.py            ← Ventana de depuración visual
