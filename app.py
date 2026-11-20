import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# Configuración de página
st.set_page_config(
    page_title="Simulador Lane Assist - VW Golf VII",
    page_icon="🚗",
    layout="wide"
)

# --- ESTILOS CSS COMPACTOS (Optimizado para que todo entre en una sola pantalla) ---
st.markdown("""
<style>
/* Reducir márgenes superiores e inferiores del contenedor principal */
.block-container {
    padding-top: 0.8rem !important;
    padding-bottom: 0.5rem !important;
    padding-left: 1.8rem !important;
    padding-right: 1.8rem !important;
    max-width: 100% !important;
}

/* Header compacto en una sola línea elegante */
.header-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1.5px solid #e2e8f0;
    padding-bottom: 4px;
    margin-bottom: 8px;
}
.header-title {
    font-size: 1.25rem !important;
    font-weight: 700 !important;
    color: #1e3a8a;
    margin: 0 !important;
}
.header-meta {
    font-size: 0.80rem !important;
    color: #475569;
}

/* Tarjetas de métricas compactas */
div[data-testid="stMetric"] {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 4px 10px !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}
[data-testid="stMetricValue"] {
    font-size: 1.12rem !important;
    font-weight: 700 !important;
    line-height: 1.2 !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.74rem !important;
    font-weight: 600 !important;
    color: #64748b !important;
    margin-bottom: 0px !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.68rem !important;
    margin-top: 0px !important;
}

/* Reducir espacio entre elementos */
div[data-testid="stVerticalBlock"] > div {
    gap: 0.4rem !important;
}
</style>
""", unsafe_allow_html=True)

# --- VALORES NOMINALES POR DEFECTO (CASO 1) ---
VALORES_CASO_1 = {
    "vx_kmh": 90.0,
    "tipo_pert": "Ráfaga temporal (Pulso)",
    "amp_pert": 0.45,
    "slider_pert": 0.45,
    "t_inicio": 2.0,
    "t_fin": 5.0,
    "Kp_mod": 1.8,
    "Ki_mod": 0.25,
    "Kd_mod": 1.1,
    "Kp_int": 2.6,
    "Ki_int": 0.35,
    "Kd_int": 1.4,
    "banda_muerta": 0.08,
    "torque_max": 2.5,
    "tau_cam": 0.04,
}

# Inicializar session_state si no existe
for k, v in VALORES_CASO_1.items():
    if k not in st.session_state:
        st.session_state[k] = v

def restaurar_caso_1():
    for k, v in VALORES_CASO_1.items():
        st.session_state[k] = v

# Callbacks para sincronizar slider y number_input de perturbación
def sync_num_to_slider():
    st.session_state["slider_pert"] = float(np.clip(st.session_state["amp_pert"], -1.5, 1.5))

def sync_slider_to_num():
    st.session_state["amp_pert"] = st.session_state["slider_pert"]

# --- BARRA LATERAL: TABLERO DE CONTROL ---
st.sidebar.markdown("### 🧪 Escenarios de Ensayo")
st.sidebar.button(
    "🔄 Restaurar Caso 1 (Nominal)",
    help="Restablece todos los parámetros por defecto de la cátedra para el Caso 1 (Nominal).",
    on_click=restaurar_caso_1,
    use_container_width=True
)
st.sidebar.info(
    "**Caso 1 (Nominal):** Valores por defecto $\\rightarrow$ El vehículo absorbe la ráfaga de viento "
    "sin tocar la línea de $0,30\\text{ m}$ y vuelve al centro de forma estable."
)

st.sidebar.header("Parámetros de Operación")

vx_kmh = st.sidebar.number_input(
    "Velocidad longitudinal [km/h] (teclado)",
    min_value=0.0,
    max_value=220.0,
    step=5.0,
    key="vx_kmh"
)
vx = vx_kmh / 3.6  # Conversión a m/s

if vx_kmh < 65:
    st.sidebar.warning("⚠️ Velocidad < 65 km/h: En el vehículo real (SSP 516), el sistema pasa a estado PASIVO.")

st.sidebar.subheader("Perturbación Externa (Viento / Peralte)")
tipo_pert = st.sidebar.selectbox(
    "Tipo de perturbación",
    ["Ráfaga temporal (Pulso)", "Viento constante / Peralte (Escalón)"],
    key="tipo_pert"
)

