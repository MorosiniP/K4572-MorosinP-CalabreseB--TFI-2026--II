# K4572-MorosinP-CalabreseB--TFI-2026--II
Trabajo final de tecnologia de automatización 
# Simulador de Control: Sistema de Asistencia para Mantenimiento de Carril (Lane Assist — VW Golf VII)

**Universidad Tecnológica Nacional — Facultad Regional Buenos Aires (UTN-FRBA)**  
**Materia:** Tecnologías de Automatización (Bloque Temático: Teoría de Control)  
**Curso:** K-4572  
**Docente:** Ing. Omar Oscar Civale  
**Integrantes:**
* Calabrese, Bruno
* Morosini, Pablo

---

## 1. Links de Acceso (Código y Tablero Interactivo)

* **Repositorio de Código Fuente (GitHub):** `[https://github.com/MorosiniP/K4572-MorosinP-CalabreseB--TFI-2026--II.git]`
* **Tablero de Control Interactivo en Vivo (Web App):** `[https://TU_APP.streamlit.app]`
* **Archivo principal de la simulación:** `app.py`

---

## 2. Instrucciones de Acceso y Ejecución

El simulador modela en tiempo discreto ($dt = 10\text{ ms}$) el lazo cerrado del sistema *Lane Assist* del Volkswagen Golf VII, permitiendo modificar en tiempo real la velocidad del vehículo, las perturbaciones externas (ráfagas o viento/peralte constante), los parámetros del controlador PID por umbrales ($K_p, K_i, K_d$), la banda muerta y los retardos físicos del sistema.

### Opción A: Acceso directo vía Web (Recomendado para evaluación)
1. Ingresar al enlace del **Tablero de Control Interactivo** indicado en la sección anterior desde cualquier navegador web.
2. Utilizar el panel lateral izquierdo (**Parámetros de Operación**) para ajustar las variables del sistema y observar la actualización instantánea de las métricas y gráficas de respuesta temporal ($\theta_o(t)$, $e(t)$ y u(t)).

### Opción B: Ejecución en entorno local
1. Clonar el repositorio o descargar los archivos fuente:
   ```bash
   git clone [https://github.com/MorosiniP/K4572-MorosinP-CalabreseB--TFI-2026--II.git](https://github.com/TU_USUARIO/tfi-lane-assist-golf7.git)
