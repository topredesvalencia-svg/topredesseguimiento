"""Lógica de la app de seguimiento por WhatsApp (sin Streamlit, para poder probarla)."""
from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import quote

import pandas as pd

ESTADOS = ["Sin marcar", "Pendiente", "Aprobado pendiente", "Ejecutado", "No aprobado"]
ABIERTOS = ["Sin marcar", "Pendiente", "Aprobado pendiente"]

COLUMNAS = ["Teléfono", "Cliente", "Población", "Zona", "Importe sin IVA (€)", "Importe con IVA (€)",
            "Fecha presupuesto", "Días", "Estado", "Nº presupuesto", "Opciones", "Nota",
            "Último contacto", "Mensajes enviados"]


# --------------------------------------------------------------------------- teléfonos
def normalizar_telefono(tel) -> str:
    """Devuelve solo dígitos con prefijo de país, listo para wa.me. '' si no es válido.

    - 9 cifras que empiezan por 6, 7, 8 o 9  -> se añade 34 (España)
    - con '+' o '00' delante -> se respeta el prefijo
    - 10-13 cifras sin '+' -> se asume que ya llevan prefijo
    """
    if tel is None or (isinstance(tel, float) and pd.isna(tel)):
        return ""
    s = str(tel).strip()
    tiene_mas = s.startswith("+")
    d = re.sub(r"\D", "", s)
    if d.startswith("00"):
        d = d[2:]
        tiene_mas = True
    if not d:
        return ""
    if not tiene_mas and len(d) == 9 and d[0] in "6789":
        return "34" + d
    if tiene_mas and 10 <= len(d) <= 15:
        return d
    if not tiene_mas and 10 <= len(d) <= 13:
        return d
    return ""


def telefono_legible(tel) -> str:
    d = normalizar_telefono(tel)
    if d.startswith("34") and len(d) == 11:
        n = d[2:]
        return f"{n[:3]} {n[3:5]} {n[5:7]} {n[7:]}"
    return f"+{d}" if d else str(tel)


def enlace_whatsapp(tel, texto: str) -> str:
    d = normalizar_telefono(tel)
    if not d:
        return ""
    return f"https://wa.me/{d}?text={quote(texto, safe='')}"


# --------------------------------------------------------------------------- plantillas
PLANTILLAS = {
    "Seguimiento": (
        "Hola {nombre}, soy {firmante} de {empresa}. Hace unos días te enviamos {presupuesto_txt} "
        "para tu instalación de red de seguridad. ¿Pudiste echarle un vistazo? Si tienes cualquier "
        "duda o quieres que ajustemos algo, dímelo y lo vemos. ¡Un saludo!"
    ),
    "Recordatorio": (
        "Hola {nombre}, soy {firmante} de {empresa}. Te escribo por {presupuesto_txt}, que sigue "
        "disponible. ¿Te encaja? Si quieres, te reservo fecha {agenda} y queda todo listo. "
        "Quedo pendiente."
    ),
    "Presupuesto caducado": (
        "Hola {nombre}, soy {firmante} de {empresa}. Tu presupuesto de red de seguridad ya ha "
        "pasado su plazo de validez. Si sigues interesado/a, dímelo y te lo actualizo para que "
        "no pierdas la fecha. ¡Gracias!"
    ),
    "Cerrar y agendar": (
        "Hola {nombre}, soy {firmante} de {empresa}. Tenemos hueco {agenda} en {poblacion}. Si te "
        "parece bien, confirmamos {presupuesto_txt} y te reservo ese día. ¿Te va bien?"
    ),
    "Confirmar fecha": (
        "¡Perfecto, {nombre}! Dejamos confirmada la instalación {fecha_instalacion}. Te escribiré "
        "el día antes para ajustar la hora. ¡Gracias por confiar en {empresa}!"
    ),
    "Cierre amistoso": (
        "Hola {nombre}, soy {firmante} de {empresa}. No quiero molestarte: si ya no te interesa el "
        "presupuesto, no pasa nada, dímelo y lo cierro. Y si más adelante te lo planteas, aquí "
        "estamos. ¡Un saludo!"
    ),
}


def primer_nombre(cliente: str) -> str:
    partes = str(cliente or "").strip().split()
    return partes[0].capitalize() if partes else ""