# Entrada numérica exacta + slider sincronizados
amp_pert = st.sidebar.number_input(
    "Intensidad de perturbación (teclado)",
    min_value=-3.0,
    max_value=3.0,
    step=0.05,
    format="%.3f",
    key="amp_pert",
    on_change=sync_num_to_slider
)
amp_slider = st.sidebar.slider(
    "Ajuste rápido intensidad",
    min_value=-1.5,
    max_value=1.5,
    step=0.05,
    key="slider_pert",
    on_change=sync_slider_to_num
)

col_t1, col_t2 = st.sidebar.columns(2)
t_inicio = col_t1.number_input("t inicio [s]", min_value=0.0, max_value=9.5, step=0.5, key="t_inicio")
t_fin = col_t2.number_input("t fin [s]", min_value=0.5, max_value=10.0, step=0.5, key="t_fin")

st.sidebar.subheader("Sintonización PID - Zona Moderada (0.08m - 0.15m)")
Kp_mod = st.sidebar.number_input("Kp moderado [Nm/m]", min_value=0.0, max_value=20.0, step=0.1, key="Kp_mod")
Ki_mod = st.sidebar.number_input("Ki moderado [Nm/(m·s)]", min_value=0.0, max_value=10.0, step=0.05, key="Ki_mod")
Kd_mod = st.sidebar.number_input("Kd moderado [Nm·s/m]", min_value=0.0, max_value=10.0, step=0.1, key="Kd_mod")

st.sidebar.subheader("Sintonización PID - Zona Intensa (> 0.15m)")
Kp_int = st.sidebar.number_input("Kp intenso [Nm/m]", min_value=0.0, max_value=20.0, step=0.1, key="Kp_int")
Ki_int = st.sidebar.number_input("Ki intenso [Nm/(m·s)]", min_value=0.0, max_value=10.0, step=0.05, key="Ki_int")
Kd_int = st.sidebar.number_input("Kd intenso [Nm·s/m]", min_value=0.0, max_value=10.0, step=0.1, key="Kd_int")

st.sidebar.subheader("Restricciones Físicas del Sistema")
banda_muerta = st.sidebar.number_input("Banda muerta [m] (teclado)", min_value=0.0, max_value=0.50, step=0.01, key="banda_muerta")
torque_max = st.sidebar.number_input("Saturación par EPS [Nm] (teclado)", min_value=0.5, max_value=10.0, step=0.1, key="torque_max")
tau_cam = st.sidebar.number_input("Retardo cámara R242 [s] (teclado)", min_value=0.0, max_value=0.50, step=0.01, key="tau_cam")

# Opciones de visualización en la barra lateral para liberar espacio vertical principal
st.sidebar.subheader("Visualización de Gráficas")
tamano_graf = st.sidebar.radio(
    "Escala de gráficas:",
    ["Ajustar a pantalla (Compacta)", "Mediana", "Ampliada"],
    index=0
)
if tamano_graf == "Ajustar a pantalla (Compacta)":
    alto_fig = 3.7
elif tamano_graf == "Mediana":
    alto_fig = 4.8
else:
    alto_fig = 6.8

pos_leyenda = st.sidebar.selectbox(
    "Ubicación de referencias (leyendas):",
    ["Exterior derecha (no tapa gráficos)", "Superior", "Ocultar"],
    index=0
)

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
delay_steps = int(round(tau_cam / dt))

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

e[-1] = e[-2]
u[-1] = u[-2]

# --- ENCABEZADO PRINCIPAL COMPACTO ---
st.markdown("""
<div class="header-container">
    <div class="header-title">🚗 Simulador de Control: Lane Assist (VW Golf VII)</div>
    <div class="header-meta"><strong>UTN - FRBA</strong> | Tecnologías de Automatización | Lazo Cerrado PID por Umbrales</div>
</div>
""", unsafe_allow_html=True)

# --- MÉTRICAS EN TIEMPO REAL (COMPACTAS) ---
desvio_max = np.max(np.abs(y))
ess_final = np.abs(e[-1])
torque_pico = np.max(np.abs(u))
en_carril = desvio_max < 0.30

