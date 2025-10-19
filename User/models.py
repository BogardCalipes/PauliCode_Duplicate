from django.db import models
from datetime import datetime
from django.utils import timezone
import os, random
from django.utils.html import mark_safe

now = timezone.now()

# ---------- Helper Function for Image Uploads ----------
def image_path(instance, filename):
    basefilename, file_extension = os.path.splitext(filename)
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    randomstr = ''.join((random.choice(chars)) for x in range(10))
    return f'profile_pic/{basefilename}_{randomstr}{file_extension}'


# ---------- USER MODEL ----------
class User(models.Model):
    school_id = models.CharField(max_length=20, primary_key=True, verbose_name="School ID")
    first_name = models.CharField(max_length=50, verbose_name="First Name")
    last_name = models.CharField(max_length=50, verbose_name="Last Name")
    password = models.CharField(max_length=255, verbose_name="Password")
    user_image = models.ImageField(upload_to=image_path, default='profile_pic/image.png')

    STUDENT = 'Student'
    TEACHER = 'Teacher'
    USER_TYPE_CHOICES = [
        (STUDENT, 'Student'),
        (TEACHER, 'Teacher'),
    ]
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, verbose_name="User Type")

    def image_tag(self):
        return mark_safe(f'<img src="{self.user_image.url}" width="50" height="50" />')

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.user_type})"


# ---------- CLASS MODEL ----------
class Class(models.Model):
    class_id = models.AutoField(primary_key=True)
    class_code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='classes')
    upload_icon = models.ImageField(upload_to='class_icons/', blank=True, null=True)

    def __str__(self):
        return f"{self.title} ({self.class_code})"


# ---------- ENROLLMENT MODEL ----------
class Enrollment(models.Model):
    enrollment_id = models.AutoField(primary_key=True)
    class_id = models.ForeignKey(Class, on_delete=models.CASCADE)
    student_id = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('class_id', 'student_id')

    def __str__(self):
        return f"{self.student_id.first_name} in {self.class_id.title}"


# ---------- PROBLEM MODEL ----------
class Problem(models.Model):
    problem_id = models.AutoField(primary_key=True)
    class_id = models.ForeignKey(Class, on_delete=models.CASCADE)
    teacher_id = models.ForeignKey(User, on_delete=models.CASCADE)
    problem_title = models.CharField(max_length=150)
    problem_description = models.TextField()
    problem_type = models.CharField(
        max_length=20,
        choices=[('Assignment', 'Assignment'), ('Quiz', 'Quiz')]
    )
    total_score = models.IntegerField()
    time_limit = models.IntegerField()
    due_date = models.DateTimeField()

    def __str__(self):
        return f"{self.problem_title} ({self.class_id.title})"


# ---------- PROBLEM TEST CASE MODEL ----------
class ProblemTestCase(models.Model):
    testcase_id = models.AutoField(primary_key=True)
    problem_id = models.ForeignKey(Problem, on_delete=models.CASCADE)
    input_data = models.TextField()
    expected_output = models.TextField()

    def __str__(self):
        return f"TestCase #{self.testcase_id} for {self.problem_id.problem_title}"


# ---------- SUBMISSION MODEL ----------
class Submission(models.Model):
    submission_id = models.AutoField(primary_key=True)
    problem_id = models.ForeignKey(Problem, on_delete=models.CASCADE)
    student_id = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    score = models.IntegerField(default=0)

    def __str__(self):
        return f"Submission by {self.student_id.first_name} for {self.problem_id.problem_title}"