def _eur(v) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    return f"{v:,.0f} €".replace(",", ".") if v == int(v) else f"{v:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def variables(fila: dict, cfg: dict) -> dict:
    opciones = str(fila.get("Opciones") or "").strip()
    imp = fila.get("Importe sin IVA (€)")
    if opciones:
        presupuesto_txt = f"los presupuestos de {opciones} + IVA"
    else:
        presupuesto_txt = f"el presupuesto de {_eur(imp)} + IVA"
    return {
        "nombre": primer_nombre(fila.get("Cliente")),
        "firmante": cfg.get("firmante", "Raúl"),
        "empresa": cfg.get("empresa", "Top Redes Valencia"),
        "poblacion": str(fila.get("Población") or "tu zona").replace("(Valencia)", "").strip() or "tu zona",
        "importe": _eur(imp),
        "importe_iva": _eur(fila.get("Importe con IVA (€)")),
        "presupuesto_txt": presupuesto_txt,
        "dias": int(fila.get("Días") or 0),
        "agenda": cfg.get("agenda", "esta semana o la próxima"),
        "fecha_instalacion": cfg.get("fecha_instalacion") or "en la fecha acordada",
    }


def redactar(plantilla: str, fila: dict, cfg: dict) -> str:
    return PLANTILLAS[plantilla].format(**variables(fila, cfg))


def plantilla_automatica(fila: dict) -> str:
    """Elige la plantilla más adecuada según estado, días y mensajes ya enviados."""
    estado = str(fila.get("Estado") or "Sin marcar")
    dias = int(fila.get("Días") or 0)
    enviados = int(fila.get("Mensajes enviados") or 0)
    if estado == "Aprobado pendiente":
        return "Cerrar y agendar"
    if enviados >= 2:
        return "Cierre amistoso"
    if enviados == 1:
        return "Recordatorio" if dias <= 30 else "Presupuesto caducado"
    if dias > 30:
        return "Presupuesto caducado"
    return "Seguimiento" if dias <= 14 else "Recordatorio"


# --------------------------------------------------------------------------- datos
def preparar(df: pd.DataFrame, hoy: date | None = None) -> pd.DataFrame:
    """Normaliza columnas, tipos y recalcula los días desde la fecha del presupuesto."""
    hoy = hoy or date.today()
    df = df.copy()
    for c in COLUMNAS:
        if c not in df.columns:
            df[c] = None
    df = df[COLUMNAS + [c for c in df.columns if c not in COLUMNAS]]
    df = df[df["Teléfono"].notna() & df["Cliente"].notna()]
    df["Teléfono"] = df["Teléfono"].astype(str)
    df["Fecha presupuesto"] = pd.to_datetime(df["Fecha presupuesto"], errors="coerce")
    df["Último contacto"] = pd.to_datetime(df["Último contacto"], errors="coerce")
    df["Días"] = (pd.Timestamp(hoy) - df["Fecha presupuesto"]).dt.days.fillna(0).astype(int)
    df["Estado"] = df["Estado"].fillna("Sin marcar").where(df["Estado"].isin(ESTADOS), "Sin marcar")
    df["Mensajes enviados"] = pd.to_numeric(df["Mensajes enviados"], errors="coerce").fillna(0).astype(int)
    for c in ("Nota", "Opciones", "Población", "Zona", "Nº presupuesto"):
        df[c] = df[c].fillna("").astype(str)
    return df.reset_index(drop=True)


def marcar_enviado(df: pd.DataFrame, idx: int, hoy: date | None = None) -> pd.DataFrame:
    hoy = hoy or date.today()
    df = df.copy()
    df.loc[idx, "Mensajes enviados"] = int(df.loc[idx, "Mensajes enviados"]) + 1
    df.loc[idx, "Último contacto"] = pd.Timestamp(hoy)
    if df.loc[idx, "Estado"] == "Sin marcar":
        df.loc[idx, "Estado"] = "Pendiente"
    return df


def cambiar_estado(df: pd.DataFrame, idx: int, estado: str, nota: str = "", hoy: date | None = None) -> pd.DataFrame:
    if estado not in ESTADOS:
        raise ValueError(f"Estado no válido: {estado}")
    hoy = hoy or date.today()
    df = df.copy()
    df.loc[idx, "Estado"] = estado
    if nota:
        previa = str(df.loc[idx, "Nota"] or "").strip()
        sello = f"[{hoy.strftime('%d/%m')}] {nota}"
        df.loc[idx, "Nota"] = f"{previa} | {sello}" if previa else sello
    return df


