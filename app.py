import time
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
t_total_actual = float(st.session_state["T_total"])
st.session_state["t_inicio"] = float(min(st.session_state["t_inicio"], t_total_actual - 0.5))
st.session_state["t_fin"] = float(min(st.session_state["t_fin"], t_total_actual))

col_t1, col_t2 = st.sidebar.columns(2)
t_inicio = col_t1.number_input(
    "t inicio [s]",
    min_value=0.0,
    max_value=t_total_actual - 0.5,
    step=0.5,
    key="t_inicio"
)
t_fin = col_t2.number_input(
    "t fin [s]",
    min_value=0.5,
    max_value=t_total_actual,
    step=0.5,
    key="t_fin",
    disabled=es_peralte
)

st.sidebar.subheader("Sintonización PID")
Kp = st.sidebar.number_input("Kp [Nm/m]", min_value=0.0, max_value=20.0, step=0.1, key="Kp")
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
T_total = st.sidebar.number_input(
    "Horizonte temporal T_total [s]",
    min_value=5.0,
    max_value=40.0,
    step=5.0,
    key="T_total"
)

# Opciones de visualización y animación en la barra lateral
st.sidebar.subheader("Visualización y Evolución Temporal")
animar_evolucion = st.sidebar.checkbox("Animar evolución en el tiempo", value=True)
velocidad_anim = st.sidebar.select_slider(
    "Velocidad de evolución:",
    options=["Muy lenta", "Lenta", "Normal", "Rápida"],
    value="Lenta",
    disabled=not animar_evolucion
)
st.sidebar.button("▶️ Reproducir evolución", use_container_width=True)

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
t = np.arange(0, T_total, dt)
n = len(t)

r = np.zeros(n)
y = np.zeros(n)
psi = np.zeros(n)
delta = np.zeros(n)
e = np.zeros(n)
u = np.zeros(n)
perturbacion = np.zeros(n)

t_fin_eff = max(t_fin, t_inicio + 0.1)

if tipo_pert == "Viento lateral (Crosswinds)":
    perturbacion[(t >= t_inicio) & (t <= t_fin_eff)] = amp_pert
elif tipo_pert == "Peralte o pendiente transversal de la calzada":
    perturbacion[t >= t_inicio] = amp_pert
elif tipo_pert == "Irregularidades del asfalto":
    mask = (t >= t_inicio) & (t <= t_fin_eff)
    tm = t[mask] - t_inicio
    rng = np.random.default_rng(42)
    perfil_baches = (
        0.65
        + 0.50 * np.sin(2.0 * np.pi * 1.6 * tm)
        + 0.35 * np.sin(2.0 * np.pi * 4.2 * tm)
        + 0.25 * rng.normal(0.0, 1.0, size=mask.sum())
    )
    perturbacion[mask] = amp_pert * perfil_baches
elif tipo_pert == "Intervención del conductor":
    mask = (t >= t_inicio) & (t <= t_fin_eff)
    tm = t[mask] - t_inicio
    dur = t_fin_eff - t_inicio
    perturbacion[mask] = amp_pert * 1.25 * np.sin(np.pi * tm / dur)

integral_e = 0.0
error_prev = 0.0
delay_steps = int(round(tau_cam / dt))

for k in range(delay_steps, n - 1):
    y_medido = y[k - delay_steps]
    e[k] = r[k] - y_medido
    abs_e = abs(e[k])

    if abs_e <= banda_muerta:
        u_raw = 0.0
        integral_e = 0.0
    else:
        integral_e += e[k] * dt
        derivada_e = (e[k] - error_prev) / dt
        u_raw = Kp * e[k] + Ki * integral_e + Kd * derivada_e

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
    <div class="header-meta"><strong>UTN - FRBA</strong> | Tecnologías de Automatización | Lazo Cerrado PID</div>