col1, col2, col3, col4 = st.columns(4)
col1.metric("Desvío Lateral Máximo", f"{desvio_max:.3f} m", delta="Límite: ±0.30 m", delta_color="off")
col2.metric("Error Estado Estable (ess)", f"{ess_final:.4f} m", delta="Ref: 0.00 m", delta_color="off")
col3.metric("Torque Máximo Aplicado", f"{torque_pico:.2f} Nm", delta=f"Tope: ±{torque_max} Nm", delta_color="off")
col4.metric(
    "Estado del Lazo",
    "ESTABLE (En carril)" if en_carril else "CRÍTICO (Pisa línea)",
    delta="Dentro de carril" if en_carril else "Excede límite",
    delta_color="normal" if en_carril else "inverse"
)

# --- GRÁFICAS ---
fig, axs = plt.subplots(3, 1, figsize=(11, alto_fig), sharex=True)

# 1. Posición Lateral
axs[0].plot(t, y, label=r'Posición real $\theta_o(t)$ [m]', color='#1f77b4', linewidth=1.6)
axs[0].plot(t, r, '--', label=r'Referencia $\theta_i(t) = 0$ m', color='black', linewidth=1.0)
axs[0].axhspan(-banda_muerta, banda_muerta, color='green', alpha=0.15, label=f'Nominal (±{banda_muerta:.2f} m)')
axs[0].axhspan(banda_muerta, 0.15, color='yellow', alpha=0.15, label='Moderada (±0.15 m)')
axs[0].axhspan(-0.15, -banda_muerta, color='yellow', alpha=0.15)
axs[0].axhline(0.30, color='red', linestyle=':', linewidth=1.1, label='Límite carril (±0.30 m)')
axs[0].axhline(-0.30, color='red', linestyle=':', linewidth=1.1)
axs[0].set_ylabel('Desvío [m]', fontsize=8.5, fontweight='bold')
axs[0].tick_params(labelsize=8)
axs[0].grid(True, alpha=0.35, linestyle='--')

# 2. Señal de Error
axs[1].plot(t, e, label=r'Error $e(t)$ [m]', color='#d62728', linewidth=1.5)
axs[1].set_ylabel('Error [m]', fontsize=8.5, fontweight='bold')
axs[1].tick_params(labelsize=8)
axs[1].grid(True, alpha=0.35, linestyle='--')

# 3. Torque Corrector y Perturbación
axs[2].plot(t, u, label=r'Torque corrector EPS $u(t)$ [Nm]', color='#9467bd', linewidth=1.5)
axs[2].plot(t, perturbacion, '--', label='Perturbación ext.', color='#ff7f0e', linewidth=1.2)
axs[2].set_ylabel('Torque / Pert.', fontsize=8.5, fontweight='bold')
axs[2].set_xlabel('Tiempo [s]', fontsize=8.5, fontweight='bold')
axs[2].tick_params(labelsize=8)
axs[2].grid(True, alpha=0.35, linestyle='--')

# Configuración de referencias (leyendas) para no tapar los datos
if pos_leyenda == "Exterior derecha (no tapa gráficos)":
    axs[0].legend(loc='center left', bbox_to_anchor=(1.01, 0.5), fontsize=7.2, frameon=True, facecolor='#fafafa', edgecolor='#dddddd')
    axs[1].legend(loc='center left', bbox_to_anchor=(1.01, 0.5), fontsize=7.2, frameon=True, facecolor='#fafafa', edgecolor='#dddddd')
    axs[2].legend(loc='center left', bbox_to_anchor=(1.01, 0.5), fontsize=7.2, frameon=True, facecolor='#fafafa', edgecolor='#dddddd')
    plt.subplots_adjust(left=0.07, right=0.76, top=0.96, bottom=0.11, hspace=0.18)
elif pos_leyenda == "Superior":
    axs[0].legend(loc='lower left', bbox_to_anchor=(0.0, 1.02), ncol=3, fontsize=6.8, frameon=False)
    axs[1].legend(loc='lower left', bbox_to_anchor=(0.0, 1.02), ncol=2, fontsize=6.8, frameon=False)
    axs[2].legend(loc='lower left', bbox_to_anchor=(0.0, 1.02), ncol=2, fontsize=6.8, frameon=False)
    plt.subplots_adjust(left=0.07, right=0.98, top=0.92, bottom=0.11, hspace=0.28)
else:
    # Ocultar leyendas
    plt.subplots_adjust(left=0.07, right=0.98, top=0.96, bottom=0.11, hspace=0.18)

try:
    st.pyplot(fig, width="stretch")
except TypeError:
    st.pyplot(fig, use_container_width=True)
