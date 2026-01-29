import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.validators import MinValueValidator, MaxValueValidator


class UserManager(BaseUserManager):
    def create_user(self, email, name, password=None):
        if not email:
            raise ValueError('Пользователь должен иметь email')
        if not name:
            raise ValueError('Пользователь должен иметь имя')
        user = self.model(
            email=self.normalize_email(email),
            name=name,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password=None):
        user = self.create_user(email, name, password)
        user.is_admin = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, null=False, blank=False)
    email = models.EmailField(max_length=255, unique=True, null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    @property
    def is_staff(self):
        return self.is_admin


class LifeSphere(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=50, unique=True, null=False, blank=False)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.title


class SphereAssessment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    value = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        null=False,
        blank=False
    )
    date = models.DateField(null=False, blank=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    sphere = models.ForeignKey(LifeSphere, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Оценка сферы"
        verbose_name_plural = "Оценки сфер"

    def __str__(self):
        return f"{self.user.name} — {self.sphere.title}: {self.value}"


class Goal(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Активна'
        COMPLETED = 'completed', 'Выполнена'
        POSTPONED = 'postponed', 'Отложена'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=100, null=False, blank=False)
    description = models.TextField(null=True, blank=True)
    deadline = models.DateField(null=False, blank=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    progress = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0,
        null=False,
        blank=False
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    sphere = models.ForeignKey(LifeSphere, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    is_pinned = models.BooleanField(default=False, verbose_name="Закреплено")

    class Meta:
        ordering = ['-is_pinned', 'deadline']

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})" # Закреплённые сверху


class DiaryEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    text = models.TextField(null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    sphere = models.ForeignKey(LifeSphere, on_delete=models.SET_NULL, null=True, blank=True)
    goal = models.ForeignKey(Goal, on_delete=models.SET_NULL, null=True, blank=True)
    media_file = models.FileField(upload_to='diary_media/', null=True, blank=True)

    class Meta:
        verbose_name = "Запись в дневнике"
        verbose_name_plural = "Записи в дневнике"

    def __str__(self):
        return f"{self.user.name} — {self.created_at.strftime('%Y-%m-%d')}"


class Reminder(models.Model):
    class Type(models.TextChoices):
        DAILY = 'daily', 'Ежедневно'
        WEEKLY = 'weekly', 'Еженедельно'
        DEADLINE_BASED = 'deadline_based', 'По дедлайну'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=20, choices=Type.choices, null=False, blank=False)
    time = models.TimeField(null=False, blank=False)
    is_enabled = models.BooleanField(default=True)
    frequency = models.CharField(max_length=100, null=True, blank=True)  # напр. "Каждый понедельник"
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, null=True, blank=True)
    sphere = models.ForeignKey(LifeSphere, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Напоминание для {self.user.email} ({self.get_type_display()})"

class GoalStep(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name='steps')
    title = models.CharField(max_length=150, null=False, blank=False)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{'✓' if self.is_completed else '☐'} {self.title}"

    def calculate_progress_from_steps(self):
        steps = self.steps.all()
        if not steps.exists():
            return self.progress
        total = steps.count()
        completed = steps.filter(is_completed=True).count()
        return int((completed / total) * 100) if total > 0 else 0


class Note(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=100, verbose_name="Заголовок")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Заметка"
        verbose_name_plural = "Заметки"
        ordering = ['-created_at']


class NoteItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.ForeignKey(Note, related_name='items', on_delete=models.CASCADE)
    text = models.CharField(max_length=200, verbose_name="Текст пункта")
    is_completed = models.BooleanField(default=False, verbose_name="Выполнено")

    def __str__(self):
        return f"{'✓' if self.is_completed else '☐'} {self.text}"

    class Meta:
        verbose_name = "Пункт заметки"
        verbose_name_plural = "Пункты заметок"