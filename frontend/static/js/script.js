async function enrollFingerprint() {
    const fingerprintId = document.getElementById("student-fingerprint").value;
    const statusDiv = document.getElementById("fingerprint-status");

    //  Clear previous status visually
    statusDiv.innerText = "";
    statusDiv.style.color = "black";

    if (!fingerprintId) {
        statusDiv.innerText = "Please enter a Fingerprint ID first.";
        statusDiv.style.color = "red";
        return;
    }

    const BACKEND_URL = `${window.location.protocol}//${window.location.hostname}:5000`;

    try {
        //  Clear old enrollment status in backend
        await fetch(`${BACKEND_URL}/clear_enroll_status/${fingerprintId}`, { method: "POST" });

        statusDiv.innerText = "Sending ID to scanner...";
        statusDiv.style.color = "black";

        //  First send Flask IP to ESP
        const ipRes = await fetch(`${BACKEND_URL}/send_ip_to_esp`, { method: "POST" });
        const ipData = await ipRes.json();

        if (!ipRes.ok || ipData.status !== "ok") {
            statusDiv.innerText = "❌ Failed to contact ESP. Check Flask and ESP connection.";
            statusDiv.style.color = "red";
            return;
        }

        console.log("✅ ESP IP (from Flask):", ipData.esp_ip);

        //  Start fingerprint enrollment via Flask
        const enrollRes = await fetch(`${BACKEND_URL}/enroll_fingerprint/${fingerprintId}`);
        const enrollData = await enrollRes.json();

        if (enrollData.status === "pending" || enrollData.status === "success") {
            statusDiv.innerText = "Fingerprint enrollment started. Waiting for result...";
            let attempts = 0;
            const maxAttempts = 10;

            const pollResult = async () => {
                const res = await fetch(`${BACKEND_URL}/get_enroll_status/${fingerprintId}`);
                const result = await res.json();

                if (result.status === "success") {
                    statusDiv.innerText = `✅ Fingerprint enrolled at ID ${fingerprintId}`;
                    statusDiv.style.color = "green";
                } else if (result.status === "fail") {
                    statusDiv.innerText = `❌ Enrollment failed: ${result.message || "Unknown error"}`;
                    statusDiv.style.color = "red";
                } else {
                    if (++attempts < maxAttempts) {
                        setTimeout(pollResult, 2000);
                    } else {
                        statusDiv.innerText = "❌ Timeout waiting for ESP.";
                        statusDiv.style.color = "red";
                    }
                }
            };

            setTimeout(pollResult, 2000);
        } else {
            statusDiv.innerText = `❌ Failed to start enrollment: ${enrollData.message || "Unknown error"}`;
            statusDiv.style.color = "red";
        }
    } catch (err) {
        console.error(err);
        statusDiv.innerText = "❌ Could not connect to Flask or ESP.";
        statusDiv.style.color = "red";
    }
}




let allSubjects = [];  // Loaded from backend
let selectedSubjectsByYear = { 1: [], 2: [], 3: [], 4: [] };


