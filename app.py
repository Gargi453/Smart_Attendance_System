
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
import pandas as pd
from datetime import date
import io
import requests
import socket
import time


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://127.0.0.1:5501"}}) #allow frontend to commuincate with bancked

# Safe connection function
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="W7301@jqir#",
        database="attendance_system"
    )



# Replace with your STATIC ESP IP
esp_ip = None
FLASK_PORT = 5000

# get flask ip 
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn’t actually connect — just used to find the right interface
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

# find esp on network by scanning
def find_esp_ip():
    global esp_ip
    local_ip = get_local_ip()
    subnet = ".".join(local_ip.split(".")[:3])

    for i in range(1, 255):
        ip = f"{subnet}.{i}"
        try:
            response = requests.get(f"http://{ip}/ping", timeout=0.3)
            if response.status_code == 200 and response.text.strip().lower() == "pong":
                esp_ip = ip
                print(f"✅ ESP found at {esp_ip}")
                return esp_ip
        except:
            continue
    print("❌ ESP not found in subnet.")
    return None

# check if esp is alive by sending ping to esp and getting pong  
def is_esp_alive():
    global esp_ip
    if not esp_ip:
        esp_ip = find_esp_ip()
    if not esp_ip:
        return False

    try:
        response = requests.get(f"http://{esp_ip}/ping", timeout=2)
        return response.status_code == 200
    except:
        return False

# after finding esp we send local ip to esp for post request from esp
def send_ip_to_esp():
    global esp_ip
    flask_ip = get_local_ip()
    esp_ip = find_esp_ip()  # 🔍 Discover ESP dynamically

    if not esp_ip:
        print("❌ ESP not found on network — cannot send Flask IP.")
        return False

    esp_url = f"http://{esp_ip}/receive_flask_ip"
    headers = {"Content-Type": "application/json"}
    payload = {"ip": flask_ip}

    for attempt in range(1, 11):
        try:
            print(f"📡 Attempt {attempt}: Sending Flask IP {flask_ip} to ESP at {esp_url}")
            response = requests.post(esp_url, json=payload, headers=headers, timeout=(2, 2))
            if response.status_code == 200:
                print(f"✅ ESP acknowledged Flask IP on attempt {attempt}")
                return True
            else:
                print(f"❌ Attempt {attempt}: ESP responded with status {response.status_code}")
        except Exception as e:
            print(f"❌ Attempt {attempt}: Failed to send Flask IP — {e}")

        time.sleep(2 if attempt < 5 else 5)

    print("❌ Failed to send Flask IP after all attempts.")
    return False

def check_esp_flask_ip():
    global esp_ip
    if not esp_ip:
        esp_ip = find_esp_ip()
    if not esp_ip:
        print("❌ ESP not found for verifying Flask IP.")
        return None

    try:
        response = requests.get(f"http://{esp_ip}/verify_ip", timeout=2)
        return response.json()
    except Exception as e:
        print("❌ Failed to verify IP from ESP:", e)
        return None


# route for student registration
@app.route('/register/student', methods=['POST'])
def register_student():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        data = request.json
        query = "INSERT INTO students (username, prn, mobile, email, password, fingerprint_id, year) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        values = (data['username'], data['prn'], data['mobile'], data['email'], data['password'], data['fingerprint_id'], data['year'])
        
        cursor.execute(query, values)
        conn.commit()
        return jsonify({"message": "Student Registered Successfully"}), 201
        
        # Route for Teacher Registration
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except: pass

# route for teacher registration
@app.route('/register/teacher', methods=['POST'])
def register_teacher():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        data = request.json
        query = "INSERT INTO teachers (username, teacher_id, mobile, email, password) VALUES (%s, %s, %s, %s, %s)"
        values = (data['username'], data['teacher_id'], data['mobile'], data['email'], data['password'])
    
        cursor.execute(query, values)
        conn.commit()
        
        for subject in data['subjects']:
            query = "INSERT INTO teacher_lectures (teacher_id, subject_name) VALUES (%s, %s)"
            cursor.execute(query, (data['teacher_id'], subject))
        conn.commit()
        
        return jsonify({"message": "Teacher Registered Successfully"}), 201
        
        # Route for Login (Student & Teacher)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except: pass

