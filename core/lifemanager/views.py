from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Q, Avg, Value
from django.db.models.functions import Lower
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse
from django.utils import timezone
from django.utils.encoding import smart_str
from .models import User, DiaryEntry, Reminder, LifeSphere, SphereAssessment, Goal, GoalStep
from datetime import date, timedelta
from collections import defaultdict
import csv
import logging
import re
from .models import Note, NoteItem
import json
from django.http import JsonResponse

logger = logging.getLogger('lifemanager')


@login_required
def dashboard(request):
    user = request.user

    latest_assessments = {}
    all_assessments_by_date = defaultdict(dict)
    all_dates = []

    assessments = SphereAssessment.objects.filter(user=user) \
        .select_related('sphere') \
        .order_by('-date')

    for assessment in assessments:
        date_str = assessment.date.isoformat()
        all_assessments_by_date[date_str][assessment.sphere.title] = assessment.value

        if date_str not in all_dates:
            all_dates.append(date_str)

    all_dates.sort(reverse=True)

    if all_dates:
        latest_date = all_dates[0]
        latest_assessments = all_assessments_by_date[latest_date]
    else:
        latest_assessments = {}

    all_spheres = list(LifeSphere.objects.values_list('title', flat=True))

    normalized_assessments_by_date = {}
    for date_str, data in all_assessments_by_date.items():
        normalized_data = {}
        for sphere in all_spheres:
            normalized_data[sphere] = data.get(sphere, 0)
        normalized_assessments_by_date[date_str] = normalized_data

    recent_data = defaultdict(list)
    for sphere in LifeSphere.objects.all():
        sphere_assessments = SphereAssessment.objects.filter(
            user=user,
            sphere=sphere
        ).order_by('-date')[:10]

        for a in reversed(sphere_assessments):
            recent_data[sphere.title].append({
                'date': a.date.strftime('%d.%m'),
                'value': a.value
            })

    chart_series = []
    colors = ['#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#3498db', '#e67e22', '#34495e']
    for i, (sphere_name, points) in enumerate(recent_data.items()):
        if points:
            chart_series.append({
                'label': sphere_name,
                'data': [p['value'] for p in points],
                'dates': [p['date'] for p in points],
                'color': colors[i % len(colors)]
            })

    active_goals = Goal.objects.filter(user=user, status='active').order_by('deadline')[:5]

    return render(request, 'dashboard.html', {
        'latest_assessments': latest_assessments,
        'all_assessments_by_date': normalized_assessments_by_date,
        'all_dates': all_dates,
        'all_spheres': all_spheres,
        'chart_series': chart_series,
        'active_goals': active_goals,
        'has_history': len(all_dates) > 1,
    })


def validate_password(password):
    errors = []
    if len(password) < 8:
        errors.append("Пароль должен содержать минимум 8 символов")
    if not re.search(r'[A-Z]', password):
        errors.append("Пароль должен содержать хотя бы одну заглавную букву")
    if not re.search(r'[a-z]', password):
        errors.append("Пароль должен содержать хотя бы одну строчную букву")
    if not re.search(r'\d', password):
        errors.append("Пароль должен содержать хотя бы одну цифру")
    if not re.search(r'[.!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', password):
        errors.append("Пароль должен содержать хотя бы один спецсимвол (например, ., !, @)")
    return errors


