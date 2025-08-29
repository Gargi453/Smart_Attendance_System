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
    
            # Recent 10 attendance logs (any subject taught by this teacher)
        cursor.execute(f"""
            SELECT attendance_date, subject_name,
                   SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present,
                   SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) AS absent
            FROM attendance
            WHERE subject_name IN ({format_str})
            GROUP BY attendance_date, subject_name
            ORDER BY attendance_date DESC
            LIMIT 10
        """, tuple(subjects))
        logs_data = cursor.fetchall()
        recent_logs = [{
            "date": row["attendance_date"].strftime('%Y-%m-%d'),
            "subject": row["subject_name"],
            "present": row["present"],
            "absent": row["absent"]
        } for row in logs_data]
    
    
    
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