# route for login student,teacher,admin
@app.route('/login', methods=['POST'])
def login():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        data = request.json
        username = data['username']
        password = data['password']
        role = data.get('role')
    
        if not role:
            return jsonify({"error": "Role selection is required"}), 400
        
        if role == "student":
            cursor.execute("SELECT id, username, email FROM students WHERE username=%s AND password=%s", (username, password))
            student = cursor.fetchone()
            if student:
                return jsonify({"message": "Student Login Successful", "role": "student", "user_id": student["id"]}), 200
    
        elif role == "teacher":
            cursor.execute("SELECT teacher_id, username, email FROM teachers WHERE username=%s AND password=%s", (username, password))
            teacher = cursor.fetchone()
            if teacher:
                return jsonify({"message": "Teacher Login Successful", "role": "teacher", "user_id": teacher["teacher_id"]}), 200
            
        elif role =="admin":
            cursor.execute("SELECT id,username,email from admin where username = %s and password=%s",(username,password))
            admin= cursor.fetchone()
            if admin:
                return jsonify({
                    "message":"Admin Login Successful",
                    "role":"admin",
                    "user_id":admin["id"]
                }),200
            conn.commit()
        return jsonify({"error": "Invalid Credentials or Role Mismatch"}), 401
            
        # route : get teacher dashboard data
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except: pass

# route for teacher dashboard data
@app.route('/get_teacher_dashboard',methods=['GET'])
def get_teacher_dashboard():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        teacher_id = request.args.get('teacher_id')
        
        cursor.execute("SELECT username, email from teachers where teacher_id = %s",(teacher_id,))
        teacher= cursor.fetchone()
        if not teacher:
            return jsonify({"error":"Invalid teacher ID"}),400
        teacher_name = teacher['username']
    
        # Get subjects taught by teacher from teacher_lectures
        cursor.execute("SELECT subject_name FROM teacher_lectures WHERE teacher_id = %s", (teacher_id,))
        subject_rows = cursor.fetchall()
        subjects = [row['subject_name'] for row in subject_rows]
        if not subjects:
            return jsonify({"error":"No subjects found for this teacher"}),400
        
        
        format_str = ','.join(['%s'] * len(subjects))
    
        today = date.today()
        subject_metrics=[]
        first_day = today.replace(day=1)
    
        for subject in subjects:
            # Total enrolled students in this subject
            cursor.execute("""
                 SELECT COUNT(*) as total_students from students
                           where year = ( select year from subjects where subject_name=%s)
               """,(subject,))
            total_students = cursor.fetchone()['total_students']

            #Total lectures done for the subject
            cursor.execute("""
                SELECT COUNT(DISTINCT attendance_date) as total_lectures from attendance
                           where subject_name = %s
             """,(subject,))
            total_lectures = cursor.fetchone()['total_lectures']
    
            # Today's attendance
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) as present
                FROM attendance 
                WHERE subject_name = %s AND attendance_date = %s
            """, (subject, today))
            today_data = cursor.fetchone()
            today_total = today_data['total']
            today_present = today_data['present'] or 0
    
            # Monthly attendance %
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) as present
                FROM attendance 
                WHERE subject_name = %s
                AND MONTH(attendance_date) = MONTH(CURDATE())
                AND YEAR(attendance_date) = YEAR(CURDATE())
            """, (subject,))
            month_data = cursor.fetchone()
            month_total = month_data['total']
            month_present = month_data['present'] or 0
            monthly_avg = round((month_present / month_total) * 100, 2) if month_total else 0
    
            subject_metrics.append({
                'subject_name': subject,
                'total_students': total_students,
                'today_total': today_total,
                'today_present': today_present,
                'monthly_average': monthly_avg,
                'total_lectures': total_lectures
            })
        # Get 10 most recent attendance entries for subjects taught by this teacher
        cursor.execute(f"""
            SELECT attendance_date, subject_name
            FROM attendance
            WHERE subject_name IN ({format_str})
            GROUP BY attendance_date, subject_name
            ORDER BY attendance_date DESC
            LIMIT 10
        """, tuple(subjects))
        
        logs_data = cursor.fetchall()
        recent_logs = []
        
        for row in logs_data:
            attendance_date = row['attendance_date']
            subject = row['subject_name']
        
            # Get present count
            cursor.execute("""
                SELECT COUNT(*) as present_count
                FROM attendance
                WHERE subject_name = %s AND attendance_date = %s AND status = 'Present'
            """, (subject, attendance_date))
            present_count = cursor.fetchone()['present_count']
        
            # Get year of the subject
            cursor.execute("SELECT year FROM subjects WHERE subject_name = %s", (subject,))
            subject_year = cursor.fetchone()
            if subject_year:
                year = subject_year['year']
                cursor.execute("SELECT COUNT(*) as total_students FROM students WHERE year = %s", (year,))
                total_students = cursor.fetchone()['total_students']
                absent_count = total_students - present_count
            else:
                absent_count = 0
        
            recent_logs.append({
                "date": attendance_date.strftime('%Y-%m-%d'),
                "subject": subject,
                "present": present_count,
                "absent": absent_count
            })

          
    
    
    
        return jsonify({
                'teacher_name': teacher_name,
                'subject_summary': subject_metrics,
                "recent_logs": recent_logs
            })
        
        
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except: pass

