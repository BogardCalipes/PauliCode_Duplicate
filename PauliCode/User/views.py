from django.shortcuts import render, redirect, get_object_or_404
from .models import User, Class, Problem, Enrollment, ProblemTestCase, Submission
from django.contrib import messages
from datetime import datetime
from django.http import JsonResponse 
import json, requests, subprocess, tempfile, os   
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.urls import reverse
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
    return render(request, 'User/index.html')



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

        context = {
            'first_name': first_name,
            'last_name': last_name,
            'school_id': school_id,
            'user_type': user_type,
        }

        if not all([first_name, last_name, school_id, user_type, password, confirm_password]):
            messages.error(request, "Please fill in all fields.")
            return render(request, 'User/sign-up.html', context)

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'User/sign-up.html', context)

        if User.objects.filter(school_id=school_id).exists():
            messages.error(request, "School ID already exists.")
            return render(request, 'User/sign-up.html', context)

        User.objects.create(
            school_id=school_id,
            first_name=first_name,
            last_name=last_name,
            password=password,
            user_type=user_type.capitalize()
        )
        messages.success(request, "Account created successfully!")
        return render(request, 'User/sign-up.html', {'redirect': True})

    return render(request, 'User/sign-up.html')


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
    school_id = request.session.get('school_id')
    if not school_id:
        messages.warning(request, "Please log in first.")
        return redirect('index')

    class_obj = get_object_or_404(Class, class_id=class_id, teacher__school_id=school_id)
    class_obj.delete()
    messages.success(request, "Class deleted successfully!")
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

    try:
        data = json.loads(request.body)
        code = data.get("code", "")
        language = data.get("language", "python")
        check_mode = data.get("check_mode", False)
        problem_id = data.get("problem_id")
        stdin_data = data.get("stdin", "")

        if not code.strip():
            return JsonResponse({"error": "Code cannot be empty."}, status=400)

        problem = get_object_or_404(Problem, pk=problem_id)

        # Save code temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as tmp_file:
            tmp_file.write(code.encode("utf-8"))
            tmp_path = tmp_file.name

        if check_mode:
            testcases = ProblemTestCase.objects.filter(problem_id=problem)
            results = []
            passed_count = 0

            for idx, tc in enumerate(testcases, start=1):
                # ✅ Clean stdin and add safe dummy fallback values
                stdin_data = (tc.input_data or "").strip()
                stdin_lines = [line.strip() for line in stdin_data.splitlines() if line.strip() != ""]

                # Add at least 10 dummy numeric lines to prevent EOF/ValueError
                while len(stdin_lines) < 10:
                    stdin_lines.append("0")

                safe_stdin = "\n".join(stdin_lines) + "\n"

                try:
                    process = subprocess.Popen(
                        ["python", tmp_path],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )

                    out, err = process.communicate(safe_stdin, timeout=5)
                    out = out.strip()
                    expected = (tc.expected_output or "").strip()

                    # ✅ Normalize whitespace and case for fair comparison
                    def normalize_output(text):
                        return " ".join(text.strip().split()).lower()

                    norm_out = normalize_output(out)
                    norm_expected = normalize_output(expected)

                    if err:
                        results.append(f"❌ Test {idx}: Failed\nExpected: {expected}\nGot: {err}")
                    elif norm_out == norm_expected:
                        results.append(f"✅ Test {idx}: Passed")
                        passed_count += 1
                    else:
                        results.append(f"❌ Test {idx}: Failed\nExpected: {expected}\nGot: {out}")


                except subprocess.TimeoutExpired:
                    results.append(f"⚠️ Test {idx}: Timeout (5s limit)")
                except Exception as e:
                    results.append(f"⚠️ Test {idx}: Error - {str(e)}")

            total_score = passed_count * 10
            result_summary = (
                "\n".join(results)
                + f"\n\n{passed_count}/{len(testcases)} test cases passed."
            )

            return JsonResponse({
                "result_summary": result_summary,
                "total_score": total_score,
            })

        else:
            # Normal run mode
            stdin_cleaned = (stdin_data or "").strip()
            stdin_lines = [line.strip() for line in stdin_cleaned.splitlines() if line.strip() != ""]

            # Add fallback dummy input
            while len(stdin_lines) < 10:
                stdin_lines.append("0")

            safe_stdin = "\n".join(stdin_lines) + "\n"

            try:
                result = subprocess.run(
                    ["python", tmp_path],
                    input=safe_stdin,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                output = result.stdout.strip()
                error = result.stderr.strip()

                return JsonResponse({
                    "output": output if output else error or "No output."
                })

            except subprocess.TimeoutExpired:
                return JsonResponse({"error": "Execution timed out (5 seconds)."})
            except Exception as e:
                return JsonResponse({"error": str(e)})

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Server error: {str(e)}"}, status=500)
    finally:
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)




@csrf_exempt
def submit_problem(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method."}, status=400)

    try:
        data = json.loads(request.body)
        code = data.get("code", "")
        problem_id = data.get("problem_id")
        language = data.get("language", "python")

        if not code.strip():
            return JsonResponse({"success": False, "message": "Code cannot be empty."}, status=400)

        # ✅ Validate problem
        problem = get_object_or_404(Problem, pk=problem_id)

        # ✅ Get logged-in student
        student_id = request.session.get('school_id')
        if not student_id:
            return JsonResponse({"success": False, "message": "User not logged in."}, status=403)
        student = get_object_or_404(User, school_id=student_id)

        # ✅ Retrieve test cases for the problem
        test_cases = ProblemTestCase.objects.filter(problem_id=problem)
        if not test_cases.exists():
            return JsonResponse({"success": False, "message": "No test cases found for this problem."}, status=404)

        # ✅ Save student code temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as temp_file:
            temp_file.write(code.encode('utf-8'))
            temp_path = temp_file.name

        # ✅ Initialize counters
        score = 0
        passed_cases = 0
        total_cases = test_cases.count()

        # ✅ Loop through each test case
        for tc in test_cases:
            try:
                result = subprocess.run(
                    ["python", temp_path],
                    input=tc.input_data,
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                output = result.stdout.strip()
                error = result.stderr.strip()

                # ✅ Check correctness — +10 for each correct test case
                if not error and output == tc.expected_output.strip():
                    passed_cases += 1
                    score += 10
                else:
                    continue

            except subprocess.TimeoutExpired:
                continue

        # ✅ Remove temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)

        # ✅ Optional: Cap score at 100
        score = min(score, 100)

        # ✅ Always save submission even if score = 0
        Submission.objects.create(
            problem_id=problem,
            student_id=student,
            code=code,
            score=score,
            submitted_at=timezone.now()
        )

        # ✅ Prepare response details
        message = f"{passed_cases}/{total_cases} test cases passed. Score: {score}"
        success = passed_cases == total_cases

        # ✅ Redirect URL
        redirect_url = reverse("student_class_details", args=[problem.class_id.class_id])

        return JsonResponse({
            "success": True,  # Always true to allow submission
            "message": message,
            "score": score,
            "passed_cases": passed_cases,
            "total_cases": total_cases,
            "redirect_url": redirect_url
        })

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON received."}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Server error: {str(e)}"}, status=500)

