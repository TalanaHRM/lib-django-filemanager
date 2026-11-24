import json

from django import forms
from django.utils.safestring import mark_safe

from .settings import FILEMANAGER_CKEDITOR_JS


def filemanager_config(url):
    d = {}
    d['filebrowserBrowseUrl'] = url
    d['filebrowserImageBrowseUrl'] = url
    d['filebrowserWidth'] = 800
    d['filebrowserHeight'] = 500
    return d


def _js_literal(value):
    """JSON for a value inlined in a <script>, with <, > and & escaped so it cannot close the tag."""
    return (
        json.dumps(value)
        .replace('<', '\\u003c')
        .replace('>', '\\u003e')
        .replace('&', '\\u0026')
    )


class CKEditorWidget(forms.Textarea):
    def __init__(self, attrs=None, config=None, filemanager_url=''):
        """ config : CKEditor config
            filemanager_url : for user to 'browse server'
            In config : toolbar = 'Basic'/'Standard'/'Full'
        """
        default = {
            'toolbar': 'Standard',
            'height': 250,
            'width': 900
        }
        default.update(config or {})
        if filemanager_url:
            default.update(filemanager_config(filemanager_url))
        self.config = default
        return super(CKEditorWidget, self).__init__(attrs)

    class Media:
        js = (
            FILEMANAGER_CKEDITOR_JS,
        )

    def render(self, name, value, attrs=None, renderer=None):
        rendered = super(CKEditorWidget, self).render(name, value, attrs, renderer)
        element_id = (attrs or {}).get('id') or self.attrs.get('id') or 'id_' + name
        div = "<div style='height:20px'></div>"
        return rendered + mark_safe(
            div
            + u"""<script type="text/javascript">
                    document.addEventListener('DOMContentLoaded', function() {
                      CKEDITOR.replace('%s',%s);
                    }, false);
                  </script>""" % (_js_literal(element_id), _js_literal(self.config))
        )