# download attendance in excel sheet
@app.route("/download_attendance_excel", methods=["GET"])
def download_attendance_excel():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        teacher_id = request.args.get("teacher_id")
        subject_name = request.args.get("subject_name")
    
        if not teacher_id or not subject_name:
            return jsonify({"error": "Missing teacher_id or subject"}), 400
    
        # conn = mysql.connector()
        # cursor = conn.cursor(dictionary=True)
        # Get all students linked to this lecture's year
        cursor.execute("""
            SELECT DISTINCT s.id AS student_id, s.username 
            FROM students s
            JOIN attendance a ON s.id = a.student_id
            WHERE a.subject_name = %s
        """, (subject_name,))
        students = cursor.fetchall()
    
        if not students:
            return jsonify({"error": "No attendance data found for this subject."}), 404
    
        student_dict = {student["student_id"]: student["username"] for student in students}
        student_ids = tuple(student_dict.keys())
    
        # Get all unique dates for that subject
        cursor.execute("""
            SELECT DISTINCT attendance_date FROM attendance
            WHERE subject_name = %s
            ORDER BY attendance_date
        """, (subject_name,))
        dates = [row["attendance_date"] for row in cursor.fetchall()]
    
        # Create empty DataFrame structure
        df = pd.DataFrame(columns=["Username"] + [date.strftime("%Y-%m-%d") for date in dates])
    
        # Fill DataFrame
        for student_id, username in student_dict.items():
            row = {"Username": username}
            for date in dates:
                cursor.execute("""
                    SELECT status FROM attendance
                    WHERE student_id = %s AND attendance_date = %s AND subject_name = %s
                """, (student_id, date, subject_name))
                result = cursor.fetchone()
                row[date.strftime("%Y-%m-%d")] = result["status"] if result else "Absent"
            df = df._append(row, ignore_index=True)
    
        # Save to Excel in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Attendance Report")
    
        output.seek(0)
    
        # Download as Excel file
        filename = f"{subject_name}_attendance_report_{date.strftime('%Y%m%d%H%M%S')}.xlsx"
        return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             as_attachment=True, download_name=filename)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except: pass

# get teacher subjects
@app.route('/get_teacher_subjects', methods=['GET'])
def get_teacher_subjects():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        teacher_id = request.args.get('teacher_id')
    
        if not teacher_id:
            return jsonify({"error": "Teacher ID is required"}), 400
    
        cursor.execute("SELECT subject_name FROM teacher_lectures WHERE teacher_id = %s", (teacher_id,))
        result = cursor.fetchall()
    
        # print("database result:,",result)
        if not result:
            return jsonify({"error": "No subjects found for this teacher"}), 404
    
        # subjects = [row["subject_name"] for row in result]  
        # print("Subjects being sent:", subjects)     debugging steps
    
        subjects = [row["subject_name"] for row in result]
    
        return jsonify({"subjects": subjects})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except: pass