def register(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        name = request.POST.get('name')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')

        field_errors = {}

        if not email:
            field_errors['email'] = "Email обязателен"
        elif User.objects.filter(email=email).exists():
            field_errors['email'] = "Пользователь с таким email уже существует"

        if not name:
            field_errors['name'] = "Имя обязательно"

        if not password:
            field_errors['password'] = "Пароль обязателен"
        else:
            password_errors = validate_password(password)
            if password_errors:
                field_errors['password'] = password_errors[0]
            elif password != password_confirm:
                field_errors['password_confirm'] = "Пароли не совпадают"

        if field_errors:
            logger.warning(f"Ошибки регистрации: {field_errors}")
            return render(request, 'registration/register.html', {
                'field_errors': field_errors,
                'email': email,
                'name': name,
            })
        else:
            try:
                user = User.objects.create_user(email=email, name=name, password=password)
                login(request, user)
                logger.info(f"Успешная регистрация: {email} (ID: {user.id})")
                return redirect('dashboard')
            except Exception as e:
                logger.error(f"Ошибка при регистрации пользователя {email}: {e}", exc_info=True)
                field_errors['non_field'] = "Произошла ошибка при регистрации"
                return render(request, 'registration/register.html', {
                    'field_errors': field_errors,
                    'email': email,
                    'name': name,
                })

    return render(request, 'registration/register.html')


def user_login(request):
    field_errors = {}
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        if not email:
            field_errors['email'] = "Email обязателен"
        if not password:
            field_errors['password'] = "Пароль обязателен"

        if not field_errors:
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                logger.info(f"Успешный вход: {email}")
                return redirect('dashboard')
            else:
                field_errors['non_field'] = "Неверный email или пароль"
                logger.warning(f"Неудачная попытка входа: {email}")

    return render(request, 'registration/login.html', {'field_errors': field_errors})


def user_logout(request):
    user_email = request.user.email
    logout(request)
    logger.info(f"Выход из системы: {user_email}")
    return redirect('login')


@login_required
def profile(request):
    user = request.user

    assessments = SphereAssessment.objects.filter(user=user).order_by('-date')
    total_assessments = assessments.count()

    week_ago = date.today() - timedelta(days=7)
    last_week_count = assessments.filter(date__gte=week_ago).count()

    avg_score = assessments.aggregate(avg=Avg('value'))['avg']
    average_score = round(avg_score, 1) if avg_score else 0

    recent_goals = Goal.objects.filter(user=user).order_by('-deadline')[:3]
    recent_entries = DiaryEntry.objects.filter(user=user).order_by('-created_at')[:3]

    return render(request, 'profile/profile.html', {
        'total_assessments': total_assessments,
        'last_week_count': last_week_count,
        'average_score': average_score,
        'recent_goals': recent_goals,
        'recent_entries': recent_entries,
    })


@login_required
def sphere_list(request):
    sort_by = request.GET.get('sort', '')

    if sort_by == 'alpha':
        spheres = LifeSphere.objects.all().order_by('title')
    else:
        spheres = LifeSphere.objects.all()

    today = date.today()
    assessed_today = SphereAssessment.objects.filter(
        user=request.user,
        date=today
    ).values_list('sphere_id', flat=True)

    return render(request, 'spheres/sphere_list.html', {
        'spheres': spheres,
        'today': today,
        'assessed_today': list(assessed_today),
        'sort_by': sort_by,
    })


@login_required
def create_assessment(request, sphere_id):
    sphere = get_object_or_404(LifeSphere, id=sphere_id)
    user = request.user

    if request.method == 'POST':
        value = request.POST.get('value')
        if value and 1 <= int(value) <= 10:
            obj, created = SphereAssessment.objects.update_or_create(
                user=user,
                sphere=sphere,
                date=date.today(),
                defaults={'value': int(value)}
            )
            action = "создана" if created else "обновлена"
            logger.info(f"Оценка сферы '{sphere.title}' {action} пользователем {user.email}: {value}/10")
            return redirect('sphere_list')
        else:
            logger.warning(f"Некорректная оценка от {user.email}: {value}")
            error = "Пожалуйста, выберите оценку от 1 до 10."
    else:
        error = None

    last_assessment = SphereAssessment.objects.filter(
        user=user, sphere=sphere
    ).order_by('-date').first()

    return render(request, 'spheres/create_assessment.html', {
        'sphere': sphere,
        'error': error,
        'last_assessment': last_assessment,
    })


def assessment_history(request):
    assessments = SphereAssessment.objects.filter(user=request.user).order_by('-date')

    # Подсчет статистики
    total_count = assessments.count()

    # Подсчет оценок за последние 7 дней
    week_ago = timezone.now().date() - timedelta(days=7)
    last_week_count = assessments.filter(date__gte=week_ago).count()

    # Подсчет средней оценки
    if total_count > 0:
        total_sum = sum(assessment.value for assessment in assessments)
        average_score = round(total_sum / total_count, 1)
    else:
        average_score = 0

    return render(request, 'spheres/assessment_history.html', {
        'assessments': assessments,
        'total_count': total_count,
        'last_week_count': last_week_count,
        'average_score': average_score,  # ← ЭТО УЖЕ ЕСТЬ!
    })


@login_required
def goal_list(request):
    goals = Goal.objects.filter(user=request.user).select_related('sphere')

    status_filter = request.GET.get('status')
    if status_filter in ['active', 'completed', 'postponed']:
        goals = goals.filter(status=status_filter)
    elif status_filter == 'all' or not status_filter:
        pass

    search_query = request.GET.get('search')
    if search_query:
        goals = goals.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    goals = goals.annotate(
        sort_order=models.Case(
            models.When(is_pinned=True, then=0),
            models.When(status='active', then=1),
            models.When(status='postponed', then=2),
            models.When(status='completed', then=3),
            default=4,
            output_field=models.IntegerField()
        )
    ).order_by('sort_order', '-deadline')

    paginator = Paginator(goals, 5)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.get_page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page_obj = paginator.get_page(1)

    all_goals = Goal.objects.filter(user=request.user)
    total_count = all_goals.count()
    active_count = all_goals.filter(status='active').count()
    completed_count = all_goals.filter(status='completed').count()
    overdue_count = all_goals.filter(deadline__lt=date.today(), status='active').count()

    return render(request, 'goals/goal_list.html', {
        'page_obj': page_obj,
        'total_count': total_count,
        'active_count': active_count,
        'completed_count': completed_count,
        'overdue_count': overdue_count,
        'current_status': status_filter or 'all',
        'search_query': search_query or '',
        'today': date.today(),
    })


@login_required
def toggle_pin_goal(request, goal_id):
    goal = get_object_or_404(Goal, id=goal_id, user=request.user)
    goal.is_pinned = not goal.is_pinned
    goal.save()
    logger.info(f"Пользователь {request.user.email} {'закрепил' if goal.is_pinned else 'открепил'} цель: {goal.title}")
    return redirect('goal_list')


@login_required
def create_goal(request):
    spheres = LifeSphere.objects.all()

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        sphere_id = request.POST.get('sphere')
        deadline_str = request.POST.get('deadline')
        status = request.POST.get('status', 'active')

        if not title or not sphere_id or not deadline_str:
            messages.error(request, "Все обязательные поля должны быть заполнены.")
            logger.warning(f"Пользователь {request.user.email} попытался создать цель без обязательных полей")
        else:
            try:
                deadline = date.fromisoformat(deadline_str)
                if deadline < date.today():
                    messages.error(request, "Дедлайн не может быть в прошлом.")
                    logger.warning(f"Пользователь {request.user.email} указал дедлайн в прошлом: {deadline}")
                else:
                    sphere = get_object_or_404(LifeSphere, id=sphere_id)
                    goal = Goal.objects.create(
                        user=request.user,
                        title=title,
                        description=description,
                        sphere=sphere,
                        deadline=deadline,
                        status=status,
                        progress=0
                    )

                    step_titles = request.POST.getlist('step_title')
                    step_checks = request.POST.getlist('step_completed')
                    has_steps = any(title.strip() for title in step_titles)

                    if has_steps:
                        for i, title in enumerate(step_titles):
                            if title.strip():
                                is_completed = (i < len(step_checks)) and (step_checks[i] == 'on')
                                GoalStep.objects.create(
                                    goal=goal,
                                    title=title.strip(),
                                    is_completed=is_completed,
                                    completed_at=timezone.now() if is_completed else None
                                )
                        steps = goal.steps.all()
                        total = steps.count()
                        completed = steps.filter(is_completed=True).count()
                        goal.progress = int((completed / total) * 100) if total > 0 else 0
                    else:
                        progress = request.POST.get('progress')
                        try:
                            goal.progress = max(0, min(100, int(progress or 0)))
                        except (ValueError, TypeError):
                            goal.progress = 0

                    if goal.progress == 100 and goal.status != 'completed':
                        goal.status = 'completed'

                    goal.save()

                    if request.POST.get('create_reminder'):
                        reminder_time = request.POST.get('reminder_time', '09:00')
                        Reminder.objects.create(
                            user=request.user,
                            type='deadline_based',
                            time=reminder_time,
                            goal=goal,
                            is_enabled=True
                        )
                        logger.info(f"Создано напоминание по дедлайну для цели: {goal.title}")

                    logger.info(f"Пользователь {request.user.email} создал цель: '{goal.title}' (ID: {goal.id})")
                    messages.success(request, "Цель успешно создана!")
                    return redirect('goal_list')

            except ValueError as e:
                messages.error(request, "Некорректная дата.")
                logger.error(f"Ошибка при разборе даты: {e}", exc_info=True)
            except Exception as e:
                messages.error(request, "Произошла ошибка при создании цели.")
                logger.error(f"Неожиданная ошибка при создании цели: {e}", exc_info=True)

    return render(request, 'goals/create_goal.html', {
        'spheres': spheres,
        'today': date.today().isoformat()
    })


@login_required
def edit_goal(request, goal_id):
    goal = get_object_or_404(Goal, id=goal_id, user=request.user)
    spheres = LifeSphere.objects.all()

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        sphere_id = request.POST.get('sphere')
        deadline_str = request.POST.get('deadline')
        status = request.POST.get('status')

        if not title or not sphere_id or not deadline_str:
            messages.error(request, "Все обязательные поля должны быть заполнены.")
        else:
            try:
                deadline = date.fromisoformat(deadline_str)
                if deadline < date.today() and status != 'completed':
                    messages.warning(request, "Дедлайн в прошлом — возможно, стоит завершить цель?")
                sphere = get_object_or_404(LifeSphere, id=sphere_id)
                goal.title = title
                goal.description = description
                goal.sphere = sphere
                goal.deadline = deadline
                goal.status = status

                goal.steps.all().delete()
                step_titles = request.POST.getlist('step_title')
                step_checks = request.POST.getlist('step_completed')
                has_steps = any(title.strip() for title in step_titles)

                if has_steps:
                    for i, title in enumerate(step_titles):
                        if title.strip():
                            is_completed = (i < len(step_checks)) and (step_checks[i] == 'on')
                            GoalStep.objects.create(
                                goal=goal,
                                title=title.strip(),
                                is_completed=is_completed,
                                completed_at=timezone.now() if is_completed else None
                            )
                    steps = goal.steps.all()
                    total = steps.count()
                    completed = steps.filter(is_completed=True).count()
                    goal.progress = int((completed / total) * 100) if total > 0 else 0
                    if goal.progress == 100 and goal.status != 'completed':
                        goal.status = 'completed'
                else:
                    progress = request.POST.get('progress')
                    try:
                        goal.progress = max(0, min(100, int(progress or 0)))
                    except (ValueError, TypeError):
                        pass

                goal.save()
                logger.info(f"Пользователь {request.user.email} обновил цель: {goal.title} (ID: {goal.id})")
                messages.success(request, "Цель обновлена!")
                return redirect('goal_list')
            except ValueError:
                messages.error(request, "Некорректная дата.")

    steps = goal.steps.all()
    return render(request, 'goals/edit_goal.html', {
        'goal': goal,
        'spheres': spheres,
        'steps': steps,
        'today': date.today().isoformat()
    })


@login_required
def delete_goal(request, goal_id):
    goal = get_object_or_404(Goal, id=goal_id, user=request.user)
    if request.method == 'POST':
        goal_title = goal.title
        goal.delete()
        logger.info(f"Пользователь {request.user.email} удалил цель: {goal_title}")
        messages.success(request, "Цель удалена.")
        return redirect('goal_list')
    return render(request, 'goals/delete_goal.html', {'goal': goal})


@login_required
def diary_list(request):
    entries = DiaryEntry.objects.filter(user=request.user) \
        .select_related('sphere', 'goal') \
        .order_by('-created_at')

    total_count = entries.count()
    with_media_count = entries.exclude(media_file='').count()
    with_goal_count = entries.exclude(goal=None).count()

    thirty_days_ago = timezone.now() - timedelta(days=30)
    last_30_days = entries.filter(created_at__gte=thirty_days_ago).count()

    return render(request, 'diary/diary_list.html', {
        'entries': entries,
        'total_count': total_count,
        'with_media_count': with_media_count,
        'with_goal_count': with_goal_count,
        'last_30_days': last_30_days,
    })


@login_required
def create_diary_entry(request):
    spheres = LifeSphere.objects.all()
    goals = Goal.objects.filter(user=request.user, status__in=['active', 'postponed'])

    if request.method == 'POST':
        text = request.POST.get('text')
        sphere_id = request.POST.get('sphere') or None
        goal_id = request.POST.get('goal') or None
        media_file = request.FILES.get('media_file')

        if not text:
            messages.error(request, "Текст записи обязателен.")
            logger.warning(f"Пустая запись от {request.user.email}")
        else:
            entry = DiaryEntry(
                user=request.user,
                text=text,
                media_file=media_file
            )
            if sphere_id:
                entry.sphere_id = sphere_id
            if goal_id:
                entry.goal_id = goal_id
            entry.save()
            logger.info(f"Пользователь {request.user.email} создал запись в дневнике (ID: {entry.id})")
            messages.success(request, "Запись добавлена!")
            return redirect('diary_list')

    return render(request, 'diary/create_diary_entry.html', {
        'spheres': spheres,
        'goals': goals
    })


@login_required
def edit_diary_entry(request, entry_id):
    entry = get_object_or_404(DiaryEntry, id=entry_id, user=request.user)
    spheres = LifeSphere.objects.all()
    goals = Goal.objects.filter(user=request.user, status__in=['active', 'postponed'])

    if request.method == 'POST':
        text = request.POST.get('text')
        sphere_id = request.POST.get('sphere') or None
        goal_id = request.POST.get('goal') or None
        media_file = request.FILES.get('media_file')

        if not text:
            messages.error(request, "Текст записи обязателен.")
        else:
            entry.text = text
            entry.sphere_id = sphere_id
            entry.goal_id = goal_id
            if media_file:
                entry.media_file = media_file
            entry.save()
            logger.info(f"Пользователь {request.user.email} обновил запись в дневнике (ID: {entry.id})")
            messages.success(request, "Запись обновлена!")
            return redirect('diary_list')

    return render(request, 'diary/edit_diary_entry.html', {
        'entry': entry,
        'spheres': spheres,
        'goals': goals
    })


@login_required
def delete_diary_entry(request, entry_id):
    entry = get_object_or_404(DiaryEntry, id=entry_id, user=request.user)
    if request.method == 'POST':
        entry.delete()
        logger.info(f"Пользователь {request.user.email} удалил запись в дневнике (ID: {entry.id})")
        messages.success(request, "Запись удалена.")
        return redirect('diary_list')
    return render(request, 'diary/delete_diary_entry.html', {'entry': entry})


@login_required
def reminder_list(request):
    reminders = Reminder.objects.filter(user=request.user).order_by('type', 'time')

    total_count = reminders.count()
    active_count = reminders.filter(is_enabled=True).count()
    daily_count = reminders.filter(type='daily').count()

    paginator = Paginator(reminders, 5)
    page_number = request.GET.get('page', 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, 'reminders/reminder_list.html', {
        'page_obj': page_obj,
        'reminders': page_obj.object_list,
        'total_count': total_count,
        'active_count': active_count,
        'daily_count': daily_count,
        'paginator': paginator,
    })


@login_required
def create_reminder(request):
    goals = Goal.objects.filter(user=request.user)
    if request.method == 'POST':
        type = request.POST.get('type')
        time = request.POST.get('time')
        goal_id = request.POST.get('goal') or None

        if not type or not time:
            messages.error(request, "Выберите тип и время напоминания.")
        elif type == 'deadline_based' and not goal_id:
            messages.error(request, "Для напоминания по дедлайну обязательно выберите цель.")
        else:
            Reminder.objects.create(
                user=request.user,
                type=type,
                time=time,
                goal_id=goal_id,
                is_enabled=True
            )
            logger.info(f"Пользователь {request.user.email} создал напоминание: тип={type}, время={time}")
            messages.success(request, "Напоминание создано!")
            return redirect('dashboard')
    return render(request, 'reminders/create_reminder.html', {'goals': goals})


@login_required
def delete_reminder(request, reminder_id):
    reminder = get_object_or_404(Reminder, id=reminder_id, user=request.user)
    if request.method == 'POST':
        reminder_type = reminder.get_type_display()
        reminder.delete()
        logger.info(f"Пользователь {request.user.email} удалил напоминание: {reminder_type}")
        messages.success(request, "Напоминание удалено.")
        return redirect('reminder_list')
    return render(request, 'reminders/delete_reminder.html', {'reminder': reminder})


@login_required
def toggle_reminder(request, reminder_id):
    reminder = get_object_or_404(Reminder, id=reminder_id, user=request.user)
    reminder.is_enabled = not reminder.is_enabled
    reminder.save()
    status = "включено" if reminder.is_enabled else "выключено"
    logger.info(f"Пользователь {request.user.email} {status} напоминание: {reminder.get_type_display()}")
    return redirect('dashboard')


@login_required
def export_data(request):
    logger.info(f"Пользователь {request.user.email} запросил экспорт данных")
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="life_balance_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        smart_str("Тип"),
        smart_str("Дата/Дедлайн"),
        smart_str("Название/Сфера"),
        smart_str("Описание/Текст/Значение"),
        smart_str("Статус/Прогресс"),
        smart_str("Привязка"),
        smart_str("Медиафайл")
    ])

    assessments = SphereAssessment.objects.filter(user=request.user).select_related('sphere').order_by('-date')
    for a in assessments:
        writer.writerow([
            smart_str("Оценка сферы"),
            smart_str(a.date.strftime('%Y-%m-%d')),
            smart_str(a.sphere.title),
            smart_str(a.value),
            smart_str(""),
            smart_str(""),
            smart_str("")
        ])

    goals = Goal.objects.filter(user=request.user).select_related('sphere').order_by('deadline')
    for goal in goals:
        steps_text = "; ".join([f"{'✓' if s.is_completed else '☐'} {s.title}" for s in goal.steps.all()])
        description = f"{goal.description or ''}\nШаги: {steps_text}".strip()
        writer.writerow([
            smart_str("Цель"),
            smart_str(goal.deadline.strftime('%Y-%m-%d')),
            smart_str(goal.title),
            smart_str(description),
            smart_str(f"{goal.get_status_display()} ({goal.progress}%)"),
            smart_str(goal.sphere.title if goal.sphere else ""),
            smart_str("")
        ])

    entries = DiaryEntry.objects.filter(user=request.user).select_related('sphere', 'goal').order_by('-created_at')
    for entry in entries:
        writer.writerow([
            smart_str("Запись в дневнике"),
            smart_str(entry.created_at.strftime('%Y-%m-%d %H:%M')),
            smart_str(entry.sphere.title if entry.sphere else "—"),
            smart_str(entry.text),
            smart_str(""),
            smart_str(entry.goal.title if entry.goal else ""),
            smart_str(entry.media_file.url if entry.media_file else "")
        ])

    return response


