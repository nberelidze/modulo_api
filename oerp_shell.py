"""
OpenERP XML-RPC interactive shell.

Usage:
    python oerp_shell.py
    python -i oerp_shell.py   # stay in REPL after script runs

Examples inside the REPL:
    oerp_execute('res.partner', 'search', [[('inno_patient', '=', True)]], {'limit': 5})
    oerp_execute('res.partner', 'read', [1], ['name', 'inno_code'])
    oerp_execute('ir.sequence', 'search', [[('name', 'like', 'Patient')]])
"""

import os
import sys

# Bootstrap Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

# Now import project utilities
from api.utils import oerp_execute, _get_oerp_xmlrpc_params, _oerp_xmlrpc_cache

def search(model, domain=None, limit=None, offset=0, order=None):
    """Shorthand: search a model and return ids."""
    kwargs = {}
    if limit is not None:
        kwargs['limit'] = limit
    if order:
        kwargs['order'] = order
    return oerp_execute(model, 'search', [domain or []], kwargs)

def read(model, ids, fields=None):
    """Shorthand: read records."""
    return oerp_execute(model, 'read', ids if isinstance(ids, list) else [ids], fields or [])

def search_read(model, domain=None, fields=None, limit=None, order=None):
    """Shorthand: combined search + read."""
    kwargs = {'fields': fields or []}
    if limit is not None:
        kwargs['limit'] = limit
    if order:
        kwargs['order'] = order
    return oerp_execute(model, 'search_read', [domain or []], kwargs)


if __name__ == '__main__':
    # Warm up the connection and show status
    try:
        url, dbname, uid, password = _get_oerp_xmlrpc_params()
        print(f"Connected to OpenERP: {url}  db={dbname}  uid={uid}")
    except Exception as e:
        print(f"WARNING: Could not connect to OpenERP: {e}", file=sys.stderr)

    print()
    print("Available helpers: oerp_execute(), search(), read(), search_read()")
    print("Type help(oerp_execute) for usage details.")
    print()

    import code
    code.interact(local={**globals(), **locals()}, banner='')
