from .models import Reminder
import json
from django.utils.safestring import mark_safe

def reminders(request):
    if request.user.is_authenticated:
        reminders_list = []
        for r in Reminder.objects.filter(user=request.user, is_enabled=True):
            reminder_dict = {
                'id': str(r.id),
                'type': r.type,
                'time': r.time.strftime('%H:%M') if r.time else '',
                'goal': None,
                'sphere': None,
            }
            if r.goal:
                reminder_dict['goal'] = {
                    'id': str(r.goal.id),
                    'title': r.goal.title
                }
            if r.sphere:
                reminder_dict['sphere'] = {
                    'id': str(r.sphere.id),
                    'title': r.sphere.title
                }
            reminders_list.append(reminder_dict)
        return {'active_reminders': reminders_list}
    return {'active_reminders': []}