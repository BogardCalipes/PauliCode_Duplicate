from django.shortcuts import render, redirect, get_object_or_404
from .models import User, Class, Problem, Enrollment, ProblemTestCase, Submission
from django.contrib import messages
from datetime import datetime
from django.http import JsonResponse 
import json, requests, subprocess, tempfile, os, shutil
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.urls import reverse
from django.db.models import Q
from django.core.serializers.json import DjangoJSONEncoder


# ---------------- LOGIN & DASHBOARD ---------------- #

def index(request):
    school_id = request.session.get('school_id')
    if school_id:
        user_type = request.session.get('user_type')
        if user_type == 'Teacher':
            return redirect('dashboard')
        else:
            return redirect('StudentDashboard')
    return render(request, 'User/index.html', {'currentpage': 'index'})



def login_view(request):
    if request.method == 'POST':
        school_id = request.POST.get('school_id', '').strip()
        password = request.POST.get('password', '').strip()

        try:
            user = User.objects.get(school_id=school_id, password=password)
            
            # Store user data in session
            request.session['school_id'] = user.school_id
            request.session['first_name'] = user.first_name
            request.session['last_name'] = user.last_name
            request.session['user_image'] = user.user_image.url if user.user_image else None
            request.session['user_type'] = user.user_type

            messages.success(request, f"Welcome back, {user.first_name}!")

            # Redirect based on user type
            if user.user_type == 'Teacher':
                return redirect('dashboard')  # make sure 'dashboard' exists in urls.py
            else:
                return redirect('StudentDashboard')  

        except User.DoesNotExist:
            messages.error(request, "Invalid School ID or Password.")
            return redirect('index')

    # Render login page
    return render(request, 'User/index.html')


#-------------TEACHER DASHBOARD----------------------#
def dashboard(request):
    school_id = request.session.get('school_id')

    if not school_id:
        # Redirect to login if not logged in
        messages.warning(request, "Please log in first.")
        return redirect('index')

    user = User.objects.filter(school_id=school_id).first()

    # Get classes created by the teacher
    classes = Class.objects.filter(teacher=user).order_by('-class_id')

    return render(request, 'User/dashboard.html', {
        'currentpage': 'dashboard',
        'user': user,
        'classes': classes,  # Pass class list to template
    })

    

def logout_view(request):
    request.session.flush()  # Clears all session data
    messages.success(request, "You have been logged out successfully.")
    return redirect('index')


# ---------------- SIGNUP ---------------- #