// main script
document.addEventListener("DOMContentLoaded", function () {
  (async () => {
    const BACKEND_URL = "http://127.0.0.1:5000";
    let selectedRole = "student";
    let allSubjects = [];  // Loaded from backend
    let selectedSubjects = [];

    //  Fetch subjects from DB on load
    async function fetchAllSubjects() {
      try {
        const res = await fetch(`${BACKEND_URL}/admin/fetch_subjects`);
        if (!res.ok) throw new Error("Failed to fetch subjects");
        const data = await res.json();
        allSubjects = data.subjects;
        console.log("Fetched Subjects:", allSubjects);
      } catch (err) {
        console.error("Error fetching subjects:", err);
      }
    }

    await fetchAllSubjects(); //  Called inside async IIFE


    //  Filter and show subjects by selected year
    window.loadSubjects = function () {
      const year = document.getElementById("teacher-year").value;
      const subjectList = document.getElementById("subject-list");
      subjectList.innerHTML = "";
    
      const yearSubjects = allSubjects.filter(sub => sub.year == year);
    
      yearSubjects.forEach(subject => {
        const div = document.createElement("div");
        div.classList.add("subject-item");
        div.textContent = subject.subject_name;
    
        // Highlight if already selected
        if (selectedSubjectsByYear[year].includes(subject.subject_name)) {
          div.classList.add("selected");
        }
    
        div.addEventListener("click", function () {
          const idx = selectedSubjectsByYear[year].indexOf(subject.subject_name);
          if (idx >= 0) {
            selectedSubjectsByYear[year].splice(idx, 1);
            div.classList.remove("selected");
          } else {
            selectedSubjectsByYear[year].push(subject.subject_name);
            div.classList.add("selected");
          }
    
          updateSelectedSubjects();
        });
    
        subjectList.appendChild(div);
      });
    
      updateSelectedSubjects();
    };

    function updateSelectedSubjects() {
      const selectedSubjectsDiv = document.getElementById("selected-subjects");
    
      const allSelected = Object.values(selectedSubjectsByYear).flat();
    
      selectedSubjectsDiv.innerHTML =
        `<strong>Selected Subjects:</strong> ${allSelected.length ? allSelected.join(", ") : "None"}`;
    }

 


    function toggleForm() {
        const loginForm = document.getElementById("login-form");
        const signupForm = document.getElementById("signup-form");
        const title = document.getElementById("page-title");

        if (loginForm.style.display === "none") {
            loginForm.style.display = "block";
            signupForm.style.display = "none";
            title.textContent = "Login Page";
        } else {
            loginForm.style.display = "none";
            signupForm.style.display = "block";
            title.textContent = "Sign Up Page";
        }
    }

    function setRole(button){
        
        document.querySelectorAll(".role-btn").forEach(btn => btn.classList.remove("active"));
        button.classList.add("active");
    }

    function setActive(button) {
        const tabContainer = button.parentElement;
        tabContainer.querySelectorAll("button").forEach(btn => btn.classList.remove("active"));
        button.classList.add("active");
    }
    
    function showForm(type) {
        document.getElementById("student-fields").style.display = type === "student" ? "block" : "none";
        document.getElementById("teacher-fields").style.display = type === "teacher" ? "block" : "none";

        document.getElementById("student-btn").classList.toggle("active", type === "student");
        document.getElementById("teacher-btn").classList.toggle("active", type === "teacher");
    }

    function togglePassword(inputId) {
        const input = document.getElementById(inputId);
        input.type = input.type === "password" ? "text" : "password";
    }

    async function handleLogin() {
        const username = document.getElementById("login-username").value;
        const password = document.getElementById("login-password").value;
        // const selectedRole = document.querySelector(".role-btn.active").getAttribute("data-role");
        const selectedButton = document.querySelector(".role-btn.active");


        if (!username || !password) {
            alert("Please enter both username and password.");
            return;
        }

        if (!selectedButton) {
            alert("Please select a role before logging in.");
            return;
        }

        const selectedRole = selectedButton.getAttribute("data-role");

        try {
            const response = await fetch(`${BACKEND_URL}/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password ,role:selectedRole}),
            });

            const data = await response.json();

            if (data.user_id) {
                localStorage.setItem("user_id", data.user_id);
                localStorage.setItem("user_role", data.role);
                
                showSuccessModal("🎉 Login Successful", "Welcome back!", () => {
                    if (selectedRole === "teacher") {
                      window.location.href = "teacher_dashboard1.html";
                    } else if (selectedRole === "student") {
                      window.location.href = "student_dashboard.html";
                    } else if (selectedRole === "admin") {
                      window.location.href = "admin_dashboard.html";
                    }});
                    
            } else {
                alert("Login failed:" + data.error);
            }
        } catch (error) {
            console.error("Error logging in:", error);
            alert("An error occurred. Please try again.");
        }
    }
    

    async function validateSignUp() {
        const isStudent = document.getElementById("student-fields").style.display === "block";
        let userData = {};
        let endpoint = "";

        if (isStudent) {
            userData = {
                username: document.getElementById("student-username").value,
                prn: document.getElementById("student-prn").value,
                mobile: document.getElementById("student-mobile").value,
                email: document.getElementById("student-email").value,
                password: document.getElementById("student-password").value,
                fingerprint_id: document.getElementById("student-fingerprint").value,
                year: document.getElementById("student-year").value,
                role: "student"
            };
            endpoint = "/register/student";
        } else {
            const allSelectedSubjects = Object.values(selectedSubjectsByYear).flat();
            userData = {
                username: document.getElementById("teacher-username").value,
                teacher_id: document.getElementById("teacher-id").value,
                mobile: document.getElementById("teacher-mobile").value,
                email: document.getElementById("teacher-email").value,
                password: document.getElementById("teacher-password").value,
                subjects: allSelectedSubjects, // Store all selected subjects
                role: "teacher"
            };
            endpoint = "/register/teacher";
        }

        for (let key in userData) {
            if (!userData[key] || userData[key] === "") {
                alert(`Please fill in all required fields. Missing: ${key}`);
                return;
            }
        }

        try {
            const response = await fetch(`${BACKEND_URL}${endpoint}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(userData),
            });

            const data = await response.json();

           if (response.ok) {
               showSuccessModal("✅ Registration Successful", "You can now log in.", () => {
                toggleForm(); // switch to login form
               clearSignupForm(); // clears fields
          });
            } 
           else {
                  alert("Registration : " + data.message);
            }

        } catch (error) {
            console.error("Error registering:", error);
            alert("An error occurred. Please try again.");
        }
    }

   

    document.getElementById("teacher-year").addEventListener("change", loadSubjects);

    window.toggleForm = toggleForm;
    window.setActive = setActive;
    window.showForm = showForm;
    window.togglePassword = togglePassword;
    window.setRole = setRole;
    window.handleLogin = handleLogin;
    window.validateSignUp = validateSignUp;
    window.loadSubjects = loadSubjects;
    window.enrollFingerprint = enrollFingerprint;
    window.closeSuccessModal = closeSuccessModal
    

  })(); // end of async IIFE  
});//end of DOMContenLoaded

