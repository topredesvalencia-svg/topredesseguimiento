"""Pruebas: python test_app.py   (o pytest)"""
from datetime import date, timedelta

import pandas as pd
from streamlit.testing.v1 import AppTest

import logica as L

HOY = date(2026, 11, 4)


# --------------------------------------------------------------------------- teléfonos
def test_telefonos():
    assert L.normalizar_telefono("612 34 56 78") == "34612345678"
    assert L.normalizar_telefono("612345678") == "34612345678"
    assert L.normalizar_telefono("+34 612 34 56 78") == "34612345678"
    assert L.normalizar_telefono("+52 984 184 7241") == "529841847241"
    assert L.normalizar_telefono("+44 7986 266831") == "447986266831"
    assert L.normalizar_telefono("+1 321 315 8127") == "13213158127"
    assert L.normalizar_telefono("13213158127") == "13213158127"
    assert L.normalizar_telefono("0034612345678") == "34612345678"
    assert L.normalizar_telefono("644 51 62 5") == ""        # incompleto
    assert L.normalizar_telefono(None) == ""
    assert L.telefono_legible("34612345678") == "612 34 56 78"


def test_enlace():
    url = L.enlace_whatsapp("612 34 56 78", "Hola, ¿qué tal? 50 € + IVA")
    assert url.startswith("https://wa.me/34612345678?text=")
    assert " " not in url and "%C2%BF" in url and "%E2%82%AC" in url
    assert L.enlace_whatsapp("12", "x") == ""


# --------------------------------------------------------------------------- plantillas
def _fila(**kw):
    base = {"Cliente": "lucía prueba", "Población": "Paterna (Valencia)", "Importe sin IVA (€)": 450,
            "Importe con IVA (€)": 495, "Días": 10, "Estado": "Sin marcar", "Opciones": "", "Mensajes enviados": 0}
    base.update(kw)
    return base


def test_plantillas_todas_se_redactan():
    cfg = {"firmante": "Raúl", "empresa": "Top Redes Valencia", "agenda": "el jueves", "fecha_instalacion": "el viernes 14"}
    for nombre in L.PLANTILLAS:
        t = L.redactar(nombre, _fila(), cfg)
        assert "{" not in t and "}" not in t, nombre
        assert "Lucía" in t, nombre
    assert "450 € + IVA" in L.redactar("Seguimiento", _fila(), cfg)
    assert "340 € · 650 € + IVA" in L.redactar("Seguimiento", _fila(Opciones="340 € · 650 €"), cfg)
    assert "Paterna" in L.redactar("Cerrar y agendar", _fila(), cfg)
    assert "(Valencia)" not in L.redactar("Cerrar y agendar", _fila(), cfg)


def test_plantilla_automatica():
    assert L.plantilla_automatica(_fila(Días=5)) == "Seguimiento"
    assert L.plantilla_automatica(_fila(Días=20)) == "Recordatorio"
    assert L.plantilla_automatica(_fila(Días=40)) == "Presupuesto caducado"
    assert L.plantilla_automatica(_fila(**{"Mensajes enviados": 1, "Días": 12})) == "Recordatorio"
    assert L.plantilla_automatica(_fila(**{"Mensajes enviados": 2})) == "Cierre amistoso"
    assert L.plantilla_automatica(_fila(Estado="Aprobado pendiente")) == "Cerrar y agendar"


# --------------------------------------------------------------------------- datos y estados
def test_preparar_y_estados():
    df = L.datos_ejemplo(HOY)
    assert list(df.columns[:14]) == L.COLUMNAS and len(df) == 4
    assert df.loc[0, "Días"] == 20
    df2 = L.marcar_enviado(df, 0, HOY)
    assert df2.loc[0, "Mensajes enviados"] == 1 and df2.loc[0, "Estado"] == "Pendiente"
    assert df2.loc[0, "Último contacto"] == pd.Timestamp(HOY)
    assert df.loc[0, "Mensajes enviados"] == 0                 # no modifica el original
    df3 = L.cambiar_estado(df2, 0, "Aprobado pendiente", "Aprobó por WhatsApp", HOY)
    assert df3.loc[0, "Estado"] == "Aprobado pendiente" and "[04/11] Aprobó" in df3.loc[0, "Nota"]
    try:
        L.cambiar_estado(df, 0, "Inventado")
        assert False
    except ValueError:
        pass