</div>
""", unsafe_allow_html=True)

# Contenedores dinámicos para actualizar métricas y gráficas paso a paso
metrics_placeholder = st.empty()
plot_placeholder = st.empty()


def render_metrics(idx_end: int):
    y_seg = y[:idx_end]
    e_seg = e[:idx_end]
    u_seg = u[:idx_end]
    t_actual = t[idx_end - 1]

    desvio_max = float(np.max(np.abs(y_seg)))
    ess_actual = float(np.abs(e_seg[-1]))
    torque_pico = float(np.max(np.abs(u_seg)))
    en_carril = desvio_max < 0.30

    if len(y_seg) > 1:
        variacion_final = float(np.max(np.abs(np.diff(y_seg[-min(50, len(y_seg)):]))))
    else:
        variacion_final = float("inf")

    if idx_end == n and variacion_final < 0.0005:
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


# --- CONFIGURACIÓN BASE DE GRÁFICAS (ejes fijos para evolución suave) ---
fig, axs = plt.subplots(3, 1, figsize=(11, alto_fig), sharex=True)

y_lim = max(0.36, float(np.max(np.abs(y))) * 1.15)
e_lim = max(0.15, float(np.max(np.abs(e))) * 1.15)
u_lim = max(0.6, float(np.max(np.abs(np.concatenate([u, perturbacion])))) * 1.15)

# 1. Posición Lateral
(line_y,) = axs[0].plot([], [], label=r'Posición real $\theta_o(t)$ [m]', color='#1f77b4', linewidth=1.7)
(dot_y,) = axs[0].plot([], [], 'o', color='#1f77b4', markersize=5)
axs[0].plot(t, r, '--', label=r'Referencia $\theta_i(t) = 0$ m', color='black', linewidth=1.0)
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

# Referencias visuales y marcas en el eje X para t_inicio y t_fin
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
base_ticks = list(np.arange(0.0, T_total + 1e-9, tick_step))
min_gap = T_total * 0.035
valid_refs = [float(rv) for rv in refs_tiempo if 0.0 <= rv <= T_total]
x_ticks = [bt for bt in base_ticks if all(abs(bt - rv) >= min_gap for rv in valid_refs)]
for rv in valid_refs:
    if all(abs(rv - tv) >= 1e-6 for tv in x_ticks):
        x_ticks.append(rv)
x_ticks.sort()
axs[2].set_xticks(x_ticks)
axs[2].set_xticklabels([f"{tv:g}" for tv in x_ticks])

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


def render_frame(idx_end: int, mostrar_cursor: bool):
    t_seg = t[:idx_end]
    line_y.set_data(t_seg, y[:idx_end])
    line_e.set_data(t_seg, e[:idx_end])
    line_u.set_data(t_seg, u[:idx_end])
    line_p.set_data(t_seg, perturbacion[:idx_end])

    if mostrar_cursor:
        t_cur = t[idx_end - 1]
        dot_y.set_data([t_cur], [y[idx_end - 1]])
        dot_e.set_data([t_cur], [e[idx_end - 1]])
        dot_u.set_data([t_cur], [u[idx_end - 1]])
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

    render_metrics(idx_end)
    try:
        plot_placeholder.pyplot(fig, width="stretch")
    except TypeError:
        plot_placeholder.pyplot(fig, use_container_width=True)


if animar_evolucion:
    config_vel = {
        "Muy lenta": (50, 0.18),
        "Lenta": (40, 0.10),
        "Normal": (28, 0.04),
        "Rápida": (20, 0.01),
    }
    num_frames, pausa_seg = config_vel[velocidad_anim]
    paso_muestras = max(1, n // num_frames)
    frames = list(range(paso_muestras, n, paso_muestras))
    if not frames or frames[-1] != n:
        frames.append(n)

    for idx in frames:
        es_final = (idx == n)
        render_frame(idx, mostrar_cursor=not es_final)
        if not es_final:
            time.sleep(pausa_seg)
else:
    render_frame(n, mostrar_cursor=False)

plt.close(fig)
