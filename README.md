# K4572-MorosinP-CalabreseB--TFI-2026--II
## Simulador de Control: Sistema de Asistencia para Mantenimiento de Carril (Lane Assist — VW Golf VII)

**Universidad Tecnológica Nacional — Facultad Regional Buenos Aires (UTN-FRBA)**  
**Materia:** Tecnologías de Automatización (Bloque Temático: Teoría de Control)  
**Curso:** K-4572  
**Docente:** Ing. Omar Oscar Civale  
**Integrantes:**
* Calabrese, Bruno
* Morosini, Pablo

---

## 1. Links de Acceso (Código y Tablero Interactivo)

* **Repositorio de Código Fuente (GitHub):** https://github.com/MorosiniP/K4572-MorosinP-CalabreseB--TFI-2026--II.git
* **Tablero de Control Interactivo en Vivo (Web App):** `[https://k4572-pablo-bruno-tfi-2026.streamlit.app/]`
* **Archivo principal de la simulación:** `app.py`

---

## 2. Descripción del Simulador

El simulador modela en tiempo discreto ($dt = 10\text{ ms}$) el lazo cerrado del sistema *Lane Assist* del Volkswagen Golf VII (referencia técnica SSP 516), permitiendo analizar la respuesta temporal de la posición lateral $\theta_o(t)$, el error $e(t)$ y el torque corrector del actuador EPS $u(t)$.

### Características principales
* **Parámetros de operación:** velocidad longitudinal ajustable (con aviso de estado pasivo por debajo de $65\text{ km/h}$ según SSP 516).
* **Perturbaciones externas configurables** (intensidad exacta por teclado/deslizador e instantes `t inicio` / `t fin`):
  * **Viento lateral (Crosswinds):** ráfaga temporal tipo pulso.
  * **Peralte o pendiente transversal de la calzada:** inclinación lateral sostenida (escalón).
  * **Irregularidades del asfalto:** perfil de baches y ondulaciones del pavimento.
  * **Intervención del conductor:** maniobra o empuje externo en el volante (impulso suave).
* **Controlador PID por zonas:** sintonización independiente de $K_p$ (Nominal, Moderado e Intenso), $K_i$ y $K_d$, con banda muerta configurable ($0{,}00\text{ m}$ para el modelo lineal ideal) y restricciones físicas del vehículo (distancia entre ejes $L = 2{,}637\text{ m}$, constante de tiempo del actuador $\tau_{\text{act}} = 0{,}08\text{ s}$, retardo de cámara $\tau_{\text{cam}} = 0{,}04\text{ s}$ y saturación de par $\pm 2{,}5\text{ Nm}$).
* **Evolución temporal continua y análisis detallado:**
  * Simulación continua (infinita) o de horizonte finito con velocidad de evolución regulable.
  * Controles de **Reanudar**, **Frenar** y **Reiniciar desde t = 0** conservando todo el historial simulado.
  * Al frenar la simulación, el gráfico pasa a modo interactivo con **zoom por rueda del mouse**, desplazamiento por arrastre, salto directo a cualquier instante (`Ir a instante [s]`) y acceso directo al instante de estabilización.
* **Indicadores y Flags de régimen:**
  * Tarjetas superiores con Desvío Lateral Máximo, Error Instantáneo $e(t)$, Torque Máximo Aplicado y Estado del Lazo (límite de carril $\pm 0{,}30\text{ m}$).
  * Barra de flags que registra el instante exacto en que se alcanza el **Estado Estable ($e_{ss}$)** y el instante en que el error logra **cero ($e = 0$)**, marcados también sobre las gráficas.

---

## 3. Instrucciones de Acceso y Ejecución

### Opción A: Acceso directo vía Web (Recomendado para evaluación)
1. Ingresar al enlace del **Tablero de Control Interactivo** indicado en la sección 1 desde cualquier navegador web.
2. Utilizar el panel lateral izquierdo (**Parámetros de Operación**) para ajustar las variables del sistema o presionar **Restaurar Caso 1 (Nominal)** para cargar los valores de referencia de la cátedra.

### Opción B: Ejecución en entorno local
1. Clonar el repositorio:
   ```bash
   git clone https://github.com/MorosiniP/K4572-MorosinP-CalabreseB--TFI-2026--II.git
   cd K4572-MorosinP-CalabreseB--TFI-2026--II
   ```
2. Instalar las dependencias (`numpy`, `matplotlib`, `plotly`, `streamlit`):
   ```bash
   pip install -r requirements.txt
   ```
3. Ejecutar la aplicación:
   ```bash
   streamlit run app.py
   ```
