import time
from collections import deque
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_DISPONIBLE = True
except ImportError:
    PLOTLY_DISPONIBLE = False

# Configuración de página
st.set_page_config(
    page_title="Simulador Lane Assist - VW Golf VII",
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
    margin-bottom: 6px;
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

/* Barra de Flags (Hitos de régimen estable y cruce por cero) */
.flags-bar {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    margin-bottom: 8px;
}
.flag-pill {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 0.80rem;
    font-weight: 600;
    border: 1px solid #cbd5e1;
    background-color: #f8fafc;
    color: #334155 !important;
}
.flag-pill.flag-ok-ss {
    background-color: #dcfce7;
    border-color: #86efac;
    color: #14532d !important;
}
.flag-pill.flag-ok-zero {
    background-color: #e0f2fe;
    border-color: #7dd3fc;
    color: #0c4a6e !important;
}
.flag-badge {
    font-weight: 800;
    color: #000000 !important;
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
dt = 0.01             # Paso de integración: 10 ms
MAX_SAMPLES = 180_000  # Límite de seguridad (~30 min de tiempo simulado)

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
    "Kp1": 0.0,
    "Kp2": 1.8,
    "Kp3": 2.6,
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

if "sim_running" not in st.session_state:
    st.session_state["sim_running"] = True


def crear_estado_simulacion() -> dict:
    delay_steps = int(round(tau_cam / dt))
    return {
        "k_step": 0,
        "y_k": 0.0,
        "psi_k": 0.0,
        "delta_k": 0.0,
        "integral_e": 0.0,
        "error_prev": 0.0,
        "desvio_max": 0.0,
        "torque_pico": 0.0,
        "y_delay_buf": deque([0.0] * (delay_steps + 1), maxlen=delay_steps + 1),
        "rng_asfalto": np.random.default_rng(42),
        "t": [],
        "y": [],
        "e": [],
        "u": [],
        "p": [],
        "hubo_desvio": False,
        "flag_ss_t": None,
        "flag_ss_err": None,
        "flag_zero_t": None,
    }


def reiniciar_simulacion(correr: bool = True):
    st.session_state["sim_state"] = crear_estado_simulacion()
    st.session_state["sim_running"] = correr
    st.session_state.pop("ventana_inicio_slider", None)


def pausar_simulacion():
    st.session_state["sim_running"] = False
    sim = st.session_state.get("sim_state")
    if sim and sim["t"]:
        t_max = sim["t"][-1]
        t_win = float(st.session_state.get("T_total", 10.0))
        st.session_state["ventana_inicio_slider"] = max(0.0, round(t_max - t_win, 2))


def reanudar_simulacion():
    st.session_state["sim_running"] = True


def restaurar_caso_1():
    for k, v in VALORES_CASO_1.items():
        st.session_state[k] = v
    reiniciar_simulacion(correr=True)


# Callbacks para sincronizar slider y number_input de perturbación
def sync_num_to_slider():
    st.session_state["slider_pert"] = float(np.clip(st.session_state["amp_pert"], -1.5, 1.5))


def sync_slider_to_num():
    st.session_state["amp_pert"] = st.session_state["slider_pert"]


# --- BARRA LATERAL: TABLERO DE CONTROL ---
st.sidebar.markdown("### Escenarios de Ensayo")
st.sidebar.button(
    "Restaurar Caso 1 (Nominal)",
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
    st.sidebar.warning("Velocidad < 65 km/h: En el vehículo real (SSP 516), el sistema pasa a estado PASIVO.")

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

# Opciones de visualización y control de reproducción en la barra lateral
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

col_btn1, col_btn2 = st.sidebar.columns(2)
col_btn1.button("Reanudar", on_click=reanudar_simulacion, use_container_width=True)
col_btn2.button("Frenar", on_click=pausar_simulacion, use_container_width=True)
st.sidebar.button(
    "Reiniciar desde t = 0",
    on_click=lambda: reiniciar_simulacion(correr=True),
    use_container_width=True
)

tamano_graf = st.sidebar.radio(
    "Escala de gráficas:",
    ["Ajustar a pantalla (Compacta)", "Mediana", "Ampliada"],
    index=0
)
if tamano_graf == "Ajustar a pantalla (Compacta)":
    alto_fig = 3.55
elif tamano_graf == "Mediana":
    alto_fig = 4.6
else:
    alto_fig = 6.6

pos_leyenda = st.sidebar.selectbox(
    "Ubicación de referencias (leyendas):",
    ["Exterior derecha (no tapa gráficos)", "Superior", "Ocultar"],
    index=0
)

# --- DETECCIÓN DE CAMBIO DE PARÁMETROS FÍSICOS ---
firma_params = (
    vx_kmh, tipo_pert, amp_pert, t_inicio, t_fin,
    Kp1, Kp2, Kp3, Ki, Kd, banda_muerta, simulacion_infinita
)
if "firma_params" not in st.session_state:
    st.session_state["firma_params"] = firma_params
    if "sim_state" not in st.session_state:
        st.session_state["sim_state"] = crear_estado_simulacion()
elif st.session_state["firma_params"] != firma_params:
    st.session_state["firma_params"] = firma_params
    reiniciar_simulacion(correr=True)

if "sim_state" not in st.session_state:
    st.session_state["sim_state"] = crear_estado_simulacion()

sim = st.session_state["sim_state"]
delay_steps = int(round(tau_cam / dt))
t_fin_eff = max(t_fin, t_inicio + 0.1)
dur_pert = t_fin_eff - t_inicio
t_min_ss = (t_inicio + 0.5) if es_peralte else (t_fin_eff + 0.5)


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
                + 0.25 * float(sim["rng_asfalto"].normal(0.0, 1.0))
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
    if len(sim["t"]) >= MAX_SAMPLES:
        return

    k_step = sim["k_step"]
    t_k = k_step * dt
    p_k = calcular_perturbacion(t_k)

    y_k = sim["y_k"]
    psi_k = sim["psi_k"]
    delta_k = sim["delta_k"]

    if k_step < delay_steps:
        e_k = 0.0
        u_k = 0.0
    else:
        y_medido = sim["y_delay_buf"][0]
        e_k = 0.0 - y_medido  # Referencia r(t) = 0.0 m

        if abs(e_k) <= banda_muerta:
            Kp = Kp1
        elif abs(e_k) <= 0.15:
            Kp = Kp2
        else:
            Kp = Kp3

        sim["integral_e"] += e_k * dt
        derivada_e = (e_k - sim["error_prev"]) / dt
        u_raw = Kp * e_k + Ki * sim["integral_e"] + Kd * derivada_e

        u_k = float(np.clip(u_raw, -torque_max, torque_max))
        sim["error_prev"] = e_k

    # Detección de hito: desvío real por la perturbación y primer alcance/cruce por 0
    if t_k >= t_inicio and abs(y_k) >= 0.005:
        sim["hubo_desvio"] = True

    if sim["hubo_desvio"] and sim["flag_zero_t"] is None:
        e_anterior = sim["e"][-1] if sim["e"] else e_k
        cruzo_cero = (e_anterior * e_k <= 0.0) and (abs(e_anterior) > 0.001)
        if abs(e_k) <= 0.001 or cruzo_cero:
            sim["flag_zero_t"] = t_k

    sim["t"].append(t_k)
    sim["y"].append(y_k)
    sim["e"].append(e_k)
    sim["u"].append(u_k)
    sim["p"].append(p_k)

    sim["desvio_max"] = max(sim["desvio_max"], abs(y_k))
    sim["torque_pico"] = max(sim["torque_pico"], abs(u_k))

    # Detección de flag de Estado Estable (ess) tras la perturbación
    if sim["flag_ss_t"] is None and t_k >= t_min_ss and len(sim["y"]) >= 50:
        y_rec = sim["y"][-50:]
        var_paso = float(np.max(np.abs(np.diff(y_rec))))
        rango_rec = max(y_rec) - min(y_rec)
        if var_paso < 0.0005 and rango_rec < 0.003:
            sim["flag_ss_t"] = t_k
            sim["flag_ss_err"] = abs(e_k)

    # Integración por Euler hacia k + 1
    d_delta = ((u_k * 0.035) - delta_k) / tau_act
    delta_next = delta_k + d_delta * dt

    d_psi = (vx / L_wb) * delta_k
    psi_next = psi_k + d_psi * dt

    dy = vx * psi_k + p_k * dt * 10.0
    y_next = y_k + dy * dt

    sim["y_k"] = y_next
    sim["psi_k"] = psi_next
    sim["delta_k"] = delta_next
    sim["y_delay_buf"].append(y_next)
    sim["k_step"] = k_step + 1


# --- ENCABEZADO PRINCIPAL COMPACTO ---
st.markdown("""
<div class="header-container">
    <div class="header-title">Simulador de Control: Lane Assist (VW Golf VII)</div>
    <div class="header-meta"><strong>UTN - FRBA</strong> | Tecnologías de Automatización | Lazo Cerrado PID</div>
</div>
""", unsafe_allow_html=True)

# Contenedores dinámicos (Métricas -> Flags de régimen -> Gráficas -> Navegador temporal al pausar)
metrics_placeholder = st.empty()
flags_placeholder = st.empty()
plot_placeholder = st.empty()


def render_metrics_and_flags(idx_fin: int, es_final_finito: bool = False):
    t_actual = sim["t"][idx_fin - 1]
    ess_actual = abs(sim["e"][idx_fin - 1])
    desvio_max = sim["desvio_max"]
    torque_pico = sim["torque_pico"]
    en_carril = desvio_max < 0.30

    titulo_error = "Error Instantáneo e(t)"
    delta_error = f"t = {t_actual:.1f} s | Ref: 0.00 m"

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

    # Barra de Flags (Estado Estable y Alcance del 0)
    if sim["flag_ss_t"] is not None:
        ss_class = "flag-pill flag-ok-ss"
        ss_texto = (
            f"<span><strong>Flag Estado Estable (e<sub>ss</sub>):</strong> Alcanzado</span>"
            f"<span class='flag-badge'>Instante t = {sim['flag_ss_t']:.2f} s</span>"
        )
    else:
        ss_class = "flag-pill"
        ss_texto = (
            f"<span><strong>Flag Estado Estable (e<sub>ss</sub>):</strong> En transitorio</span>"
            f"<span class='flag-badge'>Aún no estabilizado</span>"
        )

    if sim["flag_zero_t"] is not None:
        zero_class = "flag-pill flag-ok-zero"
        zero_texto = (
            f"<span><strong>Flag Error en Cero (e = 0):</strong> Logrado</span>"
            f"<span class='flag-badge'>Instante t = {sim['flag_zero_t']:.2f} s</span>"
        )
    else:
        zero_class = "flag-pill"
        zero_texto = (
            f"<span><strong>Flag Error en Cero (e = 0):</strong> Pendiente</span>"
            f"<span class='flag-badge'>Esperando retorno a 0</span>"
        )

    flags_placeholder.markdown(
        f"""
        <div class="flags-bar">
            <div class="{ss_class}">{ss_texto}</div>
            <div class="{zero_class}">{zero_texto}</div>
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

# Líneas de referencia para Flags (Estado Estable y Error = 0) en los 3 gráficos
flag_ss_lines = [ax.axvline(0.0, color='#16a34a', linestyle='--', linewidth=1.1, alpha=0.8, visible=False) for ax in axs]
flag_zero_lines = [ax.axvline(0.0, color='#0284c7', linestyle='--', linewidth=1.1, alpha=0.8, visible=False) for ax in axs]
flag_ss_lines[1].set_label("Flag Estado Estable")
flag_zero_lines[1].set_label("Flag Error = 0")

# Referencias visuales para t_inicio y t_fin
refs_tiempo = [t_inicio] if es_peralte else [t_inicio, t_fin]
for ax in axs:
    ax.axvline(t_inicio, color='#ff7f0e', linestyle=':', linewidth=0.9, alpha=0.55)
    if not es_peralte:
        ax.axvline(t_fin, color='#ff7f0e', linestyle=':', linewidth=0.9, alpha=0.55)


def actualizar_xticks(x_min: float, x_max: float, paso_forzado: float | None = None):
    span = max(0.1, x_max - x_min)
    if paso_forzado is not None and paso_forzado > 0:
        tick_step = paso_forzado
    elif span <= 1.0:
        tick_step = 0.1
    elif span <= 2.5:
        tick_step = 0.25
    elif span <= 5.0:
        tick_step = 0.5
    elif span <= 10.0:
        tick_step = 1.0
    elif span <= 20.0:
        tick_step = 2.0
    elif span <= 50.0:
        tick_step = 5.0
    else:
        tick_step = 10.0

    inicio_tick = np.ceil(x_min / tick_step) * tick_step
    base_ticks = list(np.arange(inicio_tick, x_max + 1e-9, tick_step))
    min_gap = span * 0.035

    refs_dinamicas = list(refs_tiempo)
    if sim["flag_ss_t"] is not None:
        refs_dinamicas.append(sim["flag_ss_t"])
    if sim["flag_zero_t"] is not None:
        refs_dinamicas.append(sim["flag_zero_t"])

    valid_refs = [float(rv) for rv in refs_dinamicas if x_min <= rv <= x_max]
    x_ticks = [bt for bt in base_ticks if all(abs(bt - rv) >= min_gap for rv in valid_refs)]
    for rv in valid_refs:
        if all(abs(rv - tv) >= min_gap * 0.6 for tv in x_ticks):
            x_ticks.append(rv)
    x_ticks.sort()
    axs[2].set_xticks(x_ticks)
    axs[2].set_xticklabels([f"{tv:.2f}".rstrip('0').rstrip('.') for tv in x_ticks])


actualizar_xticks(0.0, T_total)

# Configuración de referencias (leyendas) para no tapar los datos
if pos_leyenda == "Exterior derecha (no tapa gráficos)":
    axs[0].legend(loc='center left', bbox_to_anchor=(1.01, 0.5), fontsize=7.2, frameon=True, facecolor='#fafafa', edgecolor='#dddddd')
    axs[1].legend(loc='center left', bbox_to_anchor=(1.01, 0.5), fontsize=7.2, frameon=True, facecolor='#fafafa', edgecolor='#dddddd')
    axs[2].legend(loc='center left', bbox_to_anchor=(1.01, 0.5), fontsize=7.2, frameon=True, facecolor='#fafafa', edgecolor='#dddddd')
    plt.subplots_adjust(left=0.07, right=0.73, top=0.96, bottom=0.11, hspace=0.18)
elif pos_leyenda == "Superior":
    axs[0].legend(loc='lower left', bbox_to_anchor=(0.0, 1.02), ncol=3, fontsize=6.8, frameon=False)
    axs[1].legend(loc='lower left', bbox_to_anchor=(0.0, 1.02), ncol=3, fontsize=6.8, frameon=False)
    axs[2].legend(loc='lower left', bbox_to_anchor=(0.0, 1.02), ncol=2, fontsize=6.8, frameon=False)
    plt.subplots_adjust(left=0.07, right=0.98, top=0.92, bottom=0.11, hspace=0.28)
else:
    plt.subplots_adjust(left=0.07, right=0.98, top=0.96, bottom=0.11, hspace=0.18)


def render_frame(
    x_min: float,
    x_max: float,
    mostrar_cursor: bool,
    es_final_finito: bool = False,
    paso_xticks: float | None = None
):
    global y_lim, e_lim, u_lim

    n_hist = len(sim["t"])
    if n_hist == 0:
        return

    i_ini = max(0, int(np.floor(x_min / dt)) - 1)
    i_fin = min(n_hist, int(np.ceil(x_max / dt)) + 2)

    t_arr = sim["t"][i_ini:i_fin]
    y_arr = sim["y"][i_ini:i_fin]
    e_arr = sim["e"][i_ini:i_fin]
    u_arr = sim["u"][i_ini:i_fin]
    p_arr = sim["p"][i_ini:i_fin]

    line_y.set_data(t_arr, y_arr)
    line_e.set_data(t_arr, e_arr)
    line_u.set_data(t_arr, u_arr)
    line_p.set_data(t_arr, p_arr)

    axs[0].set_xlim(x_min, x_max)
    actualizar_xticks(x_min, x_max, paso_forzado=paso_xticks)

    # Mostrar líneas verticales de flags si ya ocurrieron
    if sim["flag_ss_t"] is not None:
        for ln in flag_ss_lines:
            ln.set_xdata([sim["flag_ss_t"], sim["flag_ss_t"]])
            ln.set_visible(x_min <= sim["flag_ss_t"] <= x_max)
    if sim["flag_zero_t"] is not None:
        for ln in flag_zero_lines:
            ln.set_xdata([sim["flag_zero_t"], sim["flag_zero_t"]])
            ln.set_visible(x_min <= sim["flag_zero_t"] <= x_max)

    # Ampliar dinámicamente los límites verticales si algún pico supera la escala actual
    if y_arr:
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

    if mostrar_cursor and t_arr:
        t_cur = sim["t"][-1]
        dot_y.set_data([t_cur], [sim["y"][-1]])
        dot_e.set_data([t_cur], [sim["e"][-1]])
        dot_u.set_data([t_cur], [sim["u"][-1]])
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

    render_metrics_and_flags(idx_fin=n_hist, es_final_finito=es_final_finito)
    try:
        plot_placeholder.pyplot(fig, width="stretch")
    except TypeError:
        plot_placeholder.pyplot(fig, use_container_width=True)


def render_plotly_interactivo(x_min: float, x_max: float, es_final_finito: bool = False):
    if not PLOTLY_DISPONIBLE:
        render_frame(x_min, x_max, mostrar_cursor=False, es_final_finito=es_final_finito)
        return

    n_hist = len(sim["t"])
    if n_hist == 0:
        return

    t_all = sim["t"]
    y_all = sim["y"]
    e_all = sim["e"]
    u_all = sim["u"]
    p_all = sim["p"]

    altura_px = 420 if tamano_graf == "Ajustar a pantalla (Compacta)" else (540 if tamano_graf == "Mediana" else 720)

    fig_p = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06
    )

    # 1. Posición Lateral
    fig_p.add_hrect(
        y0=-banda_muerta, y1=banda_muerta,
        fillcolor="rgba(34, 197, 94, 0.14)", line_width=0, row=1, col=1
    )
    fig_p.add_hline(y=0.0, line_dash="dash", line_color="black", line_width=1, row=1, col=1)
    fig_p.add_hline(y=0.30, line_dash="dot", line_color="red", line_width=1.2, row=1, col=1)
    fig_p.add_hline(y=-0.30, line_dash="dot", line_color="red", line_width=1.2, row=1, col=1)
    fig_p.add_trace(
        go.Scatter(x=t_all, y=y_all, name="Posición real θo(t) [m]", line=dict(color="#1f77b4", width=2)),
        row=1, col=1
    )

    # 2. Señal de Error
    fig_p.add_trace(
        go.Scatter(x=t_all, y=e_all, name="Error e(t) [m]", line=dict(color="#d62728", width=1.8)),
        row=2, col=1
    )

    # 3. Torque Corrector y Perturbación
    fig_p.add_trace(
        go.Scatter(x=t_all, y=u_all, name="Torque EPS u(t) [Nm]", line=dict(color="#9467bd", width=1.8)),
        row=3, col=1
    )
    fig_p.add_trace(
        go.Scatter(x=t_all, y=p_all, name=tipo_pert, line=dict(color="#ff7f0e", width=1.5, dash="dash")),
        row=3, col=1
    )

    # Líneas verticales de referencia (t_inicio, t_fin, flags)
    for row_idx in (1, 2, 3):
        fig_p.add_vline(x=t_inicio, line_dash="dot", line_color="rgba(255,127,14,0.65)", line_width=1, row=row_idx, col=1)
        if not es_peralte:
            fig_p.add_vline(x=t_fin, line_dash="dot", line_color="rgba(255,127,14,0.65)", line_width=1, row=row_idx, col=1)
        if sim["flag_ss_t"] is not None:
            fig_p.add_vline(x=sim["flag_ss_t"], line_dash="dash", line_color="#16a34a", line_width=1.3, row=row_idx, col=1)
        if sim["flag_zero_t"] is not None:
            fig_p.add_vline(x=sim["flag_zero_t"], line_dash="dash", line_color="#0284c7", line_width=1.3, row=row_idx, col=1)

    estilo_eje = dict(
        gridcolor="#cbd5e1",
        griddash="dot",
        showline=True,
        linecolor="#64748b",
        linewidth=1,
        mirror=True,
        tickfont=dict(color="#000000", size=11),
        title_font=dict(color="#000000", size=12),
        zerolinecolor="#94a3b8",
    )

    fig_p.update_yaxes(title_text="Desvío [m]", row=1, col=1, **estilo_eje)
    fig_p.update_yaxes(title_text="Error [m]", row=2, col=1, **estilo_eje)
    fig_p.update_yaxes(title_text="Torque / Pert.", row=3, col=1, **estilo_eje)
    fig_p.update_xaxes(title_text="Tiempo [s]", row=3, col=1, range=[x_min, x_max], **estilo_eje)
    fig_p.update_xaxes(range=[x_min, x_max], row=1, col=1, **estilo_eje)
    fig_p.update_xaxes(range=[x_min, x_max], row=2, col=1, **estilo_eje)

    mostrar_leyenda = (pos_leyenda != "Ocultar")
    leyenda_cfg = (
        dict(
            orientation="h",
            yanchor="bottom",
            y=1.03,
            xanchor="left",
            x=0.0,
            bgcolor="#ffffff",
            bordercolor="#cbd5e1",
            borderwidth=1,
            font=dict(color="#000000", size=11),
        )
        if pos_leyenda == "Superior"
        else dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.015,
            bgcolor="#fafafa",
            bordercolor="#cbd5e1",
            borderwidth=1,
            font=dict(color="#000000", size=11),
        )
    )

    fig_p.update_layout(
        template="plotly_white",
        height=altura_px,
        margin=dict(l=60, r=20 if pos_leyenda != "Exterior derecha (no tapa gráficos)" else 185, t=35, b=45),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(color="#000000", size=11),
        dragmode="pan",
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#ffffff", bordercolor="#64748b", font=dict(color="#000000", size=11)),
        showlegend=mostrar_leyenda,
        legend=leyenda_cfg,
    )

    render_metrics_and_flags(idx_fin=n_hist, es_final_finito=es_final_finito)
    plot_placeholder.plotly_chart(
        fig_p,
        theme=None,
        use_container_width=True,
        config={"scrollZoom": True, "displaylogo": False}
    )


# --- EJECUCIÓN DE LA SIMULACIÓN O NAVEGACIÓN EN PAUSA ---
config_vel = {
    "Muy lenta": (20, 0.18),
    "Lenta": (25, 0.10),
    "Normal": (35, 0.04),
    "Rápida": (50, 0.01),
}
paso_muestras, pausa_seg = config_vel[velocidad_anim]

if simulacion_infinita:
    if st.session_state["sim_running"]:
        st.sidebar.success("Simulando en tiempo real — presione **Frenar** para pausar y recorrer el historial.")
        while len(sim["t"]) < MAX_SAMPLES:
            for _ in range(paso_muestras):
                avanzar_paso()
            t_cur = sim["t"][-1]
            x_min = max(0.0, t_cur - T_total)
            x_max = max(T_total, t_cur)
            render_frame(x_min, x_max, mostrar_cursor=True)
            time.sleep(pausa_seg)
    else:
        st.sidebar.info("Simulación detenida — utilice el deslizador debajo del gráfico para recorrer el historial.")
        if not sim["t"]:
            avanzar_paso()
        t_max = sim["t"][-1]

        # Controles de navegación temporal debajo del gráfico (con zoom por rueda del mouse en el gráfico)
        max_inicio = max(0.0, round(t_max - T_total, 2))

        def ir_a_instante(t_objetivo: float):
            inicio_obj = float(np.clip(t_objetivo - (T_total / 2.0), 0.0, max_inicio))
            st.session_state["ventana_inicio_slider"] = round(inicio_obj, 2)
            st.session_state["ver_todo_chk"] = False

        def on_change_ir_instante():
            ir_a_instante(float(st.session_state["ir_instante_input"]))

        def on_click_ir_ss():
            if sim["flag_ss_t"] is not None:
                st.session_state["ir_instante_input"] = round(float(sim["flag_ss_t"]), 2)
                ir_a_instante(float(sim["flag_ss_t"]))

        col_nav1, col_nav2, col_nav3, col_nav4 = st.columns([3.2, 1.3, 1.3, 1.2])
        ver_todo = col_nav4.checkbox("Ver todo", value=False, key="ver_todo_chk")

        if "ir_instante_input" not in st.session_state:
            st.session_state["ir_instante_input"] = round(
                float(sim["flag_ss_t"]) if sim["flag_ss_t"] is not None else t_max, 2
            )
        else:
            st.session_state["ir_instante_input"] = float(
                np.clip(st.session_state["ir_instante_input"], 0.0, max(0.01, round(t_max, 2)))
            )

        col_nav2.number_input(
            "Ir a instante [s]",
            min_value=0.0,
            max_value=max(0.01, round(t_max, 2)),
            step=0.1,
            format="%.2f",
            key="ir_instante_input",
            on_change=on_change_ir_instante,
            disabled=(t_max <= T_total)
        )

        etiqueta_btn_ss = (
            f"Ir a e_ss ({sim['flag_ss_t']:.2f} s)"
            if sim["flag_ss_t"] is not None
            else "e_ss pendiente"
        )
        col_nav3.markdown("<div style='height: 26px;'></div>", unsafe_allow_html=True)
        col_nav3.button(
            etiqueta_btn_ss,
            on_click=on_click_ir_ss,
            disabled=(sim["flag_ss_t"] is None or t_max <= T_total),
            use_container_width=True
        )

        if ver_todo or t_max <= T_total:
            x_min_vista = 0.0
            x_max_vista = max(T_total, t_max)
            info_ss = (
                f" | Estado Estable en t = {sim['flag_ss_t']:.2f} s"
                if sim["flag_ss_t"] is not None
                else ""
            )
            col_nav1.caption(
                f"Historial conservado: 0.00 s a {t_max:.2f} s{info_ss}. "
                f"Use la rueda del mouse sobre el gráfico para hacer zoom y arrastre para desplazarse (doble clic restablece)."
            )
        else:
            if "ventana_inicio_slider" not in st.session_state:
                st.session_state["ventana_inicio_slider"] = max_inicio
            else:
                st.session_state["ventana_inicio_slider"] = float(
                    np.clip(st.session_state["ventana_inicio_slider"], 0.0, max_inicio)
                )
            label_slider = (
                f"Mover ventana del gráfico [s] — Estado Estable en t = {sim['flag_ss_t']:.2f} s"
                if sim["flag_ss_t"] is not None
                else "Mover ventana del gráfico en el tiempo [s]"
            )
            x_min_vista = col_nav1.slider(
                label_slider,
                min_value=0.0,
                max_value=max_inicio,
                step=0.1,
                key="ventana_inicio_slider"
            )
            x_max_vista = x_min_vista + T_total

        render_plotly_interactivo(x_min_vista, x_max_vista)
else:
    n_total = int(round(T_total / dt))
    if len(sim["t"]) < n_total and (st.session_state["sim_running"] or not animar_evolucion):
        if animar_evolucion:
            while len(sim["t"]) < n_total:
                pasos_este_cuadro = min(paso_muestras, n_total - len(sim["t"]))
                for _ in range(pasos_este_cuadro):
                    avanzar_paso()
                es_final = (len(sim["t"]) >= n_total)
                render_frame(0.0, T_total, mostrar_cursor=not es_final, es_final_finito=es_final)
                if not es_final:
                    time.sleep(pausa_seg)
        else:
            while len(sim["t"]) < n_total:
                avanzar_paso()
            render_frame(0.0, T_total, mostrar_cursor=False, es_final_finito=True)
        st.session_state["sim_running"] = False
    else:
        if not sim["t"]:
            avanzar_paso()
        t_max = sim["t"][-1]
        render_frame(0.0, max(T_total, t_max), mostrar_cursor=False, es_final_finito=(len(sim["t"]) >= n_total))

plt.close(fig)