//  Place this OUTSIDE the DOMContentLoaded block, at the end of script.js or before DOMContentLoaded
function showSuccessModal(title = "Success", message = "Action completed", callback = null) {
  document.getElementById("modal-title").innerText = title;
  document.getElementById("modal-message").innerText = message;
  document.getElementById("successModal").style.display = "flex";
  window._successCallback = callback;
}

function closeSuccessModal() {
  document.getElementById("successModal").style.display = "none";
  if (typeof window._successCallback === "function") {
    window._successCallback();
    window._successCallback = null;
  }
}

function clearSignupForm() {
  // Student fields
  document.getElementById("student-username").value = " ";
  document.getElementById("student-prn").value = "";
  document.getElementById("student-mobile").value = "";
  document.getElementById("student-email").value = "";
  document.getElementById("student-password").value = "";
  document.getElementById("student-fingerprint").value = "";
  document.getElementById("student-year").value = "";

  // Teacher fields
  document.getElementById("teacher-username").value = "";
  document.getElementById("teacher-id").value = "";
  document.getElementById("teacher-mobile").value = "";
  document.getElementById("teacher-email").value = "";
  document.getElementById("teacher-password").value = "";
  document.getElementById("teacher-year").value = "";

  // Clear selected subjects
  selectedSubjectsByYear = { 1: [], 2: [], 3: [], 4: [] };
  const subjectList = document.getElementById("subject-list");
  if (subjectList) subjectList.innerHTML = "";
  const selectedSubjectsDiv = document.getElementById("selected-subjects");
  if (selectedSubjectsDiv) selectedSubjectsDiv.innerHTML = "Selected Subjects: None";

  // Clear fingerprint status
  const statusDiv = document.getElementById("fingerprint-status");
  if (statusDiv) {
    statusDiv.innerText = "";
    statusDiv.style.color = "black";
}

}