def test_filtrar():
    df = L.datos_ejemplo(HOY)
    v = L.filtrar(df, L.ABIERTOS, 0, 60)
    assert len(v) == 4
    assert len(L.filtrar(df, ["Pendiente"], 0, 60)) == 1
    assert len(L.filtrar(df, L.ABIERTOS, 15, 60)) == 2
    assert list(L.filtrar(df, L.ABIERTOS, 0, 60, texto="mislata")["Cliente"]) == ["Elena Test"]
    assert list(L.filtrar(df, L.ABIERTOS, 0, 60, texto="655 00")["Cliente"]) == ["Marcos Ejemplo"]
    assert len(L.filtrar(df, L.ABIERTOS, 0, 60, solo_sin_contactar=True)) == 2


def test_excel_ida_y_vuelta():
    from io import BytesIO
    df = L.datos_ejemplo(HOY)
    df = L.marcar_enviado(df, 1, HOY)
    leido = L.preparar(pd.read_excel(BytesIO(L.a_excel_bytes(df)), dtype={"Teléfono": str}), HOY)
    assert len(leido) == 4 and leido.loc[1, "Mensajes enviados"] == 2
    assert leido.loc[2, "Teléfono"] == "+44 7700 900123"


def test_listado_real_se_lee():
    import os
    ruta = "/mnt/user-data/outputs/Seguimiento-Valencia-30-dias.xlsx"
    if not os.path.exists(ruta):
        return
    df = L.preparar(pd.read_excel(ruta, sheet_name="Seguimiento", dtype={"Teléfono": str}), HOY)
    assert len(df) >= 40
    assert (df["Teléfono"].map(L.normalizar_telefono) != "").mean() > 0.95   # casi todos con teléfono válido


# --------------------------------------------------------------------------- la app
def _app():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    return at


def _boton(at, texto):
    for b in list(at.button) + list(at.sidebar.button):
        if texto in b.label:
            return b
    raise AssertionError(f"No hay botón «{texto}»")


def test_app_arranca_sin_datos():
    at = _app()
    assert not at.exception
    assert any("Carga el listado" in i.value for i in at.info)


def test_app_flujo_completo():
    at = _app()
    _boton(at, "datos de ejemplo").click().run()
    assert not at.exception
    assert at.subheader[0].value == "Lucía Prueba"                  # el más antiguo de los abiertos... primero de la lista
    n0 = int(at.session_state["df"].loc[0, "Mensajes enviados"])
    _boton(at, "Enviado").click().run()
    assert not at.exception
    assert int(at.session_state["df"].loc[0, "Mensajes enviados"]) == n0 + 1
    assert at.session_state["pos"] == 1                             # pasa al siguiente
    _boton(at, "Aprobó").click().run()
    assert at.session_state["df"].loc[1, "Estado"] == "Aprobado pendiente"
    _boton(at, "No interesado").click().run()
    assert at.session_state["df"].loc[2, "Estado"] == "No aprobado"
    assert not at.exception


def test_app_plantilla_y_mensaje():
    at = _app()
    _boton(at, "datos de ejemplo").click().run()
    sel = at.selectbox[0]
    assert sel.value == "Recordatorio"                              # 20 días sin contactar
    sel.select("Cierre amistoso").run()
    area = [t for t in at.text_area if "Mensaje" in t.label][0]
    assert "No quiero molestarte" in area.value and "Lucía" in area.value


def test_app_resumen():
    at = _app()
    _boton(at, "datos de ejemplo").click().run()
    assert not at.exception
    assert len(at.metric) == 4


if __name__ == "__main__":
    pruebas = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for p in pruebas:
        p()
        print("OK  ", p.__name__)
    print(f"\n{len(pruebas)} pruebas pasan")
