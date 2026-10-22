"""Seed only synthetic data using the installed official beta.3 package."""
import json
from pathlib import Path
from termia.constants import DATA_FILE
from termia.stores import ConnectionStore

store=ConnectionStore(DATA_FILE)
try:
    store.data.app.language='es'
    store.data.app.theme='light'
    store.data.app.open_local_terminal_on_startup=False
    store.data.app.confirm_close_app=False
    group=store.add_group('Grupo sintético')
    store.add_server('Servidor sintético','fixture.invalid','lab',22,group.id)
    store.add_snippet('Snippet sintético','printf synthetic','Laboratorio')
    store.save()
finally:
    store.close()
(DATA_FILE.parent/'notes.json').write_text(json.dumps({'schema_version':2,
    'categories':[{'name':'Laboratorio'}],
    'notes':[{'id':'synthetic-visible-note','title':'Nota de pruebas','category':'Laboratorio',
              'content':'Nota sintética conservada durante la actualización.'}]}))
(DATA_FILE.parent/'notes.json').chmod(0o600)
