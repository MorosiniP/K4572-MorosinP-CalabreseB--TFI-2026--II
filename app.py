import time
from collections import deque
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

/* Tarjetas de métricas compactas con alto contraste garantizado (números en negro puro) */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-bottom: 8px;
}
.metric-card {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 8px 12px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.metric-label {
    font-size: 0.76rem;
    font-weight: 600;
    color: #334155 !important;
    margin-bottom: 2px;
}
.metric-value {
    font-size: 1.22rem;
    font-weight: 800;
    color: #000000 !important;
    line-height: 1.25;
}
.metric-delta {
    font-size: 0.72rem;
    font-weight: 500;
    color: #334155 !important;
    margin-top: 2px;
}

/* Reducir espacio entre elementos */
div[data-testid="stVerticalBlock"] > div {
    gap: 0.4rem !important;
}
</style>
""", unsafe_allow_html=True)

# --- CONSTANTES FÍSICAS DEL SISTEMA (VW Golf VII - SSP 516) ---
L_wb = 2.637          # Distancia entre ejes VW Golf VII [m]
tau_act = 0.08        # Constante de tiempo actuador EPS J500 + V187 [s]
torque_max = 2.5      # Saturación par EPS [Nm]
tau_cam = 0.04        # Retardo cámara R242 [s]

# --- TIPOS DE PERTURBACIÓN EXTERNA ---
TIPOS_PERTURBACION = [
    "Viento lateral (Crosswinds)",
    "Peralte o pendiente transversal de la calzada",
    "Irregularidades del asfalto",
    "Intervención del conductor",
]

# --- VALORES NOMINALES POR DEFECTO (CASO 1) ---
VALORES_CASO_1 = {
    "vx_kmh": 90.0,
    "tipo_pert": "Viento lateral (Crosswinds)",
    "amp_pert": 0.45,
    "slider_pert": 0.45,
    "t_inicio": 2.0,
    "t_fin": 5.0,
    "Kp": 1.8,
    "Ki": 0.25,
    "Kd": 1.1,
    "banda_muerta": 0.08,
    "T_total": 10.0,
}

# Inicializar session_state si no existe o si cambió de versión
for k, v in VALORES_CASO_1.items():
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state["tipo_pert"] not in TIPOS_PERTURBACION:
    st.session_state["tipo_pert"] = VALORES_CASO_1["tipo_pert"]


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
    "**Caso 1 (Nominal):** Valores por defecto $\\rightarrow$ El vehículo absorbe la ráfaga de viento lateral "
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

st.sidebar.subheader("Perturbaciones Externas")
tipo_pert = st.sidebar.selectbox(
    "Tipo de perturbación",
    TIPOS_PERTURBACION,
    key="tipo_pert"
)

descripciones_pert = {
    "Viento lateral (Crosswinds)": "Ráfaga lateral temporal (pulso) entre t inicio y t fin.",
    "Peralte o pendiente transversal de la calzada": "Inclinación lateral constante (escalón) a partir de t inicio.",
    "Irregularidades del asfalto": "Baches y ondulaciones de la calzada con vibraciones entre t inicio y t fin.",
    "Intervención del conductor": "Empuje o maniobra externa en el volante (impulso suave) entre t inicio y t fin.",
}
st.sidebar.caption(descripciones_pert[tipo_pert])

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

es_peralte = (tipo_pert == "Peralte o pendiente transversal de la calzada")
col_t1, col_t2 = st.sidebar.columns(2)
t_inicio = col_t1.number_input(
    "t inicio [s]",
    min_value=0.0,
    step=0.5,
    key="t_inicio"
)
t_fin = col_t2.number_input(
    "t fin [s]",
    min_value=0.1,
    step=0.5,
    key="t_fin",
    disabled=es_peralte
)

st.sidebar.subheader("Sintonización PID")
Kp1 = st.sidebar.number_input("Kp Nominal [Nm/m]", min_value=0.0, max_value=20.0, step=0.1, key="Kp1")
Kp2 = st.sidebar.number_input("Kp Moderado [Nm/m]", min_value=0.0, max_value=20.0, step=0.1, key="Kp2")
Kp3 = st.sidebar.number_input("Kp Intenso [Nm/m]", min_value=0.0, max_value=20.0, step=0.1, key="Kp3")
Ki = st.sidebar.number_input("Ki [Nm/(m·s)]", min_value=0.0, max_value=10.0, step=0.05, key="Ki")
Kd = st.sidebar.number_input("Kd [Nm·s/m]", min_value=0.0, max_value=10.0, step=0.1, key="Kd")

st.sidebar.subheader("Restricciones y Horizonte Temporal")
banda_muerta = st.sidebar.number_input(
    "Banda muerta [m] (0.00 = modelo lineal ideal)",
    min_value=0.0,
    max_value=0.20,
    step=0.01,
    format="%.2f",
    key="banda_muerta"
)
simulacion_infinita = st.sidebar.checkbox("Simulación infinita (continua)", value=True)
T_total = st.sidebar.number_input(
    "Ventana de tiempo visible [s]" if simulacion_infinita else "Horizonte temporal T_total [s]",
    min_value=5.0,
    max_value=40.0,
    step=5.0,
    key="T_total"
)

# Opciones de visualización y animación en la barra lateral
st.sidebar.subheader("Visualización y Evolución Temporal")
animar_evolucion = st.sidebar.checkbox(
    "Animar evolución en el tiempo",
    value=True,
    disabled=simulacion_infinita
)
velocidad_anim = st.sidebar.select_slider(
    "Velocidad de evolución:",
    options=["Muy lenta", "Lenta", "Normal", "Rápida"],
    value="Lenta",
    disabled=not (animar_evolucion or simulacion_infinita)
)
st.sidebar.button("▶️ Reiniciar desde t = 0" if simulacion_infinita else "▶️ Reproducir evolución", use_container_width=True)

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
dt = 0.01          # Paso de integración: 10 ms
delay_steps = int(round(tau_cam / dt))
t_fin_eff = max(t_fin, t_inicio + 0.1)
dur_pert = t_fin_eff - t_inicio
rng_asfalto = np.random.default_rng(42)

# Buffers acotados a la ventana visible para mantener memoria constante y render fluido
buf_len = int(round(T_total / dt)) + 20
t_buf = deque(maxlen=buf_len)
y_buf = deque(maxlen=buf_len)
e_buf = deque(maxlen=buf_len)
u_buf = deque(maxlen=buf_len)
p_buf = deque(maxlen=buf_len)
y_delay_buf = deque([0.0] * (delay_steps + 1), maxlen=delay_steps + 1)

# Estado dinámico del sistema
k_step = 0
y_k = 0.0
psi_k = 0.0
delta_k = 0.0
integral_e = 0.0
error_prev = 0.0
desvio_max = 0.0
torque_pico = 0.0


def calcular_perturbacion(t_actual: float) -> float:
    if tipo_pert == "Viento lateral (Crosswinds)":
        return amp_pert if (t_inicio <= t_actual <= t_fin_eff) else 0.0
    if tipo_pert == "Peralte o pendiente transversal de la calzada":
        return amp_pert if (t_actual >= t_inicio) else 0.0
    if tipo_pert == "Irregularidades del asfalto":
        if t_inicio <= t_actual <= t_fin_eff:
            tm = t_actual - t_inicio
            perfil = (
                0.65
                + 0.50 * np.sin(2.0 * np.pi * 1.6 * tm)
                + 0.35 * np.sin(2.0 * np.pi * 4.2 * tm)
                + 0.25 * float(rng_asfalto.normal(0.0, 1.0))
            )
            return amp_pert * perfil
        return 0.0
    if tipo_pert == "Intervención del conductor":
        if t_inicio <= t_actual <= t_fin_eff:
            tm = t_actual - t_inicio
            return amp_pert * 1.25 * float(np.sin(np.pi * tm / dur_pert))
        return 0.0
    return 0.0


def avanzar_paso():
    global k_step, y_k, psi_k, delta_k, integral_e, error_prev, desvio_max, torque_pico

    t_k = k_step * dt
    p_k = calcular_perturbacion(t_k)

    if k_step < delay_steps:
        e_k = 0.0
        u_k = 0.0
    else:
        y_medido = y_delay_buf[0]
        e_k = 0.0 - y_medido  # Referencia r(t) = 0.0 m

        Kp = 0.0

        if abs(e_k) <= 0.08:
            Kp = Kp1
        elif abs(e_k) <= 0.15:
            Kp = Kp2
        else:
            Kp = Kp3

        integral_e += e_k * dt
        derivada_e = (e_k - error_prev) / dt
        u_raw = Kp * e_k + Ki * integral_e + Kd * derivada_e

        u_k = float(np.clip(u_raw, -torque_max, torque_max))
        error_prev = e_k

    t_buf.append(t_k)
    y_buf.append(y_k)
    e_buf.append(e_k)
    u_buf.append(u_k)
    p_buf.append(p_k)

    desvio_max = max(desvio_max, abs(y_k))
    torque_pico = max(torque_pico, abs(u_k))

    # Integración por Euler hacia k + 1
    d_delta = ((u_k * 0.035) - delta_k) / tau_act
    delta_next = delta_k + d_delta * dt

    d_psi = (vx / L_wb) * delta_k
    psi_next = psi_k + d_psi * dt

    dy = vx * psi_k + p_k * dt * 10.0
    y_next = y_k + dy * dt

    y_k = y_next
    psi_k = psi_next
    delta_k = delta_next
    y_delay_buf.append(y_next)
    k_step += 1


# --- ENCABEZADO PRINCIPAL COMPACTO ---
st.markdown("""
<div class="header-container">
    <div class="header-title">🚗 Simulador de Control: Lane Assist (VW Golf VII)</div>
    <div class="header-meta"><strong>UTN - FRBA</strong> | Tecnologías de Automatización | Lazo Cerrado PID</div>
</div>
""", unsafe_allow_html=True)

# Contenedores dinámicos para actualizar métricas y gráficas paso a paso
metrics_placeholder = st.empty()
plot_placeholder = st.empty()


def render_metrics(es_final_finito: bool = False):
    t_actual = t_buf[-1]
    ess_actual = abs(e_buf[-1])
    en_carril = desvio_max < 0.30

    if len(y_buf) > 1:
        y_reciente = list(y_buf)[-min(50, len(y_buf)):]
        variacion_final = float(np.max(np.abs(np.diff(y_reciente))))
    else:
        variacion_final = float("inf")

    estabilizado = (len(y_buf) >= 50 and variacion_final < 0.0005)
    if (simulacion_infinita and estabilizado) or (es_final_finito and variacion_final < 0.0005):
        titulo_error = "Error Estado Estable (ess)"
        delta_error = f"Estabilizado en t = {t_actual:.1f} s"
    else:
        titulo_error = "Error Instantáneo e(t)"
        delta_error = f"En transitorio (t = {t_actual:.1f} s)"

    estado_texto = "ESTABLE (En carril)" if en_carril else "CRÍTICO (Pisa línea)"
    estado_delta = "Dentro de carril" if en_carril else "Excede límite"
    estado_delta_color = "#15803d" if en_carril else "#b91c1c"
    estado_val_color = "#000000" if en_carril else "#991b1b"

    metrics_placeholder.markdown(
        f"""
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Desvío Lateral Máximo</div>
                <div class="metric-value" style="color:#000000 !important;">{desvio_max:.3f} m</div>
                <div class="metric-delta" style="color:#334155 !important;">Límite: ±0.30 m</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">{titulo_error}</div>
                <div class="metric-value" style="color:#000000 !important;">{ess_actual:.4f} m</div>
                <div class="metric-delta" style="color:#334155 !important;">{delta_error}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Torque Máximo Aplicado</div>
                <div class="metric-value" style="color:#000000 !important;">{torque_pico:.2f} Nm</div>
                <div class="metric-delta" style="color:#334155 !important;">Tope: ±{torque_max:.1f} Nm</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Estado del Lazo</div>
                <div class="metric-value" style="color:{estado_val_color} !important;">{estado_texto}</div>
                <div class="metric-delta" style="color:{estado_delta_color} !important; font-weight:600;">{estado_delta}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


# --- CONFIGURACIÓN BASE DE GRÁFICAS ---
fig, axs = plt.subplots(3, 1, figsize=(11, alto_fig), sharex=True)

y_lim = 0.36
e_lim = 0.15
u_lim = 0.60

# 1. Posición Lateral
(line_y,) = axs[0].plot([], [], label=r'Posición real $\theta_o(t)$ [m]', color='#1f77b4', linewidth=1.7)
(dot_y,) = axs[0].plot([], [], 'o', color='#1f77b4', markersize=5)
axs[0].axhline(0.0, linestyle='--', label=r'Referencia $\theta_i(t) = 0$ m', color='black', linewidth=1.0)
axs[0].axhspan(-banda_muerta, banda_muerta, color='green', alpha=0.15, label=f'Banda nominal (±{banda_muerta:.2f} m)')
axs[0].axhline(0.30, color='red', linestyle=':', linewidth=1.1, label='Límite carril (±0.30 m)')
axs[0].axhline(-0.30, color='red', linestyle=':', linewidth=1.1)
vline_0 = axs[0].axvline(0.0, color='#64748b', linestyle='-.', linewidth=0.9, alpha=0.6)
axs[0].set_xlim(0, T_total)
axs[0].set_ylim(-y_lim, y_lim)
axs[0].set_ylabel('Desvío [m]', fontsize=8.5, fontweight='bold')
axs[0].tick_params(labelsize=8)
axs[0].grid(True, alpha=0.35, linestyle='--')

# 2. Señal de Error
(line_e,) = axs[1].plot([], [], label=r'Error $e(t)$ [m]', color='#d62728', linewidth=1.5)
(dot_e,) = axs[1].plot([], [], 'o', color='#d62728', markersize=5)
vline_1 = axs[1].axvline(0.0, color='#64748b', linestyle='-.', linewidth=0.9, alpha=0.6)
axs[1].set_ylim(-e_lim, e_lim)
axs[1].set_ylabel('Error [m]', fontsize=8.5, fontweight='bold')
axs[1].tick_params(labelsize=8)
axs[1].grid(True, alpha=0.35, linestyle='--')

# 3. Torque Corrector y Perturbación
(line_u,) = axs[2].plot([], [], label=r'Torque corrector EPS $u(t)$ [Nm]', color='#9467bd', linewidth=1.5)
(dot_u,) = axs[2].plot([], [], 'o', color='#9467bd', markersize=5)
(line_p,) = axs[2].plot([], [], '--', label=tipo_pert, color='#ff7f0e', linewidth=1.3)
vline_2 = axs[2].axvline(0.0, color='#64748b', linestyle='-.', linewidth=0.9, alpha=0.6)
axs[2].set_ylim(-u_lim, u_lim)
axs[2].set_ylabel('Torque / Pert.', fontsize=8.5, fontweight='bold')
axs[2].set_xlabel('Tiempo [s]', fontsize=8.5, fontweight='bold')
axs[2].tick_params(labelsize=8)
axs[2].grid(True, alpha=0.35, linestyle='--')

# Referencias visuales para t_inicio y t_fin
refs_tiempo = [t_inicio] if es_peralte else [t_inicio, t_fin]
for ax in axs:
    ax.axvline(t_inicio, color='#ff7f0e', linestyle=':', linewidth=0.9, alpha=0.55)
    if not es_peralte:
        ax.axvline(t_fin, color='#ff7f0e', linestyle=':', linewidth=0.9, alpha=0.55)

if T_total <= 10.0:
    tick_step = 1.0
elif T_total <= 20.0:
    tick_step = 2.0
else:
    tick_step = 5.0


def actualizar_xticks(x_min: float, x_max: float):
    inicio_tick = np.ceil(x_min / tick_step) * tick_step
    base_ticks = list(np.arange(inicio_tick, x_max + 1e-9, tick_step))
    min_gap = (x_max - x_min) * 0.035
    valid_refs = [float(rv) for rv in refs_tiempo if x_min <= rv <= x_max]
    x_ticks = [bt for bt in base_ticks if all(abs(bt - rv) >= min_gap for rv in valid_refs)]
    for rv in valid_refs:
        if all(abs(rv - tv) >= 1e-6 for tv in x_ticks):
            x_ticks.append(rv)
    x_ticks.sort()
    axs[2].set_xticks(x_ticks)
    axs[2].set_xticklabels([f"{tv:g}" for tv in x_ticks])


actualizar_xticks(0.0, T_total)

# Configuración de referencias (leyendas) para no tapar los datos
if pos_leyenda == "Exterior derecha (no tapa gráficos)":
    axs[0].legend(loc='center left', bbox_to_anchor=(1.01, 0.5), fontsize=7.2, frameon=True, facecolor='#fafafa', edgecolor='#dddddd')
    axs[1].legend(loc='center left', bbox_to_anchor=(1.01, 0.5), fontsize=7.2, frameon=True, facecolor='#fafafa', edgecolor='#dddddd')
    axs[2].legend(loc='center left', bbox_to_anchor=(1.01, 0.5), fontsize=7.2, frameon=True, facecolor='#fafafa', edgecolor='#dddddd')
    plt.subplots_adjust(left=0.07, right=0.73, top=0.96, bottom=0.11, hspace=0.18)
elif pos_leyenda == "Superior":
    axs[0].legend(loc='lower left', bbox_to_anchor=(0.0, 1.02), ncol=3, fontsize=6.8, frameon=False)
    axs[1].legend(loc='lower left', bbox_to_anchor=(0.0, 1.02), ncol=2, fontsize=6.8, frameon=False)
    axs[2].legend(loc='lower left', bbox_to_anchor=(0.0, 1.02), ncol=2, fontsize=6.8, frameon=False)
    plt.subplots_adjust(left=0.07, right=0.98, top=0.92, bottom=0.11, hspace=0.28)
else:
    plt.subplots_adjust(left=0.07, right=0.98, top=0.96, bottom=0.11, hspace=0.18)


def render_frame(mostrar_cursor: bool, es_final_finito: bool = False):
    global y_lim, e_lim, u_lim

    t_arr = list(t_buf)
    y_arr = list(y_buf)
    e_arr = list(e_buf)
    u_arr = list(u_buf)
    p_arr = list(p_buf)

    line_y.set_data(t_arr, y_arr)
    line_e.set_data(t_arr, e_arr)
    line_u.set_data(t_arr, u_arr)
    line_p.set_data(t_arr, p_arr)

    # Avanzar la ventana del eje X cuando la simulación supera T_total
    t_cur = t_arr[-1]
    x_min = max(0.0, t_cur - T_total)
    x_max = max(T_total, t_cur)
    axs[0].set_xlim(x_min, x_max)
    actualizar_xticks(x_min, x_max)

    # Ampliar dinámicamente los límites verticales si algún pico supera la escala actual
    y_req = max(0.36, max(abs(v) for v in y_arr) * 1.15)
    e_req = max(0.15, max(abs(v) for v in e_arr) * 1.15)
    u_req = max(0.60, max(max(abs(v) for v in u_arr), max(abs(v) for v in p_arr)) * 1.15)
    if y_req > y_lim:
        y_lim = y_req
        axs[0].set_ylim(-y_lim, y_lim)
    if e_req > e_lim:
        e_lim = e_req
        axs[1].set_ylim(-e_lim, e_lim)
    if u_req > u_lim:
        u_lim = u_req
        axs[2].set_ylim(-u_lim, u_lim)

    if mostrar_cursor:
        dot_y.set_data([t_cur], [y_arr[-1]])
        dot_e.set_data([t_cur], [e_arr[-1]])
        dot_u.set_data([t_cur], [u_arr[-1]])
        vline_0.set_xdata([t_cur, t_cur])
        vline_1.set_xdata([t_cur, t_cur])
        vline_2.set_xdata([t_cur, t_cur])
        vline_0.set_visible(True)
        vline_1.set_visible(True)
        vline_2.set_visible(True)
    else:
        dot_y.set_data([], [])
        dot_e.set_data([], [])
        dot_u.set_data([], [])
        vline_0.set_visible(False)
        vline_1.set_visible(False)
        vline_2.set_visible(False)

    render_metrics(es_final_finito=es_final_finito)
    try:
        plot_placeholder.pyplot(fig, width="stretch")
    except TypeError:
        plot_placeholder.pyplot(fig, use_container_width=True)


config_vel = {
    "Muy lenta": (20, 0.18),
    "Lenta": (25, 0.10),
    "Normal": (35, 0.04),
    "Rápida": (50, 0.01),
}
paso_muestras, pausa_seg = config_vel[velocidad_anim]

if simulacion_infinita:
    while True:
        for _ in range(paso_muestras):
            avanzar_paso()
        render_frame(mostrar_cursor=True)
        time.sleep(pausa_seg)
elif animar_evolucion:
    n_total = int(round(T_total / dt))
    pasos_restantes = n_total
    while pasos_restantes > 0:
        pasos_este_cuadro = min(paso_muestras, pasos_restantes)
        for _ in range(pasos_este_cuadro):
            avanzar_paso()
        pasos_restantes -= pasos_este_cuadro
        es_final = (pasos_restantes == 0)
        render_frame(mostrar_cursor=not es_final, es_final_finito=es_final)
        if not es_final:
            time.sleep(pausa_seg)
else:
    n_total = int(round(T_total / dt))
    for _ in range(n_total):
        avanzar_paso()
    render_frame(mostrar_cursor=False, es_final_finito=True)

plt.close(fig)