# route for view attendance
@app.route('/view_attendance_data')
def view_attendance_data():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        teacher_id = request.args.get("teacher_id")
        subject = request.args.get("subject")
        from_date = request.args.get("from_date")
        to_date = request.args.get("to_date")
    
        if not teacher_id or not subject:
            return jsonify({"error": "Missing teacher_id or subject"}), 400
    
        try:
            # Get all students for that subject/year
            cursor.execute("""
                SELECT DISTINCT s.id AS student_id, s.username
                FROM students s
                JOIN attendance a ON s.id = a.student_id
                WHERE a.subject_name = %s
            """, (subject,))
            students = cursor.fetchall()
    
            if not students:
                return jsonify({"error": "No students found for this subject"}), 404
    
            # Get unique dates for that subject
            date_query = """
                SELECT DISTINCT attendance_date FROM attendance
                WHERE subject_name = %s
            """
            params = [subject]
    
            if from_date and to_date:
                date_query += " AND attendance_date BETWEEN %s AND %s"
                params.extend([from_date, to_date])
    
            cursor.execute(date_query, tuple(params))
            raw_dates = cursor.fetchall()
            dates = sorted([d["attendance_date"].strftime('%Y-%m-%d') for d in raw_dates])
            

            if from_date and to_date:
                date_query += " AND attendance_date BETWEEN %s AND %s"
                params.extend([from_date, to_date])
            elif from_date:
                date_query += " AND attendance_date >= %s"
                params.append(from_date)
            elif to_date:
                date_query += " AND attendance_date <= %s"
                params.append(to_date)
        

            # Prepare attendance dictionary
            attendance_data = []
    
            for student in students:
                student_id = student["student_id"]
                username = student["username"]
    
                cursor.execute("""
                    SELECT attendance_date, status FROM attendance
                    WHERE student_id = %s AND subject_name = %s
                """, (student_id, subject))
                records = cursor.fetchall()
    
                # Convert keys (dates) to strings
                record_dict = {r["attendance_date"].strftime('%Y-%m-%d'): r["status"] for r in records}
    
                # attendance_data.append({
                #     "username": username,
                #     **record_dict  # spread each date:status as flat keys
                # })
    
                # attendance percentage calculation4
                total = len(dates)
                present = sum(1 for d in dates if record_dict.get(d) == "Present")
                percentage = round((present / total) * 100, 2) if total > 0 else 0.0
    
                data_row = {"username": username, "percentage": percentage}
                data_row.update(record_dict)
                attendance_data.append(data_row)
    
                # print("DATES :",dates)
                # print("Student attendance",attendance_data)
    
            return jsonify({
                "dates":dates,
                "attendance":attendance_data
            })
    
        except Exception as e:
                return jsonify({"error": str(e)})
        
        #  route for student dashboard
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except: pass

# route for record attendance in database
@app.route("/record_attendance", methods=["POST"])
def record_attendance():
    try:
        data = request.get_json()
        fingerprint_id = data.get("fingerprint_id")
        subject = data.get("subject","").strip()  # subject now comes from JSON payload

        if not fingerprint_id or not subject:
            return jsonify({"success": False, "message": "Missing fingerprint_id or subject"}), 400

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        #  Get student by fingerprint_id
        cursor.execute("SELECT id, username FROM students WHERE fingerprint_id = %s", (fingerprint_id,))
        student = cursor.fetchone()
        cursor.nextset()  # <-- clears out any unread result if present

        if not student:
            return jsonify({"success": False, "message": "Student not found"}), 404
        
        

        student_id = student['id']
        today = date.today().strftime("%Y-%m-%d")
       
        # Check if attendance already exists
        
        cursor.execute("""
            SELECT id FROM attendance
            WHERE student_id = %s AND subject_name = %s AND attendance_date = %s
        """, (student_id, subject, today))
        existing = cursor.fetchone()

        if existing:
            return jsonify({
                "success": True,
                "message": "Attendance already marked.",
                "username": student["username"]
            }), 200

        #  Insert new attendance
        cursor.execute("""
            INSERT INTO attendance (student_id, subject_name, attendance_date, status)
            VALUES (%s, %s, %s, 'Present')
        """, (student_id, subject, today))
        conn.commit()

        return jsonify({
            "success": True,
            "message": "Attendance recorded successfully.",
            "username": student["username"]
        }), 200

    except Exception as e:
        print("Error in /record _attendance",str(e))
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass



