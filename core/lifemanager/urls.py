from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('password_change/', auth_views.PasswordChangeView.as_view(
        template_name='registration/password_change.html',
        success_url='/profile/'
    ), name='password_change'),

    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.html',
        success_url='/login/'
    ), name='password_reset'),

    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),

    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url='/login/'
    ), name='password_reset_confirm'),

    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),

    path('spheres/', views.sphere_list, name='sphere_list'),
    path('assessments/', views.assessment_history, name='assessment_history'),
    path('assess/<uuid:sphere_id>/', views.create_assessment, name='create_assessment'),

    path('goals/', views.goal_list, name='goal_list'),
    path('goals/create/', views.create_goal, name='create_goal'),
    path('goals/<uuid:goal_id>/edit/', views.edit_goal, name='edit_goal'),
    path('goals/<uuid:goal_id>/delete/', views.delete_goal, name='delete_goal'),

    path('diary/', views.diary_list, name='diary_list'),
    path('diary/create/', views.create_diary_entry, name='create_diary_entry'),
    path('diary/<uuid:entry_id>/edit/', views.edit_diary_entry, name='edit_diary_entry'),
    path('diary/<uuid:entry_id>/delete/', views.delete_diary_entry, name='delete_diary_entry'),

    path('reminders/', views.reminder_list, name='reminder_list'),
    path('reminders/create/', views.create_reminder, name='create_reminder'),
    path('reminders/<uuid:reminder_id>/toggle/', views.toggle_reminder, name='toggle_reminder'),
    path('reminders/<uuid:reminder_id>/delete/', views.delete_reminder, name='delete_reminder'),
    path('goals/<uuid:goal_id>/pin/', views.toggle_pin_goal, name='toggle_pin_goal'),
    path('export/', views.export_data, name='export_data'),

    path('notes/', views.note_list, name='note_list'),
    path('notes/create/', views.create_note, name='create_note'),
    path('notes/<uuid:note_id>/edit/', views.edit_note, name='edit_note'),
    path('notes/<uuid:note_id>/delete/', views.delete_note, name='delete_note'),
    path('notes/<uuid:note_id>/toggle-item/<uuid:item_id>/', views.toggle_note_item, name='toggle_note_item'),
]