"""Render exposes the terminal business API, never OCI storage or coordinator calls."""
import os


def restrict_render_surface(app):
    if os.getenv('RENDER')!='true':return
    app.router.routes[:]=[route for route in app.router.routes if not (
        getattr(route,'path','').startswith(('/api/v2/storage','/api/v3/storage'))
        or getattr(route,'path','') in {'/api/v2/integracion','/api/v3/integracion'})]