# route for student dashobard
@app.route('/get_student_dashboard', methods=['GET'])
def get_student_dashboard():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        student_id = request.args.get('student_id')
    
        if not student_id:
            return jsonify({"error": "Student ID is required"}), 400
    
        # Fetch student info
        cursor.execute("SELECT username, email ,year FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
    
        if not student:
            return jsonify({"error": "Student not found"}), 404
    
        # get subjects based on students year
        cursor.execute("SELECT subject_name from subjects where year = %s",(student['year'],))
        subjects= [row['subject_name'] for row in cursor.fetchall()]
        
    #    Fetch trend data (datewise attendance %)
        cursor.execute("""
               SELECT attendance_date, 
                      COUNT(*) as total, 
                      SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present
               FROM attendance
               WHERE student_id = %s
               GROUP BY attendance_date
               ORDER BY attendance_date ASC
        """, (student_id,))
        trend_rows = cursor.fetchall()

        trend = [{
            "attendance_date": row["attendance_date"].strftime('%Y-%m-%d'),
            "present": row["present"],
            "total": row["total"]
        } for row in trend_rows]
        

        return jsonify({
                "student":{
                    "username":student["username"],
                    "email":student["email"]
                },
                "subjects":subjects,
                "trend":trend
            })
   
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except: pass

# route for student attendnace summary
@app.route('/get_student_attendance_summary', methods=['GET'])
def get_student_attendance_summary():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        student_id = request.args.get('student_id')
    
        if not student_id:
            return jsonify({'error': 'student_id required'}), 400
    
        cursor.execute("SELECT year FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
        if not student:
            return jsonify({"error": "Student not found"}), 400
    
        student_year = student['year']
    
        cursor.execute("SELECT subject_name FROM subjects WHERE year = %s", (student_year,))
        subjects = cursor.fetchall()
    
        if not subjects:
            return jsonify({"error": "No subjects found for the student's year"}), 400
    
        attendance_summary = []
    
        for subject in subjects:
            subject_name = subject.get('subject_name')
            if not subject_name:
                continue
    
            cursor.execute("""
                SELECT COUNT(distinct attendance_date) AS total
                FROM attendance
                WHERE subject_name = %s
            """, (subject_name,))
            total_lectures = cursor.fetchone()['total']
    
            cursor.execute("""
                SELECT COUNT(*) AS attended
                FROM attendance
                WHERE subject_name = %s AND student_id = %s AND status = 'Present'
            """, (subject_name, student_id))
            attended_lectures = cursor.fetchone()['attended']
    
            attendance_summary.append({
                "subject_name": subject_name,
                "total_lectures": total_lectures,
                "attended_lectures": attended_lectures
            })
    
        # Fetch all subjects for the student year
        cursor.execute("SELECT subject_name FROM subjects WHERE year = %s", (student_year,))
        subjects = [row['subject_name'] for row in cursor.fetchall()]
        
        # Fetch all unique (date, subject) pairs = all lectures conducted
        format_str = ','.join(['%s'] * len(subjects))
        cursor.execute(f"""
            SELECT DISTINCT attendance_date, subject_name
            FROM attendance
            WHERE subject_name IN ({format_str})
            ORDER BY attendance_date DESC
        """, tuple(subjects))
        lectures = cursor.fetchall()
        
        datewise_attendance = []
        
        for lec in lectures:
            date = lec['attendance_date']
            subject = lec['subject_name']
        
            # Check if student has record for this date+subject
            cursor.execute("""
                SELECT status FROM attendance
                WHERE student_id = %s AND subject_name = %s AND attendance_date = %s
            """, (student_id, subject, date))
            result = cursor.fetchone()
        
            status = result['status'] if result else 'Absent'
        
            datewise_attendance.append({
                "attendance_date": date.strftime('%Y-%m-%d'),
                "subject_name": subject,
                "status": status
            })

    
        return jsonify({
                "attendance": attendance_summary,
                "datewise_attendance": datewise_attendance
            })
        
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except: pass

# route for admin dashoard
@app.route('/get_admin_dashboard', methods=['GET'])
def get_admin_dashboard():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT COUNT(*) AS total_students FROM students")
            students = cursor.fetchone()
    
            cursor.execute("SELECT COUNT(*) AS total_teachers FROM teachers")
            teachers = cursor.fetchone()
    
            cursor.execute("SELECT COUNT(DISTINCT subject_name) AS total_subjects FROM subjects")
            subjects = cursor.fetchone()
    
            cursor.execute("""
                SELECT status, COUNT(*) AS today_attendance 
                FROM attendance 
                WHERE DATE(attendance_date) = CURDATE()
                GROUP BY status
            """)
            today_attendance = cursor.fetchall()
    
            cursor.execute("""
                SELECT a.attendance_date, s.username, a.subject_name, a.status 
                FROM attendance a
                JOIN students s ON a.student_id = s.id
                ORDER BY a.attendance_date DESC
                LIMIT 10
            """)
            recent_logs = cursor.fetchall()
    
            return jsonify({
                "total_students": students["total_students"],
                "total_teachers": teachers["total_teachers"],
                "total_subjects": subjects["total_subjects"],
                "today_attendance": today_attendance,
                "recent_logs": recent_logs
            })
    
        except Exception as e:
                return jsonify({"error": str(e)})
        
        
        # Fetch students by year
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except: pass

# route for fetch student in admin dashobard
@app.route('/admin/fetch_students')
def admin_fetch_students():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        year = request.args.get('year')
        if not year:
            return jsonify({"error": "Year is required"}), 400
    
        try:
            cursor.execute("SELECT id, username, prn FROM students WHERE year = %s", (year,))
            students = cursor.fetchall()
            return jsonify({"students": students})
        except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        
        # Fetch teachers by year
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except: pass

# route for fetch teachers in admin dashoard
@app.route('/admin/fetch_teachers')
def admin_fetch_teachers():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT t.id, t.username, t.teacher_id, t.email,t.password, t.mobile,
                   GROUP_CONCAT(l.subject_name SEPARATOR ', ') AS subjects
            FROM teachers t
            LEFT JOIN teacher_lectures l ON t.teacher_id = l.teacher_id
            GROUP BY t.id, t.username, t.teacher_id, t.email, t.mobile
        """)
        teachers = cursor.fetchall()
        return jsonify({"teachers": teachers})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

# route for fetch subjects in admin dahssobard
@app.route('/admin/fetch_subjects')
def admin_fetch_subjects():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id, subject_name, year FROM subjects ORDER BY year, subject_name")
            subjects = cursor.fetchall()
            return jsonify({"subjects": subjects})
        except Exception as e:
                return jsonify({"error": str(e)}), 500
            
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except: pass

@app.route('/admin/low_attendance_alerts', methods=['GET'])
def low_attendance_alerts():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            year_filter = request.args.get('year')
            if year_filter:
                cursor.execute("SELECT id, username, year FROM students WHERE year = %s", (year_filter,))
            else:
                cursor.execute("SELECT id, username, year FROM students")
            students = cursor.fetchall()

            defaulters = []

            for student in students:
                student_id = student['id']
                username = student['username']
                year = student['year']

                #  Get subjects for student's year
                cursor.execute("SELECT subject_name FROM subjects WHERE year = %s", (year,))
                subject_rows = cursor.fetchall()
                year_subjects = [row['subject_name'] for row in subject_rows]

                if not year_subjects:
                    continue  # Skip if no subjects found

                #  Get total distinct lecture dates for those year subjects
                format_strings = ','.join(['%s'] * len(year_subjects))
                cursor.execute(f"""
                    SELECT COUNT(DISTINCT attendance_date) AS total_lectures
                    FROM attendance
                    WHERE subject_name IN ({format_strings})
                """, tuple(year_subjects))
                total_result = cursor.fetchone()
                total_lectures = total_result['total_lectures'] or 0

                if total_lectures == 0:
                    continue  # No lectures conducted for year

                #  Count student's attended lectures only for their year's subjects
                cursor.execute(f"""
                    SELECT COUNT(*) AS attended
                    FROM attendance
                    WHERE student_id = %s AND status = 'Present' AND subject_name IN ({format_strings})
                """, (student_id, *year_subjects))
                attended_result = cursor.fetchone()
                attended = attended_result['attended'] or 0

                #  Calculate attendance %
                percentage = round((attended / total_lectures) * 100, 2)

                if percentage < 75:
                    defaulters.append({
                        "username": username,
                        "year": year,
                        "attendance_percentage": percentage
                    })

            #  Return top 5 sorted by lowest attendance
            defaulters = sorted(defaulters, key=lambda x: x["attendance_percentage"])[:5]
            return jsonify({"defaulters": defaulters})

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass


# load students
@app.route('/admin/students')
def get_students():
    try:
        year = request.args.get('year')
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        if year:
            cursor.execute("SELECT * FROM students WHERE year = %s", (year,))
        else:
            cursor.execute("SELECT * FROM students")

        students = cursor.fetchall()
        return jsonify({"students": students})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/admin/add_student', methods=['POST'])
def add_student():
    try:
        data = request.json
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO students (username, prn, mobile, email, password, fingerprint_id, year)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            data['username'],
            data['prn'],
            data['mobile'],
            data['email'],
            data['password'],  
            data['fingerprint_id'],
            data['year']
        ))
        conn.commit()
        return jsonify({"success": True, "message": "Student added successfully."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    finally:
        cursor.close()
        conn.close()



@app.route('/admin/update_student', methods=['PUT'])
def update_student():
    try:
        data = request.json
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE students
            SET username=%s, mobile=%s, email=%s, password=%s,fingerprint_id=%s, year=%s
            WHERE prn=%s
        """, (
            data['username'],
            data['mobile'],
            data['email'],
            data['password'],
            data['fingerprint_id'],
            data['year'],
            data['prn']
        ))
        conn.commit()
        return jsonify({"success": True, "message": "Student updated."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/admin/delete_student/<prn>', methods=['DELETE'])
def delete_student(prn):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM students WHERE prn=%s", (prn,))
        conn.commit()
        return jsonify({"success": True, "message": "Student deleted."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    finally:
        cursor.close()
        conn.close()



@app.route('/admin/student_counts_by_year')
def student_counts_by_year():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT year, COUNT(*) as count
            FROM students
            GROUP BY year
        """)
        result = cursor.fetchall()
        data = {str(year): count for (year, count) in result}
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/admin/add_teacher', methods=['POST'])
def add_teacher():
    try:
        data = request.get_json()

        username = data.get("username")
        teacher_id = data.get("teacher_id")
        email = data.get("email")
        mobile = data.get("mobile")
        password = data.get("password")  # <-- Added
        subjects = data.get("subjects", [])

        if not all([username, teacher_id, email, mobile, password]):
            return jsonify({"success": False, "message": "Missing required fields"}), 400

        conn = get_connection()
        cursor = conn.cursor()

        #  Insert into teachers table
        cursor.execute("""
            INSERT INTO teachers (username, teacher_id, email, password, mobile)
            VALUES (%s, %s, %s, %s, %s)
        """, (username, teacher_id, email, password, mobile))

        #  Insert subjects into teacher_lectures
        for subject in subjects:
            cursor.execute("""
                INSERT INTO teacher_lectures (teacher_id, subject_name)
                VALUES (%s, %s)
            """, (teacher_id, subject))

        conn.commit()
        return jsonify({"success": True, "message": "Teacher added successfully."}), 201

    except Exception as e:
        print("Error in /admin/add_teacher:", str(e))
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass


@app.route('/admin/update_teacher', methods=['PUT'])
def update_teacher():
    try:
        data = request.get_json()
        required = ['username', 'teacher_id', 'email', 'password', 'mobile', 'subjects']
        for field in required:
            if field not in data:
                return jsonify({'success': False, 'message': f'Missing field: {field}'}), 400

        conn = get_connection()
        cursor = conn.cursor()

        # Update teacher info
        cursor.execute("""
            UPDATE teachers SET username=%s, email=%s, password=%s, mobile=%s
            WHERE teacher_id=%s
        """, (data['username'], data['email'], data['password'], data['mobile'], data['teacher_id']))

        # Delete existing subject mappings
        cursor.execute("DELETE FROM teacher_lectures WHERE teacher_id = %s", (data['teacher_id'],))

        #  Re-insert updated subjects
        for subject in data['subjects']:
            cursor.execute("INSERT INTO teacher_lectures (teacher_id, subject_name) VALUES (%s, %s)", (data['teacher_id'], subject))

        conn.commit()
        return jsonify({'success': True, 'message': 'Teacher updated successfully'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        try: cursor.close(); conn.close()
        except: pass

@app.route('/admin/delete_teacher/<teacher_id>', methods=['DELETE'])
def delete_teacher(teacher_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        #  Delete subjects first due to FK
        cursor.execute("DELETE FROM teacher_lectures WHERE teacher_id = %s", (teacher_id,))

        #  Then delete teacher
        cursor.execute("DELETE FROM teachers WHERE teacher_id = %s", (teacher_id,))
        conn.commit()

        return jsonify({'success': True, 'message': 'Teacher deleted successfully'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        try: cursor.close(); conn.close()
        except: pass


# fetch all subjects
@app.route('/admin/fetch_subjects', methods=['GET'])
def fetch_subjects():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, subject_name, year FROM subjects")
        subjects = cursor.fetchall()
        return jsonify({"subjects": subjects})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/admin/add_subject', methods=['POST'])
def add_subject():
    try:
        data = request.get_json()
        print(" Incoming Subject Data:", data)

        if not data or 'subject_name' not in data or 'year' not in data:
            return jsonify({"error": "Missing subject_name or year"}), 400

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO subjects (subject_name, year) VALUES (%s, %s)",
                       (data['subject_name'], int(data['year'])))
        conn.commit()
        return jsonify({"message": "Subject added successfully."})
    except Exception as e:
        print("❌ Error in /admin/add_subject:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()



# update a subject
@app.route('/admin/update_subject', methods=['PUT'])
def update_subject():
    try:
        data = request.json
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE subjects SET subject_name=%s, year=%s WHERE id=%s", 
                       (data['subject_name'], data['year'], data['id']))
        conn.commit()
        return jsonify({"message": "Subject updated successfully."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# delete a subject
@app.route('/admin/delete_subject/<int:id>', methods=['DELETE'])
def delete_subject(id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM subjects WHERE id=%s", (id,))
        conn.commit()
        return jsonify({"message": "Subject deleted successfully."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()




# 

# ESP8266_IP = "http://10.110.121.30"


@app.route("/send_ip_to_esp", methods=["POST"])
def api_send_ip_to_esp():
    success = send_ip_to_esp()
    if success:
        return jsonify({
            "status": "ok",
            "message": "IP sent",
            "esp_ip": esp_ip  #  Include ESP IP here
        })
    else:
        return jsonify({"status": "fail", "message": "ESP not reachable"}), 500




def get_esp_url(path: str):
    global esp_ip
    if not esp_ip:
        esp_ip = find_esp_ip()
    return f"http://{esp_ip}{path}" if esp_ip else None


# Start enrollment 

@app.route("/enroll_fingerprint/<int:fingerprint_id>")
def enroll_fingerprint(fingerprint_id):
    try:
        print(f"Sending request to ESP for ID {fingerprint_id}")
        response = requests.get(get_esp_url(f"/enroll/{fingerprint_id}"), timeout=5)

        print("Raw ESP Response:", response.text)

        # Always tell frontend to wait
        return jsonify({
            "status": "pending",
            "message": f"Enrollment request sent to ESP. Await confirmation from OLED and ESP..."
        })

    except requests.exceptions.ReadTimeout:
        print("ESP took too long to respond (timeout), but enrollment might still be in progress.")
        return jsonify({
            "status": "pending",
            "message": "ESP did not respond in time, but enrollment may still be in progress..."
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ESP will POST here after enrollment completes

enroll_status = {}

@app.route("/enroll_result", methods=["POST"])
def enroll_result():
    try:
        data = request.get_json()
        fid = str(data.get("fingerprint_id"))
        status = data.get("status")

        enroll_status[fid] = {
            "status": status,
            "message": "Enroll success" if status == "success" else "Enroll failed"
        }

        print(f"Received enroll result for ID {fid}: {status}")
        return jsonify({"ack": True})

    except Exception as e:
        return jsonify({"ack": False, "error": str(e)}), 500


# Frontend can poll this for status
@app.route("/get_enroll_status/<fid>")
def get_enroll_status(fid):
    result = enroll_status.get(fid)
    if result:
        return jsonify(result)
    return jsonify({"status": "pending", "message": "Waiting for ESP response..."})

@app.route('/clear_enroll_status/<int:fingerprint_id>', methods=['POST'])
def clear_enroll_status(fingerprint_id):
    fid = str(fingerprint_id)
    enroll_status[fid] = {
        "status": "pending",
        "message": "Enrollment reset"
    }
    return jsonify({"status": "cleared"})


# shows fingprint list in admin dashboard
@app.route('/fingerprint/list')
def proxy_list_fingerprints():

    send_ip_to_esp()  # Ensure ESP knows Flask IP

    try:
        response = requests.get(get_esp_url("/list"), timeout=10)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({
            "error": "Could not reach fingerprint scanner",
            "details": str(e)
        }), 500

# delete fingerprint id form scanner
@app.route('/fingerprint/delete/<int:fingerprint_id>')
def proxy_delete_fingerprint(fingerprint_id):
    send_ip_to_esp()

    try:
        response = requests.get(get_esp_url(f"/delete/{fingerprint_id}"), timeout=5)

        if response.status_code != 200:
            return jsonify({
                "error": "ESP error",
                "status_code": response.status_code,
                "text": response.text
            }), 502

        try:
            data = response.json()
        except ValueError:
            data = {"message": response.text.strip()}

        return jsonify({"status": "success", "result": data})

    except Exception as e:
        return jsonify({
            "error": "Could not delete fingerprint",
            "details": str(e)
        }), 500


if __name__ == '__main__':
     app.run(host='0.0.0.0', port=5000, debug=True)

