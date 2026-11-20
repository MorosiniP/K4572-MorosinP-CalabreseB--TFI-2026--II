import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# Configuración de página
st.set_page_config(page_title="Simulador Lane Assist - VW Golf VII", layout="wide")

st.title("Simulador de Control: Lane Assist (VW Golf VII)")
st.markdown("**Materia:** Teoría de Control (UTN - FRBA) | **Modelo:** Lazo Cerrado con Controlador PID por Umbrales")

# --- BARRA LATERAL: TABLERO DE CONTROL ---
st.sidebar.header("Parámetros de Operación")

vx_kmh = st.sidebar.slider("Velocidad longitudinal [km/h]", min_value=50, max_value=160, value=90, step=5)
vx = vx_kmh / 3.6  # Conversión a m/s

if vx_kmh < 65:
    st.sidebar.warning("⚠️ Velocidad < 65 km/h: En el vehículo real (SSP 516), el sistema pasa a estado PASIVO.")

st.sidebar.subheader("Perturbación Externa (Viento / Peralte)")
tipo_pert = st.sidebar.selectbox("Tipo de perturbación", ["Ráfaga temporal (Pulso)", "Viento constante / Peralte (Escalón)"])
amp_pert = st.sidebar.slider("Intensidad de perturbación", min_value=0.0, max_value=1.2, value=0.45, step=0.05)
t_inicio = st.sidebar.slider("Tiempo de inicio [s]", min_value=1.0, max_value=5.0, value=2.0, step=0.5)
t_fin = st.sidebar.slider("Tiempo de fin [s] (solo pulso)", min_value=3.0, max_value=9.0, value=5.0, step=0.5)

st.sidebar.subheader("Sintonización PID - Zona Moderada (0.08m - 0.15m)")
Kp_mod = st.sidebar.slider("Kp moderado [Nm/m]", 0.1, 5.0, 1.8, 0.1)
Ki_mod = st.sidebar.slider("Ki moderado [Nm/(m·s)]", 0.0, 2.0, 0.25, 0.05)
Kd_mod = st.sidebar.slider("Kd moderado [Nm·s/m]", 0.0, 3.0, 1.1, 0.1)

st.sidebar.subheader("Sintonización PID - Zona Intensa (> 0.15m)")
Kp_int = st.sidebar.slider("Kp intenso [Nm/m]", 0.5, 6.0, 2.6, 0.1)
Ki_int = st.sidebar.slider("Ki intenso [Nm/(m·s)]", 0.0, 2.0, 0.35, 0.05)
Kd_int = st.sidebar.slider("Kd intenso [Nm·s/m]", 0.0, 4.0, 1.4, 0.1)

st.sidebar.subheader("Restricciones Físicas del Sistema")
banda_muerta = st.sidebar.slider("Zona de nominalidad / banda muerta [m]", 0.0, 0.15, 0.08, 0.01)
torque_max = st.sidebar.slider("Saturación de par EPS J500 [Nm]", 1.0, 4.0, 2.5, 0.1)
tau_cam = st.sidebar.slider("Retardo cámara R242 [s]", 0.0, 0.20, 0.04, 0.02)

# --- MODELO FÍSICO Y SIMULACIÓN ---
L_wb = 2.637       # Distancia entre ejes VW Golf VII (m)
tau_act = 0.08     # Constante de tiempo actuador EPS J500 + V187 (s)

dt = 0.01          # Paso de integración: 10 ms
T_total = 10.0     # Tiempo total simulado: 10 s
t = np.arange(0, T_total, dt)
n = len(t)

r = np.zeros(n)
y = np.zeros(n)
psi = np.zeros(n)
delta = np.zeros(n)
e = np.zeros(n)
u = np.zeros(n)
perturbacion = np.zeros(n)

if tipo_pert == "Ráfaga temporal (Pulso)":
    perturbacion[(t >= t_inicio) & (t <= t_fin)] = amp_pert
else:
    perturbacion[t >= t_inicio] = amp_pert

