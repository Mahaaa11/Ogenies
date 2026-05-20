"""
Entry point Passenger pour PlanetHoster N0C (Setup Python App).

Passenger ne parle que WSGI ; FastAPI/Starlette sont ASGI. On utilise donc
`a2wsgi` (declaree dans requirements.txt) pour exposer l'app ASGI en WSGI.

N0C s'occupe d'activer le virtualenv et de pointer Passenger sur ce fichier.
Il suffit que ce fichier expose une variable `application`.
"""
import os
import sys

# S'assure que la racine du projet est sur le PYTHONPATH afin que
# `backend.app.main` et `src.lnc_agent.*` soient resolvables.
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from a2wsgi import ASGIMiddleware  # noqa: E402

from backend.app.main import app as _asgi_app  # noqa: E402

application = ASGIMiddleware(_asgi_app)
