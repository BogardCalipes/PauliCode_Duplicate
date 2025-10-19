from django.urls import path
from . import views

urlpatterns = [

    #--------------Portal---------------------------#
    path('', views.index, name='index'),  # shows the login page
    path('login/', views.login_view, name='login'),  # handles login form submission
    path('logout/', views.logout_view, name='logout'),  # handles logout

    #--------------Teacher Part--------------------#
    path('dashboard/', views.dashboard, name='dashboard'),
    path('signup/', views.signup, name='signup'),
    path('create-class/', views.create_class, name='create_class'),
    path('MyClasses/', views.MyClasses, name='MyClasses'),
    path('delete-class/<int:class_id>/', views.delete_class, name='delete_class'),
    path('class/<int:class_id>/', views.classDetails, name='classDetails'),
    path('class/<int:class_id>/add-problem/', views.add_problem, name='add_problem'),
    path("problem/<int:problem_id>/details/", views.get_problem_details, name="get_problem_details"),
    path("problem/<int:problem_id>/edit/", views.edit_problem, name="edit_problem"),
    path("problem/<int:problem_id>/delete/", views.delete_problem, name="delete_problem"),
    path('report/', views.report, name='report'),  # Reports dashboard
    path('delete_student/<str:school_id>/', views.delete_student, name='delete_student'),
    path('delete_submission/<int:submission_id>/', views.delete_submission, name='delete_submission'),
   



    

    #---------------Student Part--------------------#
    path('StudentDashboard/', views.StudentDashboard, name='StudentDashboard'),
    path('classes/', views.StudentClass, name='StudentClass'),
    path('student/join-class/', views.join_class, name='join_class'),
    path('student/class/<int:class_id>/', views.student_class_details, name='student_class_details'),
    path('student/class/<int:class_id>/unenroll/', views.unenroll_class, name='unenroll_class'),

    #--------------Student Playground---------------#
    path('playground/<int:problem_id>/', views.playground, name='playground'),
    path('run_playground_code/', views.run_playground_code, name='run_playground_code'),
    path('submit_problem/<int:problem_id>/', views.submit_problem, name='submit_problem'),



]
