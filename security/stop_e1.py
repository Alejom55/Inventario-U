"""Set the E1 stop switch. The bounded runner performs its scoped rollback."""
import json
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def stop(root=ROOT):
    marker=Path(root)/'security/runtime/STOP'
    marker.parent.mkdir(parents=True,exist_ok=True)
    if not marker.exists():
        marker.write_text(json.dumps({'stopped_at_utc':datetime.now(timezone.utc).isoformat(),
            'reason':'Operator requested E1 stop; preserve the shared API and VM.'})+'\n')
    return marker


def main():
    print(stop())
    print('STOP activo. El ejecutor deja de inyectar y entra en finally para revertir solo sus SKU.')
    print('Comprobar raw.json: rollback_verified=true y cleanup_error_type=null. Si falla, no declarar reversión.')
    print('No apaga la VM ni modifica el servicio compartido. No retirar STOP sin revisar la causa.')


if __name__=='__main__':main()