def signup(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        school_id = request.POST.get('school_id', '').strip()
        user_type = request.POST.get('user_type', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        user_image = request.FILES.get('user_image')  # handle uploaded file

        context = {
            'first_name': first_name,
            'last_name': last_name,
            'school_id': school_id,
            'user_type': user_type,
        }

        # ✅ Validate inputs
        if not all([first_name, last_name, school_id, user_type, password, confirm_password]):
            messages.error(request, "Please fill in all fields.")
            return render(request, 'User/sign-up.html', context)

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'User/sign-up.html', context)

        if User.objects.filter(school_id=school_id).exists():
            messages.error(request, "School ID already exists.")
            return render(request, 'User/sign-up.html', context)

        # ✅ Create new user
        user = User.objects.create(
            school_id=school_id,
            first_name=first_name,
            last_name=last_name,
            password=password,
            user_type=user_type.capitalize(),
            user_image=user_image if user_image else 'profile_pic/default.png'
        )

        messages.success(request, "Account created successfully! Please log in.")
        return redirect('index')  # ✅ Redirect to index.html (login page)

    return render(request, 'User/sign-up.html', {'currentpage': 'sign-up'})



# ---------------- CLASS MANAGEMENT ---------------- #

def create_class(request):
    if request.method == "POST":
        class_code = request.POST.get("class_code")
        title = request.POST.get("title")
        description = request.POST.get("description")
        upload_icon = request.FILES.get("upload_icon")

        teacher = User.objects.get(school_id=request.session.get("school_id"))

        # Prevent duplicate class codes
        if Class.objects.filter(class_code=class_code).exists():
            messages.error(request, "Class code already exists.")
            # Redirect back to the same page (MyClasses or dashboard)
            previous_page = request.META.get('HTTP_REFERER', '')
            if 'MyClasses' in previous_page:
                return redirect('MyClasses')
            return redirect('dashboard')

        # Create the class
        Class.objects.create(
            class_code=class_code,
            title=title,
            description=description,
            upload_icon=upload_icon,
            teacher=teacher
        )
        messages.success(request, "Class created successfully!")

        # Redirect to the same page where the request came from
        previous_page = request.META.get('HTTP_REFERER', '')
        if 'MyClasses' in previous_page:
            return redirect('MyClasses')
        return redirect('dashboard')

    return redirect('dashboard')

def MyClasses(request):
    school_id = request.session.get('school_id')
    if not school_id:
        messages.warning(request, "Please log in first.")
        return redirect('index')

    teacher = User.objects.filter(school_id=school_id).first()
    classes = Class.objects.filter(teacher=teacher).order_by('-class_id')  # use class_id

    return render(request, 'User/MyClasses.html', {
        'currentpage': 'MyClasses',
        'user': teacher,
        'classes': classes,
    })



def delete_class(request, class_id):
    """Deletes a class created by the teacher and redirects to the appropriate page."""
    school_id = request.session.get('school_id')
    if not school_id:
        messages.warning(request, "Please log in first.")
        return redirect('index')

    # Get class belonging to the teacher
    class_obj = get_object_or_404(Class, pk=class_id, teacher__school_id=school_id)
    class_obj.delete()
    messages.success(request, 'Class deleted successfully!')

    # Redirect based on where the request came from
    referer = request.META.get('HTTP_REFERER', '')
    if 'report' in referer.lower():
        return redirect('report')
    else:
        return redirect('MyClasses')


# ---------------- CLASS DETAILS PAGE ---------------- #

def classDetails(request, class_id):
    # Check if user is logged in
    school_id = request.session.get('school_id')
    if not school_id:
        messages.warning(request, "Please log in first.")
        return redirect('index')

    # Get teacher info
    teacher = get_object_or_404(User, school_id=school_id)

    # Get the class object
    class_obj = get_object_or_404(Class, class_id=class_id, teacher=teacher)

    # Base query for problems
    problems = Problem.objects.filter(class_id=class_obj).order_by('-problem_id')

    # ---- SEARCH AND FILTER FOR PROBLEMS ----
    query = request.GET.get('q', '').strip()
    filter_type = request.GET.get('filter', '').strip()

    # Toggle filter (Assignment / Quiz)
    last_filter = request.session.get('last_filter', '')
    if filter_type == last_filter:
        filter_type = ''
        request.session['last_filter'] = ''
    else:
        request.session['last_filter'] = filter_type

    # Apply search/filter for problems
    if query:
        problems = problems.filter(problem_title__icontains=query)
    if filter_type == 'Assignment':
        problems = problems.filter(problem_type='Assignment')
    elif filter_type == 'Quiz':
        problems = problems.filter(problem_type='Quiz')
    if not query and not filter_type:
        problems = Problem.objects.filter(class_id=class_obj).order_by('-problem_id')

    # ---- STUDENT SEARCH ----
    student_query = request.GET.get('student_search', '').strip()

    students = (
        Enrollment.objects.filter(class_id=class_obj)
        .select_related('student_id')
        .order_by('student_id__first_name')
    )

    # Filter students if search term entered
    if student_query:
        students = students.filter(
            student_id__first_name__icontains=student_query
        ) | students.filter(
            student_id__last_name__icontains=student_query
        )

    return render(request, 'User/classDetails.html', {
        'currentpage': 'MyClasses',
        'user': teacher,
        'class': class_obj,
        'problems': problems,
        'students': students,
        'query': query,
        'filter_type': filter_type,
        'student_query': student_query,
    })




    # ---- ADD PROBLEM------------

def add_problem(request, class_id):
    # Ensure user is logged in
    school_id = request.session.get('school_id')
    if not school_id:
        messages.warning(request, "Please log in first.")
        return redirect('index')

    teacher = get_object_or_404(User, school_id=school_id)
    class_obj = get_object_or_404(Class, class_id=class_id, teacher=teacher)

    if request.method == "POST":
        title = request.POST.get("problem_title", "").strip()
        description = request.POST.get("problem_description", "").strip()
        problem_type = request.POST.get("problem_type", "").strip()
        total_score = request.POST.get("total_score", "").strip()
        time_limit = request.POST.get("time_limit", "").strip()
        due_date = request.POST.get("due_date", "").strip()

        # Test cases
        inputs = [
            request.POST.get(f"input{i}", "").strip() for i in range(1, 4)
        ]
        outputs = [
            request.POST.get(f"output{i}", "").strip() for i in range(1, 4)
        ]

        # Validation
        if not all([title, description, problem_type, total_score, time_limit, due_date]):
            messages.error(request, "Please fill in all fields.")
            return redirect('classDetails', class_id=class_id)

        try:
            total_score = int(total_score)
            time_limit = int(time_limit)
            due_date = datetime.fromisoformat(due_date)
        except ValueError:
            messages.error(request, "Invalid input values.")
            return redirect('classDetails', class_id=class_id)

        # Create Problem
        problem = Problem.objects.create(
            class_id=class_obj,
            teacher_id=teacher,
            problem_title=title,
            problem_description=description,
            problem_type=problem_type,
            total_score=total_score,
            time_limit=time_limit,
            due_date=due_date,
        )

        # Add test cases
        for i in range(3):
            if inputs[i] or outputs[i]:
                ProblemTestCase.objects.create(
                    problem_id=problem,
                    input_data=inputs[i],
                    expected_output=outputs[i]
                )

        messages.success(request, f"Problem '{title}' created successfully!")
        return redirect('classDetails', class_id=class_id)

    return redirect('classDetails', class_id=class_id)

#--------------------------Problem Details---------------------------------#

                #Works for both Students and Teachers

def get_problem_details(request, problem_id):
    """Return problem details as JSON (used in both Teacher and Student modals)."""
    problem = get_object_or_404(Problem, pk=problem_id)
    test_cases = ProblemTestCase.objects.filter(problem_id=problem)

    # Default value
    answered = False

    # Check if the logged-in user is a student and has submitted this problem
    school_id = request.session.get('school_id')
    if school_id:
        user = User.objects.filter(school_id=school_id).first()
        if user and user.user_type == "Student":
            answered = Submission.objects.filter(problem_id=problem, student_id=user).exists()

    # Prepare data
    data = {
        "problem_id": problem.problem_id,
        "title": problem.problem_title,
        "description": problem.problem_description,
        "type": problem.problem_type,
        "score": problem.total_score,
        "time_limit": problem.time_limit,
        "due_date": problem.due_date.strftime("%Y-%m-%d %H:%M"),
        "answered": answered,  # ✅ Student-specific info only if applicable
        "test_cases": [
            {"input": tc.input_data, "output": tc.expected_output} for tc in test_cases
        ]
    }

    return JsonResponse(data)


#----------------------Problem Deletion------------------------------------#

def delete_problem(request, problem_id):
    problem = get_object_or_404(Problem, pk=problem_id)
    class_id = problem.class_id.class_id
    problem.delete()
    messages.success(request, "Problem deleted successfully.")
    return redirect('classDetails', class_id=class_id)

#----------------------Edit Problem-----------------------------------------#
def edit_problem(request, problem_id):
    problem = get_object_or_404(Problem, pk=problem_id)
    class_id = problem.class_id.class_id

    if request.method == "POST":
        title = request.POST.get("problem_title", "").strip()
        description = request.POST.get("problem_description", "").strip()
        problem_type = request.POST.get("problem_type", "").strip()
        total_score = request.POST.get("total_score", "").strip()
        time_limit = request.POST.get("time_limit", "").strip()
        due_date = request.POST.get("due_date", "").strip()

        try:
            problem.problem_title = title
            problem.problem_description = description
            problem.problem_type = problem_type
            problem.total_score = int(total_score)
            problem.time_limit = int(time_limit)
            problem.due_date = datetime.fromisoformat(due_date)
            problem.save()

            # Update only this problem's test cases
            ProblemTestCase.objects.filter(problem_id=problem.problem_id).delete()
            for i in range(3):
                input_data = request.POST.get(f"input{i+1}", "").strip()
                output_data = request.POST.get(f"output{i+1}", "").strip()
                if input_data or output_data:
                    ProblemTestCase.objects.create(
                        problem_id=problem,
                        input_data=input_data,
                        expected_output=output_data
                    )

            messages.success(request, f"Problem '{problem.problem_title}' updated successfully!")
        except Exception as e:
            messages.error(request, f"Update failed: {e}")

    return redirect('classDetails', class_id=class_id)


# ---------- REPORT DASHBOARD ----------  
def report(request):
    if not request.session.get('school_id'):
        messages.warning(request, "Please log in first.")
        return redirect('index')

    user = User.objects.get(school_id=request.session['school_id'])

    # Filter only the teacher’s own classes
    if user.user_type.lower() == 'teacher':
        classes = Class.objects.filter(teacher=user).order_by('class_id')
    else:
        classes = Class.objects.filter(enrollment__student_id=user).distinct().order_by('class_id')

    # Handle search input
    search_query = request.GET.get('search', '').strip()
    selected_class = None

    if search_query:
        selected_class = classes.filter(
            Q(title__icontains=search_query) | Q(class_code__icontains=search_query)
        ).first()

    # Problems and submissions for the selected class
    problems = Problem.objects.filter(class_id__in=classes).select_related('class_id').order_by('problem_id')
    submissions = Submission.objects.select_related(
        'student_id', 'problem_id', 'problem_id__class_id'
    ).filter(problem_id__in=problems).exclude(submission_id__isnull=True)

    # Students in the teacher’s classes
    students = User.objects.filter(
        user_type__iexact='student',
        enrollment__class_id__in=classes
    ).distinct().order_by('school_id')

    # Students enrolled in the selected class
    enrolled_students = []
    if selected_class:
        enrolled_students = students.filter(enrollment__class_id=selected_class).distinct()

    # Counts for summary
    total_students = students.count()
    total_submissions = submissions.count()
    pending_reviews = submissions.filter(score__isnull=True).count()

    context = {
        'user': user,
        'classes': classes,
        'problems': problems,
        'students': students,
        'enrolled_students': enrolled_students,
        'submissions': submissions,
        'selected_class': selected_class,
        'total_students': total_students,
        'total_submissions': total_submissions,
        'pending_reviews': pending_reviews,
        'currentpage': 'report',
        'search_query': search_query,
    }

    return render(request, 'User/report.html', context)


# ---------- DELETE STUDENT ----------
def delete_student(request, school_id):
    student = get_object_or_404(User, school_id=school_id, user_type__iexact='student')
    student.delete()
    messages.success(request, 'Student deleted successfully!')
    return redirect('report')




# ---------------- REVIEW SUBMISSION ---------------- #
def review_submission(request, submission_id):
    submission = get_object_or_404(Submission, submission_id=submission_id)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        feedback = request.POST.get('feedback')
        submission.status = new_status
        submission.feedback = feedback
        submission.save()
        messages.success(request, '✅ Submission review updated successfully!')
        return redirect('report')

    return render(request, 'review_submission.html', {'submission': submission})


# ---------- DELETE SUBMISSION ----------
def delete_submission(request, submission_id):
    submission = get_object_or_404(Submission, submission_id=submission_id)
    submission.delete()
    messages.success(request, 'Student submission deleted successfully!')
    return redirect('report')




#---------------Student Part-------------------------#

#---------------Student Dashboard--------------------#
def StudentDashboard(request):  # for student
    school_id = request.session.get('school_id')

    if not school_id:
        # Redirect to login if not logged in
        messages.warning(request, "Please log in first.")
        return redirect('index')

    student = User.objects.filter(school_id=school_id).first()

    # Get all classes the student is enrolled in
    enrolled_classes = Class.objects.filter(
        enrollment__student_id=student
    ).order_by('-class_id').distinct()

    return render(request, 'Students/StudentDashboard.html', {
        'currentpage': 'StudentDashboard',
        'user': student,
        'classes': enrolled_classes,
    })


#---------------Student Enrolled Classes----------------#
def StudentClass(request):
    school_id = request.session.get('school_id')
    if not school_id:
        messages.warning(request, "Please log in first.")
        return redirect('index')

    student = User.objects.filter(school_id=school_id).first()

    # Get classes the student is enrolled in
    enrolled_classes = Class.objects.filter(
        enrollment__student_id=student
    ).order_by('-class_id').distinct()

    return render(request, 'Students/StudentClass.html', {
        'currentpage': 'StudentClass',
        'user': student,
        'classes': enrolled_classes,
    })

# ---------------- JOIN CLASS (STUDENT) ---------------- #
def join_class(request):
    if request.method == "POST":
        school_id = request.session.get('school_id')
        if not school_id:
            messages.warning(request, "Please log in first.")
            return redirect('index')

        student = User.objects.get(school_id=school_id)
        class_code = request.POST.get('class_code', '').strip()

        if not class_code:
            messages.error(request, "Please enter a class code.")
            return redirect('StudentClass')

        try:
            class_obj = Class.objects.get(class_code=class_code)
        except Class.DoesNotExist:
            messages.error(request, "Class not found. Please check the code.")
            return redirect('StudentClass')

        # Check if already enrolled
        if Enrollment.objects.filter(class_id=class_obj, student_id=student).exists():
            messages.warning(request, f"You are already enrolled in '{class_obj.title}'.")
            return redirect('StudentClass')

        # Create enrollment
        Enrollment.objects.create(class_id=class_obj, student_id=student)
        messages.success(request, f"Successfully joined '{class_obj.title}'!")
        return redirect('StudentClass')

    # If GET request, just redirect
    return redirect('StudentClass')

#---------------STUDENT CLASS DETAILS PAGE---------------------#

def student_class_details(request, class_id):
    # Make sure the student is logged in
    school_id = request.session.get('school_id')
    if not school_id:
        messages.warning(request, "Please log in first.")
        return redirect('index')

    # Get student and class instance
    enrollment = get_object_or_404(Enrollment, student_id__school_id=school_id, class_id=class_id)
    student = enrollment.student_id
    class_instance = get_object_or_404(Class, pk=class_id)

    # Search and filter handling
    query = request.GET.get('q', '').strip()
    filter_type = request.GET.get('filter', '').strip()

    problems = Problem.objects.filter(class_id=class_instance).order_by('-problem_id')
    if query:
        problems = problems.filter(problem_title__icontains=query)
    if filter_type:
        problems = problems.filter(problem_type=filter_type)

    # Prepare problems + submission info
    problem_data = []
    for p in problems:
        submission = Submission.objects.filter(
            student_id=student,
            problem_id=p
            
        ).order_by('-submission_id').first()

        half_score = p.total_score / 2

        problem_data.append({
            'problem': p,
            'score': submission.score if submission else None,
            'answered': submission is not None,
            'half_score': half_score, 
        })

    context = {
        'user': student,                     # ✅ Added this for StudentSidebar
        'class': class_instance,
        'problems': problem_data,
        'query': query,
        'filter_type': filter_type,
        'currentpage': 'StudentClass',       # ✅ Keeps sidebar highlighting correct
    }

    return render(request, 'Students/student_class_details.html', context)

#------------------Unenroll Function--------------------#
def unenroll_class(request, class_id):
    school_id = request.session.get('school_id')
    if not school_id:
        messages.warning(request, "Please log in first.")
        return redirect('index')

    student = get_object_or_404(User, school_id=school_id)
    enrollment = Enrollment.objects.filter(class_id=class_id, student_id=student).first()
    if enrollment:
        enrollment.delete()
        messages.success(request, "You have unenrolled from the class.")
    else:
        messages.error(request, "You are not enrolled in this class.")

    return redirect('StudentClass')

# External code runner API
PISTON_URL = "https://emkc.org/api/v2/piston/execute"

# ---------------- PLAYGROUND PAGE ---------------- #
def playground(request, problem_id):
    """Renders the coding playground for a student"""
    school_id = request.session.get('school_id')
    if not school_id:
        messages.warning(request, "Please log in first.")
        return redirect('index')

    student = get_object_or_404(User, school_id=school_id)
    problem = get_object_or_404(Problem, pk=problem_id)

    return render(request, 'Students/StudentPlayGround.html', {
        'user': student,
        'problem': problem
    })


# ---------------- RUN & CHECK CODE ---------------- #
@csrf_exempt
def run_playground_code(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method."}, status=400)

    tmp_dir = None
    try:
        data = json.loads(request.body)
        code = data.get("code", "")
        language = (data.get("language", "python") or "python").lower()
        check_mode = data.get("check_mode", False)
        problem_id = data.get("problem_id")
        stdin_data = data.get("stdin", "")

        if not code.strip():
            return JsonResponse({"error": "Code cannot be empty."}, status=400)

        problem = get_object_or_404(Problem, pk=problem_id)
        tmp_dir = tempfile.mkdtemp(prefix="code_run_")

        extensions = {"python": "main.py", "c": "main.c", "cpp": "main.cpp", "java": "Main.java"}
        source_path = os.path.join(tmp_dir, extensions.get(language, "main.py"))

        with open(source_path, "w", encoding="utf-8") as f:
            f.write(code)

        # ✅ Test case checking mode
        if check_mode:
            testcases = list(ProblemTestCase.objects.filter(problem_id=problem))
            total_cases = len(testcases)
            results = []
            passed_count = 0

            for i, tc in enumerate(testcases, start=1):
                expected = (tc.expected_output or "").strip()
                raw_input = (tc.input_data or "").strip()

                exec_res = execute_source(language, source_path, stdin_data=raw_input + "\n")

                if exec_res.get("error"):
                    results.append(f"❌ Test {i}: {exec_res['error']}")
                    continue

                output = (exec_res.get("stdout") or "").strip()

                # ✅ Hidden test case logic
                is_hidden = (
                    (total_cases == 1) or
                    (total_cases == 2 and i == 2) or
                    (total_cases == 3 and i == 3)
                )

                if is_hidden:
                    if output == expected:
                        results.append(f"✅ Test {i}: Passed (Hidden Case)")
                        passed_count += 1
                    else:
                        results.append(f"❌ Test {i}: Failed (Hidden Case)")
                else:
                    if output == expected:
                        results.append(f"✅ Test {i}: Passed")
                        passed_count += 1
                    else:
                        results.append(
                            f"❌ Test {i}: Failed\nInput: {raw_input}\nExpected: {expected}\nGot: {output}"
                        )

            return JsonResponse({
                "result_summary": "\n".join(results),
                "total_score": passed_count * 10,
            })

        # Manual Run Mode
        exec_res = execute_source(language, source_path, stdin_data=stdin_data + "\n")
        return JsonResponse({
            "output": exec_res.get("stdout", "No output."),
            "stderr": exec_res.get("stderr", ""),
            "compile_error": exec_res.get("compile_error", ""),
            "error": exec_res.get("error", "")
        })

    except Exception as e:
        return JsonResponse({"error": f"Server error: {str(e)}"}, status=500)
    finally:
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


@csrf_exempt
def submit_problem(request, problem_id):
    """
    Handles code submission from students.
    Runs test cases, hides hidden ones, gives score, and returns JSON response for modal display.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method."}, status=400)

    try:
        data = json.loads(request.body)
        code = data.get("code", "")
        language = data.get("language", "python")
    except Exception:
        return JsonResponse({"success": False, "message": "Invalid JSON received."}, status=400)

    problem = get_object_or_404(Problem, pk=problem_id)
    student = get_object_or_404(User, pk=request.session["school_id"])

    test_cases = ProblemTestCase.objects.filter(problem_id=problem)
    total_cases = test_cases.count()
    passed_cases = 0
    score = 0
    results = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        ext_map = {"python": ".py", "c": ".c", "cpp": ".cpp", "java": ".java"}
        ext = ext_map.get(language)
        if not ext:
            return JsonResponse({"success": False, "message": "Unsupported language selected."}, status=400)

        source_path = os.path.join(tmp_dir, f"Main{ext}")
        with open(source_path, "w") as src:
            src.write(code)

        for i, tc in enumerate(test_cases, start=1):
            raw_input = (tc.input_data or "").strip()
            expected = (tc.expected_output or "").strip()

            try:
                exec_res = execute_source(language, source_path, stdin_data=raw_input + ("\n" if raw_input else "\n"))

                # Handle compile/runtime errors
                if exec_res.get("compile_error") or exec_res.get("timeout") or exec_res.get("stderr"):
                    results.append(f"❌ Test {i}: Error\n{exec_res.get('compile_error') or exec_res.get('stderr') or exec_res.get('timeout')}")
                    continue

                out = (exec_res.get("stdout") or "").strip()

                # ✅ Hidden test case logic
                # Hide details for last test case or based on count rules
                is_hidden = (
                    (total_cases == 1) or
                    (total_cases == 2 and i == 2) or
                    (total_cases == 3 and i == 3)
                )

                if out == expected:
                    passed_cases += 1
                    score += 10
                    if is_hidden:
                        results.append(f"✅ Test {i}: Passed (Hidden Case)")
                    else:
                        results.append(f"✅ Test {i}: Passed")
                else:
                    if is_hidden:
                        results.append(f"❌ Test {i}: Failed (Hidden Case)")
                    else:
                        results.append(f"❌ Test {i}: Failed\nInput: {raw_input}\nExpected: {expected}\nGot: {out}")

            except Exception as e:
                results.append(f"❌ Test {i}: Exception\n{str(e)}")
                continue

    # ✅ Save submission
    Submission.objects.create(
        problem_id=problem,
        student_id=student,
        code=code,
        score=score,
        submitted_at=timezone.now()
    )

    result_summary = "\n".join(results) + f"\n\n{passed_cases}/{total_cases} test cases passed. Score: {score}"
    redirect_url = reverse("student_class_details", args=[problem.class_id.class_id])

    return JsonResponse({
        "success": True,
        "result_summary": result_summary,
        "score": score,
        "passed_cases": passed_cases,
        "total_cases": total_cases,
        "redirect_url": redirect_url
    })


def count_expected_inputs(test_output):
    """
    Estimate number of inputs based on output prompts.
    """
    if not test_output:
        return 0
    num_prompts = test_output.count("Enter num")
    if num_prompts == 0:
        num_prompts = test_output.count("\n") + 1
    return num_prompts

# Helper to find executable (cross-platform)
def find_executable(names):
    for n in names:
        path = shutil.which(n)
        if path:
            return path
    return None

def execute_source(language, source_path, stdin_data="", timeout_sec=5):
    """Executes code safely via Piston API and always returns JSON-safe output."""
    PISTON_URL = "https://emkc.org/api/v2/piston/execute"

    with open(source_path, "r", encoding="utf-8") as f:
        code = f.read()

    # Correct language mapping for Piston
    lang_map = {
        "python": "python3",
        "python3": "python3",
        "c": "c",
        "cpp": "cpp",
        "java": "java",
    }
    lang = lang_map.get(language.lower(), "python3")

    payload = {
        "language": lang,
        "version": "*",
        "files": [{"name": "main", "content": code}],
        "stdin": stdin_data or "",
    }

    try:
        res = requests.post(PISTON_URL, json=payload, timeout=timeout_sec + 2)

        # Ensure JSON response
        if "application/json" not in res.headers.get("Content-Type", ""):
            return {
                "stdout": "",
                "stderr": "",
                "compile_error": "",
                "error": f"⚠️ Non-JSON from Piston ({res.status_code}): {res.text[:200]}"
            }

        data = res.json()

        if res.status_code != 200:
            return {
                "stdout": "",
                "stderr": "",
                "compile_error": "",
                "error": f"⚠️ Piston API error {res.status_code}: {data}"
            }

        # Defensive key access
        run_data = data.get("run", {})
        compile_data = data.get("compile", {})

        return {
            "stdout": run_data.get("stdout", ""),
            "stderr": run_data.get("stderr", ""),
            "compile_error": compile_data.get("stderr", ""),
            "error": "",
        }

    except requests.Timeout:
        return {"stdout": "", "stderr": "", "compile_error": "", "error": "⏱️ Timed out."}
    except requests.RequestException as e:
        return {"stdout": "", "stderr": "", "compile_error": "", "error": f"🌐 Request error: {e}"}
    except Exception as e:
        return {"stdout": "", "stderr": "", "compile_error": "", "error": f"⚠️ Unexpected: {e}"}

