"""Seguimiento de presupuestos por WhatsApp · Top Redes Valencia.

Flujo: cargas el listado -> la app te va mostrando cliente a cliente con el mensaje ya redactado ->
abres WhatsApp con un clic -> pulsas «Enviado» (o «Aprobó» / «No interesado») -> pasa al siguiente.
Al final descargas el listado actualizado.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

import logica as L

st.set_page_config(page_title="Seguimiento por WhatsApp · Top Redes", page_icon="🐾", layout="wide")


# ----------------------------------------------------------------------------- contraseña (opcional)
def _acceso_ok() -> bool:
    try:
        clave = st.secrets.get("APP_PASSWORD", "")
    except Exception:
        clave = ""
    if not clave or st.session_state.get("acceso"):
        return True
    st.title("🐾 Seguimiento por WhatsApp")
    entrada = st.text_input("Contraseña", type="password")
    if entrada and entrada == clave:
        st.session_state["acceso"] = True
        st.rerun()
    elif entrada:
        st.error("Contraseña incorrecta")
    return False


if not _acceso_ok():
    st.stop()


def _secreto(nombre: str) -> str:
    try:
        return str(st.secrets.get(nombre, ""))
    except Exception:
        return ""


# ----------------------------------------------------------------------------- estado de sesión
ss = st.session_state
ss.setdefault("df", None)
ss.setdefault("origen", "")
ss.setdefault("pos", 0)
ss.setdefault("envios_api", 0)


def _cargar(archivo) -> None:
    if archivo.name.lower().endswith(".csv"):
        crudo = pd.read_csv(archivo, dtype={"Teléfono": str}, sep=None, engine="python")
    else:
        crudo = pd.read_excel(archivo, sheet_name=0, dtype={"Teléfono": str})
    ss.df = L.preparar(crudo)
    ss.origen = f"{archivo.name}-{archivo.size}"
    ss.pos = 0


def _usar_ejemplo() -> None:
    ss.df = L.datos_ejemplo()
    ss.origen = "ejemplo"
    ss.pos = 0


# ----------------------------------------------------------------------------- barra lateral
with st.sidebar:
    st.header("🐾 Configuración")
    firmante = st.text_input("Quién firma los mensajes", value="Raúl", key="firmante")
    empresa = st.text_input("Empresa", value="Top Redes Valencia", key="empresa")
    agenda = st.text_input("Cuándo tienes hueco (para proponer)", value="esta semana o la próxima", key="agenda")
    st.divider()
    archivo = st.file_uploader("Listado de seguimiento (.xlsx o .csv)", type=["xlsx", "csv"])
    if archivo is not None and ss.origen != f"{archivo.name}-{archivo.size}":
        _cargar(archivo)
    st.button("Probar con datos de ejemplo", on_click=_usar_ejemplo, width="stretch")
    st.divider()
    token, phone_id = _secreto("WHATSAPP_TOKEN"), _secreto("WHATSAPP_PHONE_ID")
    modos = ["Enlace de WhatsApp (recomendado)"]
    if token and phone_id:
        modos.append("API de WhatsApp Cloud (avanzado)")
    modo = st.radio("Modo de envío", modos, key="modo")
    st.caption(
        "Con el enlace, cada mensaje se abre en tu WhatsApp ya escrito y tú pulsas enviar: "
        "no necesita cuenta de empresa ni plantillas aprobadas."
    )
    st.caption("⚠️ En Streamlit Cloud los datos no se guardan entre sesiones: descarga el listado al terminar.")

cfg = {"firmante": firmante, "empresa": empresa, "agenda": agenda}

st.title("🐾 Seguimiento de presupuestos por WhatsApp")

if ss.df is None:
    st.info("Carga el listado de seguimiento en la barra lateral, o pulsa «Probar con datos de ejemplo».")
    st.stop()


# ----------------------------------------------------------------------------- filtros
c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
estados = c1.multiselect("Estados", L.ESTADOS, default=L.ABIERTOS, key="f_estados")
dmax = max(60, int(ss.df["Días"].max() or 0))
dias_rango = c2.slider("Días desde el presupuesto", 0, dmax, (0, dmax), key="f_dias")
texto = c3.text_input("Buscar (nombre, teléfono, población)", key="f_texto")
sin_contactar = c4.checkbox("Solo los no contactados", key="f_sin")
zonas_todas = sorted(z for z in ss.df["Zona"].unique() if z)
zonas = st.multiselect("Zona", zonas_todas, default=zonas_todas, key="f_zonas") if zonas_todas else []


def _vista() -> pd.DataFrame:
    return L.filtrar(
        ss.df, ss.get("f_estados", L.ABIERTOS), ss.get("f_dias", (0, 9999))[0], ss.get("f_dias", (0, 9999))[1],
        ss.get("f_texto", ""), ss.get("f_sin", False), ss.get("f_zonas") or None,
    )


# ----------------------------------------------------------------------------- acciones
def _avanzar(idx: int) -> None:
    idxs = list(_vista().index)
    ss.pos = idxs.index(idx) + 1 if idx in idxs else min(ss.pos, max(len(idxs) - 1, 0))


def _enviado(idx: int) -> None:
    ss.df = L.marcar_enviado(ss.df, idx)
    _avanzar(idx)


def _estado(idx: int, estado: str, nota: str) -> None:
    ss.df = L.cambiar_estado(ss.df, idx, estado, nota)
    _avanzar(idx)


def _saltar(idx: int) -> None:
    _avanzar(idx)


def _anterior() -> None:
    ss.pos = max(ss.pos - 1, 0)


def _guardar_nota(idx: int) -> None:
    ss.df.loc[idx, "Nota"] = ss.get(f"nota_{idx}", "")


tab_cola, tab_lista, tab_res = st.tabs(["📲 Cola de envío", "📋 Listado y estados", "📊 Resumen"])

# ----------------------------------------------------------------------------- COLA DE ENVÍO
with tab_cola:
    vista = _vista()
    idxs = list(vista.index)
    if not idxs:
        st.success("No hay clientes con estos filtros. ¡Todo al día! 🎉")
    else:
        ss.pos = min(max(ss.pos, 0), len(idxs) - 1)
        idx = idxs[ss.pos]
        fila = ss.df.loc[idx].to_dict()
        st.progress((ss.pos + 1) / len(idxs), text=f"Cliente {ss.pos + 1} de {len(idxs)}")

        izq, der = st.columns([2, 3])
        with izq:
            st.subheader(fila["Cliente"])
            st.write(f"📞 **{L.telefono_legible(fila['Teléfono'])}**")
            st.write(f"📍 {fila['Población'] or '—'}")
            imp = L._eur(fila["Importe sin IVA (€)"])
            st.write(f"💶 {imp} + IVA ({L._eur(fila['Importe con IVA (€)'])} con IVA)")
            if fila["Opciones"]:
                st.write(f"🔀 Varias opciones: {fila['Opciones']}")
            st.write(f"🗓️ Hace **{fila['Días']} días** · Estado: **{fila['Estado']}**")
            ult = fila["Último contacto"]
            st.write(f"✉️ Mensajes enviados: **{fila['Mensajes enviados']}**"
                     + (f" (último: {pd.Timestamp(ult).strftime('%d/%m')})" if pd.notna(ult) else ""))
            st.text_input("Nota", value=fila["Nota"], key=f"nota_{idx}", on_change=_guardar_nota, args=(idx,))

        with der:
            sugerida = L.plantilla_automatica(fila)
            nombres = list(L.PLANTILLAS)
            plantilla = st.selectbox("Plantilla", nombres, index=nombres.index(sugerida), key=f"tpl_{idx}",
                                     help=f"Sugerida según los días y los mensajes ya enviados: {sugerida}")
            cfg_cliente = dict(cfg)
            if plantilla == "Confirmar fecha":
                cfg_cliente["fecha_instalacion"] = st.text_input(
                    "Fecha acordada (ej.: «el jueves 12 por la mañana»)", key=f"fecha_{idx}")
            mensaje = st.text_area("Mensaje (puedes editarlo)", value=L.redactar(plantilla, fila, cfg_cliente),
                                   height=170, key=f"msg_{idx}_{plantilla}_{cfg_cliente.get('fecha_instalacion','')}")
            url = L.enlace_whatsapp(fila["Teléfono"], mensaje)
            if url and modo.startswith("Enlace"):
                st.link_button("📲 Abrir WhatsApp con este mensaje", url, type="primary", width="stretch")
            elif not url:
                st.error("El teléfono no es válido: revísalo en el listado.")

            if modo.startswith("API") and url:
                st.caption("Envío directo con la API de WhatsApp Cloud (experimental).")
                plantilla_meta = st.text_input("Plantilla aprobada en Meta (obligatoria para el primer mensaje)",
                                               value=_secreto("WHATSAPP_TEMPLATE"), key="plantilla_meta")
                confirmar = st.checkbox("Confirmo que este cliente ha pedido el presupuesto y quiero escribirle",
                                        key=f"conf_{idx}")
                if st.button("🚀 Enviar por API", disabled=not confirmar or ss.envios_api >= 25):
                    if plantilla_meta:
                        ok, detalle = L.enviar_api_plantilla(
                            fila["Teléfono"], plantilla_meta,
                            [L.primer_nombre(fila["Cliente"]), L._eur(fila["Importe sin IVA (€)"])],
                            token, phone_id)
                    else:
                        ok, detalle = L.enviar_api_texto(fila["Teléfono"], mensaje, token, phone_id)
                    if ok:
                        ss.envios_api += 1
                        ss.df = L.marcar_enviado(ss.df, idx)
                        st.success("Enviado ✅")
                    else:
                        st.error(f"No se pudo enviar: {detalle}")
                st.caption(f"Envíos por API en esta sesión: {ss.envios_api}/25")

        b1, b2, b3, b4, b5 = st.columns(5)
        b1.button("◀ Anterior", on_click=_anterior, width="stretch", disabled=ss.pos == 0)
        b2.button("✅ Enviado", on_click=_enviado, args=(idx,), type="primary", width="stretch")
        b3.button("👍 Aprobó", on_click=_estado, args=(idx, "Aprobado pendiente", "Aprobó por WhatsApp"),
                  width="stretch")
        b4.button("👎 No interesado", on_click=_estado, args=(idx, "No aprobado", "No interesado"),
                  width="stretch")
        b5.button("⏭ Saltar", on_click=_saltar, args=(idx,), width="stretch")

        with st.expander("🔒 Cerrar el presupuesto (cuando el cliente responde)"):
            st.write("Pulsa **Aprobó** cuando diga que sí: pasa a «Aprobado pendiente» y puedes enviarle la "
                     "confirmación de fecha eligiendo la plantilla **Confirmar fecha**. Cuando hagas la "
                     "instalación, márcalo como ejecutado:")
            e1, e2 = st.columns(2)
            e1.button("🛠️ Marcar como ejecutado", on_click=_estado, args=(idx, "Ejecutado", "Instalado"),
                      key=f"ej_{idx}", width="stretch")
            e2.button("↩️ Volver a pendiente", on_click=_estado, args=(idx, "Pendiente", "Reabierto"),
                      key=f"pe_{idx}", width="stretch")

# ----------------------------------------------------------------------------- LISTADO
with tab_lista:
    vista = _vista()
    st.caption(f"{len(vista)} clientes con los filtros actuales. Puedes cambiar el estado y la nota directamente.")
    cols = ["Cliente", "Teléfono", "Población", "Importe sin IVA (€)", "Días", "Estado", "Mensajes enviados",
            "Último contacto", "Nota"]
    editado = st.data_editor(
        vista[cols], key="editor", width="stretch", hide_index=False,
        disabled=[c for c in cols if c not in ("Estado", "Nota")],
        column_config={
            "Estado": st.column_config.SelectboxColumn("Estado", options=L.ESTADOS, required=True),
            "Importe sin IVA (€)": st.column_config.NumberColumn(format="%.0f €"),
            "Último contacto": st.column_config.DateColumn(format="DD/MM"),
        },
    )
    cambios = (editado["Estado"] != vista["Estado"]) | (editado["Nota"].fillna("") != vista["Nota"].fillna(""))
    if cambios.any():
        ss.df.loc[editado.index[cambios], "Estado"] = editado.loc[cambios, "Estado"]
        ss.df.loc[editado.index[cambios], "Nota"] = editado.loc[cambios, "Nota"].fillna("")
        st.rerun()

    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Descargar listado actualizado (.xlsx)", L.a_excel_bytes(ss.df),
                       file_name=f"seguimiento-{date.today().strftime('%Y%m%d')}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       width="stretch")
    d2.download_button("⬇️ Descargar en CSV", ss.df[L.COLUMNAS].to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"seguimiento-{date.today().strftime('%Y%m%d')}.csv", mime="text/csv",
                       width="stretch")

# ----------------------------------------------------------------------------- RESUMEN
with tab_res:
    df = ss.df
    abiertos = df[df["Estado"].isin(["Sin marcar", "Pendiente"])]
    aprob = df[df["Estado"] == "Aprobado pendiente"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Por cerrar", len(abiertos), L._eur(abiertos["Importe sin IVA (€)"].sum()))
    m2.metric("Aprobados por agendar", len(aprob), L._eur(aprob["Importe sin IVA (€)"].sum()))
    m3.metric("Mensajes enviados", int(df["Mensajes enviados"].sum()))
    decididos = df["Estado"].isin(["Ejecutado", "Aprobado pendiente", "No aprobado"]).sum()
    ganados = df["Estado"].isin(["Ejecutado", "Aprobado pendiente"]).sum()
    m4.metric("Conversión", f"{ganados / decididos:.0%}" if decididos else "—")
    resumen = (df.groupby("Estado").agg(Clientes=("Cliente", "count"), Importe=("Importe sin IVA (€)", "sum"))
                 .reindex(L.ESTADOS).fillna(0))
    st.bar_chart(resumen["Clientes"])
    st.dataframe(resumen.style.format({"Clientes": "{:.0f}", "Importe": "{:,.0f} €"}), width="stretch")
