# Seguimiento de presupuestos por WhatsApp · Top Redes Valencia

App en Streamlit que te va mostrando, cliente a cliente, el mensaje de seguimiento ya redactado.
Abres WhatsApp con un clic, pulsas enviar y marcas el resultado. Al final descargas el listado actualizado.

## Cómo se usa
1. Carga el listado (`Seguimiento-Valencia-30-dias.xlsx`) en la barra lateral.
2. Pestaña **Cola de envío**: la app elige la plantilla según los días y los mensajes ya enviados
   (Seguimiento → Recordatorio → Cierre amistoso; Presupuesto caducado si pasan de 30 días).
3. **📲 Abrir WhatsApp** abre el chat con el texto escrito (puedes editarlo antes). Pulsa enviar en WhatsApp.
4. Vuelve a la app y pulsa:
   - **✅ Enviado**: suma un mensaje, anota la fecha y pasa a «Pendiente».
   - **👍 Aprobó**: pasa a «Aprobado pendiente». Después usa la plantilla **Confirmar fecha**.
   - **👎 No interesado**: pasa a «No aprobado».
   - **⏭ Saltar** / **◀ Anterior**.
5. Cuando instales, **🛠️ Marcar como ejecutado**.
6. Pestaña **Listado y estados**: edita estados y notas, y **descarga el Excel actualizado**.

## Por qué enlaces y no envío automático
Un envío 100 % automático exige la **API de WhatsApp Business (Cloud API)**: cuenta de empresa verificada,
plantillas aprobadas por Meta para iniciar conversaciones y coste por conversación. Con el enlace `wa.me`
funciona con tu WhatsApp normal o Business, sin plantillas ni coste, y tú mantienes el control de cada mensaje
(y evitas que bloqueen tu número por envíos masivos).

Si más adelante quieres la API, la app ya la incluye como modo avanzado (experimental, sin probar contra Meta):
añade en los *secrets* `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID` y, para el primer mensaje, `WHATSAPP_TEMPLATE`
(nombre de la plantilla aprobada, con dos variables: nombre e importe). Tiene un tope de 25 envíos por sesión y
pide confirmar cada uno.

## Instalación
```
pip install -r requirements.txt
streamlit run app.py
```
Para publicarla: sube la carpeta a un repositorio **privado** de GitHub y despliégala en Streamlit Cloud con el
acceso restringido. **No subas el listado real al repositorio** (contiene nombres y teléfonos): se carga desde la app.
En Streamlit Cloud los datos no se guardan entre sesiones, así que descarga el Excel al terminar.

Contraseña opcional (Settings → Secrets):
```
APP_PASSWORD = "tu-clave"
```

## Mensajes y protección de datos
Los mensajes solo van a clientes que han pedido presupuesto. Son breves, no insisten (máximo tres toques) y el
de **Cierre amistoso** ofrece cerrar el presupuesto si ya no interesa. Si un cliente pide que no le escribas más,
márcalo como «No aprobado» con la nota «No contactar».

## Pruebas
```
python test_app.py
```