def filtrar(df: pd.DataFrame, estados, dias_min, dias_max, texto="", solo_sin_contactar=False, zonas=None) -> pd.DataFrame:
    m = df["Estado"].isin(estados) & df["Días"].between(dias_min, dias_max)
    if texto:
        t = texto.strip().lower()
        m &= (df["Cliente"].str.lower().str.contains(t, regex=False)
              | df["Población"].str.lower().str.contains(t, regex=False)
              | df["Teléfono"].str.replace(" ", "").str.contains(t.replace(" ", ""), regex=False))
    if solo_sin_contactar:
        m &= df["Mensajes enviados"] == 0
    if zonas:
        m &= df["Zona"].isin(zonas)
    return df[m]


def a_excel_bytes(df: pd.DataFrame) -> bytes:
    from io import BytesIO
    salida = df[COLUMNAS].copy()
    for c in ("Fecha presupuesto", "Último contacto"):
        salida[c] = pd.to_datetime(salida[c], errors="coerce").dt.date
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        salida.to_excel(w, index=False, sheet_name="Seguimiento")
        ws = w.sheets["Seguimiento"]
        for col, ancho in zip("ABCDEFGHIJKLMN", [18, 26, 24, 22, 14, 14, 14, 7, 18, 26, 22, 40, 14, 10]):
            ws.column_dimensions[col].width = ancho
        ws.freeze_panes = "C2"
        ws.auto_filter.ref = ws.dimensions
    return buf.getvalue()


# --------------------------------------------------------------------------- API de WhatsApp (opcional)
def enviar_api_texto(telefono, texto: str, token: str, phone_number_id: str, version: str = "v20.0", timeout: int = 20):
    """Envía un mensaje de texto con la API de WhatsApp Cloud. Devuelve (ok, detalle).

    Solo funciona con texto libre dentro de las 24 h posteriores a un mensaje del cliente;
    para iniciar conversación hay que usar una plantilla aprobada (enviar_api_plantilla).
    """
    import requests
    d = normalizar_telefono(telefono)
    if not d:
        return False, "Teléfono no válido"
    url = f"https://graph.facebook.com/{version}/{phone_number_id}/messages"
    r = requests.post(url, headers={"Authorization": f"Bearer {token}"}, timeout=timeout,
                      json={"messaging_product": "whatsapp", "to": d, "type": "text",
                            "text": {"body": texto, "preview_url": False}})
    return r.ok, r.text[:300]


def enviar_api_plantilla(telefono, plantilla: str, parametros: list[str], token: str, phone_number_id: str,
                         idioma: str = "es", version: str = "v20.0", timeout: int = 20):
    """Envía una plantilla aprobada por Meta (obligatoria para iniciar conversación)."""
    import requests
    d = normalizar_telefono(telefono)
    if not d:
        return False, "Teléfono no válido"
    url = f"https://graph.facebook.com/{version}/{phone_number_id}/messages"
    comp = [{"type": "body", "parameters": [{"type": "text", "text": p} for p in parametros]}] if parametros else []
    r = requests.post(url, headers={"Authorization": f"Bearer {token}"}, timeout=timeout,
                      json={"messaging_product": "whatsapp", "to": d, "type": "template",
                            "template": {"name": plantilla, "language": {"code": idioma}, "components": comp}})
    return r.ok, r.text[:300]


def datos_ejemplo(hoy: date | None = None) -> pd.DataFrame:
    """Datos ficticios para probar la app sin cargar el listado real."""
    hoy = hoy or date.today()
    from datetime import timedelta
    filas = [
        ("612 34 56 78", "Lucía Prueba", "Paterna (Valencia)", "Valencia y alrededores", 450, 495, 20, "Sin marcar", "", "", 0),
        ("655 00 11 22", "Marcos Ejemplo", "Valencia", "Valencia y alrededores", 300, 330, 9, "Pendiente", "", "", 1),
        ("+44 7700 900123", "Elena Test", "Mislata (Valencia)", "Valencia y alrededores", 650, 715, 34, "Sin marcar", "340 € · 650 €", "", 0),
        ("699 88 77 66", "Pablo Demo", "Torrent (Valencia)", "Valencia y alrededores", 850, 935, 12, "Aprobado pendiente", "", "Quiere esperar a noviembre", 1),
    ]
    out = []
    for tel, nom, pob, zona, imp, imp_iva, dias, est, ops, nota, env in filas:
        out.append({"Teléfono": tel, "Cliente": nom, "Población": pob, "Zona": zona, "Importe sin IVA (€)": imp,
                    "Importe con IVA (€)": imp_iva, "Fecha presupuesto": hoy - timedelta(days=dias), "Días": dias,
                    "Estado": est, "Nº presupuesto": "EJEMPLO", "Opciones": ops, "Nota": nota,
                    "Último contacto": None, "Mensajes enviados": env})
    return preparar(pd.DataFrame(out), hoy)