@login_required
def note_list(request):
    notes = Note.objects.filter(user=request.user).prefetch_related('items').order_by('-created_at')
    return render(request, 'notes/note_list.html', {'notes': notes})


@login_required
def create_note(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        item_texts = request.POST.getlist('item_text')

        if not title or not any(item_texts):
            messages.error(request, "Заголовок и хотя бы один пункт обязательны.")
        else:
            note = Note.objects.create(user=request.user, title=title)
            for text in item_texts:
                if text.strip():
                    NoteItem.objects.create(note=note, text=text.strip())
            logger.info(f"Пользователь {request.user.email} создал заметку: '{title}'")
            messages.success(request, "Заметка создана!")
            return redirect('note_list')

    return render(request, 'notes/create_note.html')


@login_required
def edit_note(request, note_id):
    note = get_object_or_404(Note, id=note_id, user=request.user)

    if request.method == 'POST':
        title = request.POST.get('title')
        item_texts = request.POST.getlist('item_text')
        item_ids = request.POST.getlist('item_id')
        completed_ids = request.POST.getlist('completed_items')

        if not title or not any(item_texts):
            messages.error(request, "Заголовок и хотя бы один пункт обязательны.")
        else:
            note.title = title
            note.save()

            existing_items = {str(item.id): item for item in note.items.all()}
            updated_item_ids = set()
            for i, text in enumerate(item_texts):
                if not text.strip():
                    continue

                if i < len(item_ids) and item_ids[i] in existing_items:
                    item = existing_items[item_ids[i]]
                    item.text = text.strip()
                    item.is_completed = item_ids[i] in completed_ids
                    item.save()
                    updated_item_ids.add(item_ids[i])
                else:
                    NoteItem.objects.create(
                        note=note,
                        text=text.strip(),
                        is_completed=str(i) in completed_ids
                    )

            for item_id, item in existing_items.items():
                if item_id not in updated_item_ids:
                    item.delete()

            logger.info(f"Пользователь {request.user.email} обновил заметку: '{note.title}'")
            messages.success(request, "Заметка обновлена!")
            return redirect('note_list')

    return render(request, 'notes/edit_note.html', {'note': note})


@login_required
def delete_note(request, note_id):
    note = get_object_or_404(Note, id=note_id, user=request.user)
    if request.method == 'POST':
        note_title = note.title
        note.delete()
        logger.info(f"Пользователь {request.user.email} удалил заметку: '{note_title}'")
        messages.success(request, "Заметка удалена.")
        return redirect('note_list')
    return render(request, 'notes/delete_note.html', {'note': note})


@login_required
def toggle_note_item(request, note_id, item_id):
    note = get_object_or_404(Note, id=note_id, user=request.user)
    item = get_object_or_404(NoteItem, id=item_id, note=note)

    if request.method == 'POST':
        data = json.loads(request.body)
        item.is_completed = data.get('completed', False)
        item.save()
        logger.debug(
            f"Пользователь {request.user.email} обновил пункт заметки {item_id}: completed={item.is_completed}")
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=400)