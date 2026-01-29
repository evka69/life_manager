import json
from django import template
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.safestring import mark_safe
from datetime import date, datetime

register = template.Library()

class CustomJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)

@register.filter(name='safe_json')
def safe_json(value):
    """Безопасно преобразует значение в JSON"""
    if value is None:
        return 'null'
    return mark_safe(json.dumps(value, cls=CustomJSONEncoder))