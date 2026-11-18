"""Create a blank signing aid using the bundled document runtime (ReportLab)."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle


def main():
    root=Path(__file__).resolve().parents[1]
    target=root/'output/pdf/reglas-e1-para-firmar.pdf'
    target.parent.mkdir(parents=True,exist_ok=True)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='SmallE1',fontName='Helvetica',fontSize=9,leading=12,spaceAfter=6))
    p=lambda text:Paragraph(text,styles['SmallE1'])
    story=[Paragraph('Reglas de compromiso | E1 Inventario-U',styles['Title']),
        p('<b>FORMULARIO SIN ACEPTAR.</b> Completar el alcance exacto y adjuntar su JSON antes de firmar. '
          'Este documento en blanco no autoriza experimentos ni sustituye la aceptación personal de los tres integrantes.'),
        p('<b>Responsable:</b> Alejandro Marín. <b>Experimento:</b> reutilización de credencial de lectura para intentar crear SKU sintéticos en un laboratorio propio.'),
        p('<b>Cuenta AWS:</b> ____________________ <b>VM:</b> _____________________________'),
        p('<b>API HTTPS:</b> __________________________________________________________'),
        p('<b>Prometheus HTTPS:</b> ___________________________________________________'),
        p('<b>Inicio UTC:</b> _____________________ <b>Fin UTC:</b> ________________________'),
        p('<b>Revisión Git inmutable (40 caracteres):</b> ____________________________________'),
        p('<b>SHA256 del alcance JSON:</b><br/>________________________________________________________________________'),
        p('<b>Perfil fijo por ronda:</b> 10 lecturas legítimas y 10 intentos adversos; máximo 2 peticiones/s y 100 peticiones totales incluyendo monitorización y limpieza. Observación primaria: 30 s. Objetivo único: MTTD &lt;= 30 s. Guardarraíl: MTTC &lt;= 5 s y rechazo sostenido.'),
        p('<b>Alcance:</b> únicamente cuenta, VM, revisión, orígenes HTTPS, rutas y ventana indicados en el JSON adjunto. GET/POST/DELETE en SKU sintéticos y controles privados de publicación; consultas de monitorización autorizadas. Prohibidos terceros, universidad, otros grupos y datos reales. No se permite ampliar destinos mediante redirecciones.'),
        p('<b>Parada:</b> crear security/runtime/STOP ante señal del responsable, degradación inesperada, pérdida de telemetría o fin de ventana. Detener carga; intentar limpieza únicamente de los SKU creados en esa ejecución. Confirmar GET 404 y salud 200. No eliminar volúmenes ni registros ajenos.'),
        p('<b>Coste y cierre:</b> respetar la autorización vigente sobre la infraestructura. En la VM actual el usuario autorizó créditos Free hasta indicar apagado manual; la ventana E1 solo limita el experimento. No apagar el flujo compartido al terminar una ronda. No solapar experimentos del grupo. Conservar logs sanitizados, hashes, UTC y trazas; mantener credenciales y firmas fuera de Git.'),
        p('<b>Aceptación personal:</b> he revisado el JSON cuyo hash aparece arriba, verifico que tengo autorización sobre los recursos y acepto exclusivamente ese alcance y ventana. Cambios requieren nueva aceptación. Cada integrante conserva o entrega su PDF firmado; el hash de cada PDF se registra en el JSON privado.'),
    ]
    rows=[[p('<b>Nombre completo</b>'),p('<b>Firma personal</b>'),p('<b>Fecha y hora UTC</b>')]]
    for _ in range(3):rows.append(['','',''])
    table=Table(rows,colWidths=[65*mm,65*mm,40*mm],rowHeights=[10*mm,15*mm,15*mm,15*mm])
    table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.5,colors.HexColor('#a4aab2')),
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eef2f6')),('VALIGN',(0,0),(-1,-1),'TOP')]))
    story.extend([Spacer(1,2*mm),table,Spacer(1,3*mm),p('Revisión humana obligatoria: la comprobación de hashes demuestra integridad, no autentica escritura manuscrita. No completar nombres ni firmas por otra persona.')])
    doc=SimpleDocTemplate(str(target),pagesize=A4,rightMargin=19*mm,leftMargin=19*mm,topMargin=15*mm,bottomMargin=14*mm,
        title='Reglas E1 - formulario sin aceptar',author='Inventario-U')
    doc.build(story)
    print(target)


if __name__=='__main__':main()
