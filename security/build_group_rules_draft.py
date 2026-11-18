"""Prepare E1 fields without signing, accepting scope, or inventing execution IDs."""
import argparse
import hashlib
import io
import json
from pathlib import Path

from pypdf import PdfReader,PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
from reportlab.lib import colors

from security.scope import scope_digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--scope',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    rules=json.loads(args.scope.read_text(encoding='utf-8'))
    assert not rules['participants'],'Draft must not claim personal acceptance'
    source=PdfReader(args.source)
    assert len(source.pages)==4 and not source.get_fields(),'Review a changed source layout before editing'
    original_signing_text=''.join(source.pages[-1].extract_text().split())
    for page in source.pages:
        assert not any(a.get_object().get('/FT')=='/Sig' for a in page.get('/Annots',[]))
    start=rules['window_start_utc'].replace('T',' ').replace('+00:00','')
    end=rules['window_end_utc'].split('T')[-1].replace('+00:00','')
    overlays={
        1:[(215,583,'PROPUESTA - no aceptada'),(215,574,start[:16]),(215,565,'hasta '+end[:5]+' UTC'),
           (357,578,'R0: PENDIENTE'),(357,567,'R1: PENDIENTE - sin ejecutar')],
        2:[(129,728,'uv run python -m security.stop_e1'),
           (129,717,'STOP cooperativo; limpieza en finally. Ver anexo E1.')],
        3:[(57,492,'Fecha y hora UTC: _________________________'),
           (277,492,'Fecha y hora UTC: _________________________'),
           (57,370,'Fecha y hora UTC: _________________________')],
    }
    for index,lines in overlays.items():
        page=source.pages[index];buffer=io.BytesIO()
        c=canvas.Canvas(buffer,pagesize=(float(page.mediabox.width),float(page.mediabox.height)))
        c.setFillColor(colors.white)
        if index==1:c.rect(214,562,135,26,fill=1,stroke=0);c.rect(356,563,175,23,fill=1,stroke=0)
        elif index==2:c.rect(128,713,380,25,fill=1,stroke=0)
        c.setFillColor(colors.black);c.setFont('Helvetica',7.3)
        for x,y,text in lines:c.drawString(x,y,text)
        c.save();buffer.seek(0);page.merge_page(PdfReader(buffer).pages[0])
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='E1Body',fontName='Helvetica',fontSize=9,leading=12,spaceAfter=7))
    p=lambda text:Paragraph(text,styles['E1Body'])
    digest=scope_digest(rules)
    story=[Paragraph('Anexo E1 | Alcance propuesto para aceptar',styles['Title']),
        p('<b>BORRADOR SIN FIRMAS. NO AUTORIZA EJECUCIONES.</b> La ventana debe confirmarse sin solapar otras rondas. Para E1 se requiere aceptación personal de los tres antes de ejecutar; la narración del documento original sobre firmas posteriores no autoriza E1.'),
        p('<b>Responsable:</b> Alejandro Marín. <b>Cuenta AWS:</b> '+rules['account_id']+'. <b>VM:</b> '+rules['instance_id']+'.'),
        p('<b>API E1 prevista:</b> '+rules['api_origin']+'<br/><b>Prometheus E1 previsto:</b> '+rules['prometheus_origin']),
        p('Laboratorio aislado dentro de la VM propia: base y credenciales exclusivas. Su despliegue y comprobación HTTPS están pendientes. El flujo grupal conserva la API key y '+
          'https://3.151.219.131.sslip.io/api/v2; no ejecutar R1 sobre ese flujo.'),
        p('<b>Ventana propuesta:</b> '+start+' hasta '+end+' UTC (18 de noviembre, 10:00-11:00 COL). No es una ventana aceptada. Ejecutar R0 y después R1, anunciando inicio y fin en el grupo.'),
        p('<b>Revisión de aplicación prevista:</b> '+rules['application_revision']+'<br/><b>SHA256 del alcance JSON:</b> '+digest),
        p('<b>Hipótesis:</b> ante 10 lecturas normales y 10 intentos de crear SKU con identidad de lectura, a máximo 2 peticiones/s, R1 detecta el abuso en MTTD &lt;= 30 s. Guardarraíl: MTTC &lt;= 5 s y rechazo sostenido. Máximo 100 peticiones por ronda, incluidos sondeos y limpieza; observación primaria 30 s.'),
        p('<b>R0:</b> API key sin alcance por operación. <b>R1:</b> JWT Ed25519 con emisor, audiencia, sujeto, vida máxima de 300 s y alcance; token señuelo rechazado y alerta nativa. Técnica conceptual T1078. Ninguna medición oficial disponible todavía.'),
        p('<b>Operaciones:</b> GET, POST y DELETE solo en las rutas SKU del JSON, salud y publicación privada de resultados; consultas al Prometheus exacto. Crear y borrar únicamente SKU CYBER-E1 devueltos por la propia ejecución. No tocar los IDs del flujo ni los señuelos de los compañeros.'),
        p('<b>Parada exacta:</b> desde la raíz del ejecutor: <font name="Courier">uv run python -m security.stop_e1</font>. No matar el proceso: STOP impide el siguiente intento y activa su bloque finally. Este comprueba el código de cada SKU creado, elimina solo esos IDs, confirma GET 404 y salud 200.'),
        p('<b>Verificación:</b> revisar security/results/&lt;execution_id&gt;/raw.json: rollback_verified=true y cleanup_error_type=null. Si falla, conservar raw.json, suspender nuevas rondas y completar limpieza por esos mismos IDs y códigos con credencial operadora. STOP no revoca tokens ya emitidos; expiran en máximo 300 s. No declarar reversión hasta verificarla.'),
        p('<b>Coste y disponibilidad:</b> créditos Free autorizados y apagado manual. Ni STOP ni el final de ventana apagan la VM o cambian la API compartida. La Elastic IP se conserva mientras no se libere.'),
        p('<b>Runs R0/R1:</b> PENDIENTES. Tras ejecutar, adjuntar un anexo de resultados con enlaces, UTC, execution_id, trace_id, logs y hashes. No cambiar el alcance firmado ni rellenar números supuestos. Firma personal y fecha UTC en la hoja siguiente; adjuntar el JSON revisado.'),
        p('<b>Fuente grupal:</b> redundante3452/deportBack, security/game-day/reglas-compromiso.pdf. SHA256 original: '+hashlib.sha256(args.source.read_bytes()).hexdigest()),
    ]
    annex=io.BytesIO();SimpleDocTemplate(annex,pagesize=A4,leftMargin=42,rightMargin=42,topMargin=32,bottomMargin=30).build(story)
    annex.seek(0);annex_reader=PdfReader(annex)
    assert len(annex_reader.pages)==1,'Keep the scope annex readable on one page'
    writer=PdfWriter()
    for page in source.pages[:3]:writer.add_page(page)
    writer.add_page(annex_reader.pages[0]);writer.add_page(source.pages[3])
    writer.add_metadata({'/Title':'Reglas grupales - borrador E1 sin aceptar','/Author':'Inventario-U'})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('wb') as stream:writer.write(stream)
    check=PdfReader(args.output)
    assert len(check.pages)==5 and 'PENDIENTE' in check.pages[1].extract_text()
    signing_text=check.pages[-1].extract_text()
    assert ''.join(signing_text.split()).startswith(original_signing_text)
    assert signing_text.count('Fecha y hora UTC:')==3
    print(args.output)


if __name__=='__main__':main()