integral_e = 0.0
error_prev = 0.0
delay_steps = int(tau_cam / dt)

for k in range(delay_steps, n - 1):
    y_medido = y[k - delay_steps]
    e[k] = r[k] - y_medido
    abs_e = abs(e[k])

    if abs_e <= banda_muerta:
        u_raw = 0.0
    elif abs_e <= 0.15:
        integral_e += e[k] * dt
        derivada_e = (e[k] - error_prev) / dt
        u_raw = Kp_mod * e[k] + Ki_mod * integral_e + Kd_mod * derivada_e
    else:
        integral_e += e[k] * dt
        derivada_e = (e[k] - error_prev) / dt
        u_raw = Kp_int * e[k] + Ki_int * integral_e + Kd_int * derivada_e

    u[k] = np.clip(u_raw, -torque_max, torque_max)
    error_prev = e[k]

    d_delta = ((u[k] * 0.035) - delta[k]) / tau_act
    delta[k + 1] = delta[k] + d_delta * dt

    d_psi = (vx / L_wb) * delta[k]
    psi[k + 1] = psi[k] + d_psi * dt

    dy = vx * psi[k] + perturbacion[k] * dt * 10.0
    y[k + 1] = y[k] + dy * dt

# --- MÉTRICAS EN TIEMPO REAL ---
desvio_max = np.max(np.abs(y))
ess_final = np.abs(e[-2])
torque_pico = np.max(np.abs(u))

col1, col2, col3, col4 = st.columns(4)
col1.metric("Desvío Lateral Máximo", f"{desvio_max:.3f} m", delta="Límite carril: 0.30 m", delta_color="off")
col2.metric("Error Estado Estable (ess)", f"{ess_final:.4f} m")
col3.metric("Torque Máximo Aplicado", f"{torque_pico:.2f} Nm", delta=f"Tope: ±{torque_max} Nm", delta_color="off")
estado = "ESTABLE (En carril)" if desvio_max < 0.30 else "CRÍTICO (Pisa línea)"
col4.metric("Estado del Lazo", estado)

# --- GRÁFICAS ---
fig, axs = plt.subplots(3, 1, figsize=(11, 8), sharex=True)

axs[0].plot(t, y, label='Posición lateral real θo(t) [m]', color='#1f77b4', linewidth=2)
axs[0].plot(t, r, '--', label='Referencia θi(t) = 0 m', color='black')
axs[0].axhspan(-banda_muerta, banda_muerta, color='green', alpha=0.15, label=f'Zona nominalidad (±{banda_muerta:.2f} m)')
axs[0].axhspan(banda_muerta, 0.15, color='yellow', alpha=0.15, label='Zona corrección moderada (±0.15 m)')
axs[0].axhspan(-0.15, -banda_muerta, color='yellow', alpha=0.15)
axs[0].axhline(0.30, color='red', linestyle=':', linewidth=1.2, label='Límite de carril (±0.30 m)')
axs[0].axhline(-0.30, color='red', linestyle=':', linewidth=1.2)
axs[0].set_ylabel('Desvío [m]')
axs[0].set_title('Respuesta Dinámica del Lazo Cerrado - Lane Assist VW Golf VII')
axs[0].legend(loc='upper right', fontsize=8)
axs[0].grid(True, alpha=0.4)

axs[1].plot(t, e, label='Señal de error e(t) [m]', color='#d62728', linewidth=1.8)
axs[1].set_ylabel('Error [m]')
axs[1].legend(loc='upper right', fontsize=8)
axs[1].grid(True, alpha=0.4)

axs[2].plot(t, u, label='Torque corrector EPS u(t) [Nm]', color='#9467bd', linewidth=1.8)
axs[2].plot(t, perturbacion, '--', label='Perturbación externa', color='#ff7f0e', linewidth=1.5)
axs[2].set_ylabel('Torque / Perturbación')
axs[2].set_xlabel('Tiempo [s]')
axs[2].legend(loc='upper right', fontsize=8)
axs[2].grid(True, alpha=0.4)

plt.tight_layout()
st.pyplot(fig)