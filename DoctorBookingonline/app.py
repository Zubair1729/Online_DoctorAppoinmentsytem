import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_pymongo import PyMongo  # type: ignore
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from bson import errors
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)

# MongoDB Atlas Configuration
app.config["MONGO_URI"] = "your_MongodbAtlas String" # eg:mongodb+srv://username:password@doctapointmnet.anvt49s.mongodb.net/doctorbooking?retryWrites=true&w=majority
app.secret_key = "a_random_secure_key"



# Initialize PyMongo
mongo = PyMongo(app)
doctors_collection = mongo.db.doctors
branches_collection = mongo.db.branches
appointments_collection = mongo.db.appointments
patients_collection = mongo.db.patients

# File Upload Config
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ensure upload directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    return render_template('home.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Both username and password are required!", "danger")
            return redirect(url_for("login"))

        if role == "doctor":
            user = doctors_collection.find_one({"username": username, "role": "doctor"})
            if user and check_password_hash(user["password"], password):
                session["user"] = {"username": username, "role": "doctor"}
                
                return redirect(url_for("doctor_dashboard"))
            else:
                flash("Invalid Doctor credentials!", "danger")

        elif role == "patient":
            user = patients_collection.find_one({"username": username, "role": "patient"})
            if user and check_password_hash(user["password"], password):
                session["user"] = {"username": username, "role": "patient"}
                
                return redirect(url_for("patient_dashboard"))
            else:
                flash("Invalid Patient credentials!", "danger")

        else:
            flash("Invalid role selection!", "danger")

        return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        role = request.form.get("role", "").strip()
        password = request.form.get("password", "").strip()

        if not role or not password:
            flash("Role and password are required!", "danger")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        if role == "doctor":
            username = request.form.get("username", "").strip()
            specialization = request.form.get("specialization", "").strip()
            custom_specialization = request.form.get("custom_specialization", "").strip()
            branch = request.form.get("branch", "").strip()
            more_details = request.form.get("more_details", "").strip()
            custom_branch_name = request.form.get("custom_branch_name", "").strip()
            custom_branch_address = request.form.get("custom_branch_address", "").strip()

            if specialization == "other":
                specialization = custom_specialization

            if branch == "custom":
                if not custom_branch_name or not custom_branch_address:
                    flash("Branch name and address are required!", "danger")
                    return redirect(url_for("register"))

                branches_collection.insert_one({"name": custom_branch_name, "address": custom_branch_address})
                branch = custom_branch_name
                branch_address = custom_branch_address
            else:
                branch_data = branches_collection.find_one({"name": branch}, {"_id": 0, "address": 1})
                if not branch_data:
                    flash("Invalid branch selected!", "danger")
                    return redirect(url_for("register"))
                branch_address = branch_data.get("address")

            image_filename = None
            if "photo" in request.files:
                file = request.files["photo"]
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                    image_filename = filename

            doctors_collection.insert_one({
                "username": username,
                "password": hashed_password,
                "specialization": specialization,
                "branch": branch,
                "branch_address": branch_address,
                "more_details": more_details,
                "photo": image_filename,
                "role": "doctor"
            })

            flash("Doctor registration successful! You can now log in.", "success")

        elif role == "patient":
            name = request.form.get("name", "").strip()
            phone_number = request.form.get("phone_number", "").strip()

            if not name or not phone_number:
                flash("Name and phone number are required for patients!", "danger")
                return redirect(url_for("register"))

            patients_collection.insert_one({
                "username": name,
                "phone_number": phone_number,
                "password": hashed_password,
                "role": "patient"
            })

            flash("Patient registration successful! You can now log in.", "success")

        return redirect(url_for("login"))

    branches = list(branches_collection.find({}, {"_id": 0, "name": 1, "address": 1}))
    return render_template("register.html", branches=branches)

# Additional routes continue here as in your script...



@app.route("/doctor_dashboard")
def doctor_dashboard():
    # Check if user is logged in and is a doctor
    if "user" not in session or session["user"]["role"] != "doctor":
        flash("Please log in first!", "warning")
        return redirect(url_for("login"))

    # Fetch doctor's username from session
    doctor_name = session["user"]["username"]
    
    # Get total appointments for the doctor
    total_appointments = appointments_collection.count_documents({"doctor_name": doctor_name})

    # Get current date and today's appointments count
    current_date = datetime.now().strftime("%Y-%m-%d")
    todays_patients = appointments_collection.count_documents({"doctor_name": doctor_name, "date": current_date})

    # Get upcoming appointments count
    upcoming_appointments = appointments_collection.count_documents({"doctor_name": doctor_name, "date": {"$gt": current_date}})
    
    return render_template(
        "dashboard.html",
        doctor=doctor_name,
        total_appointments=total_appointments,
        todays_patients=todays_patients,
        upcoming_appointments=upcoming_appointments
    )


@app.route("/patients")
def patients():
    # Ensure the user is logged in as a doctor
    if "user" not in session or session["user"]["role"] != "doctor":
        flash("Please log in first!", "warning")
        return redirect(url_for("login"))

    current_date = datetime.now().strftime("%Y-%m-%d")

    # Fetch all patients (appointments) for the logged-in doctor
    doctor_name = session["user"]["username"]
    doctor_patients = list(appointments_collection.find({"doctor_name": doctor_name}))

    # Separate patients for today and future dates
    current_patients = [patient for patient in doctor_patients if patient["date"] == current_date]
    other_patients = [patient for patient in doctor_patients if patient["date"] > current_date]

    # Sort lists
    current_patients.sort(key=lambda x: x["time"])
    other_patients.sort(key=lambda x: x["date"])

    return render_template(
        "patients.html", 
        current_patients=current_patients, 
        other_patients=other_patients, 
        current_date=current_date
    )


@app.route('/patient_dashboard')
def patient_dashboard():
    if "user" in session and session["user"]["role"] == "patient":
        patient_name = session["user"].get("name", "Patient")
        flash(f"Welcome, {patient_name}!", "success")  # Show patient's name in the flash message
        return render_template("patient_dashboard.html", username=patient_name)
    flash("You need to log in first.", "danger")
    return redirect(url_for("login"))

@app.route("/appointments")
def appointments():
    # Ensure the user is logged in as a doctor
    if "user" not in session or session["user"]["role"] != "doctor":
        flash("Please log in first!", "warning")
        return redirect(url_for("login"))

    current_date = datetime.now().strftime("%Y-%m-%d")

    # Fetch all appointments for the logged-in doctor
    doctor_name = session["user"]["username"]
    doctor_appointments = list(appointments_collection.find({"doctor_name": doctor_name}))

    # Sort appointments by date and time
    doctor_appointments.sort(key=lambda x: (x["date"], x["time"]))

    return render_template("appointments.html", appointments=doctor_appointments)
@app.route("/profile", methods=["GET", "POST"])
def profile():
    # Ensure the user is logged in as a doctor
    if "user" not in session or session["user"]["role"] != "doctor":
        flash("You need to log in first!", "danger")
        return redirect(url_for("login"))

    doctor_name = session["user"]["username"]

    if request.method == "POST":
        # Fetch form data for updating profile
        username = request.form.get("username", "").strip()
        specialization = request.form.get("specialization", "").strip()
        more_details = request.form.get("more_details", "").strip()
        branch_id = request.form.get("branch", "").strip()  # Fetch the selected branch

        # Handle image upload if provided
        image_filename = None
        if "photo" in request.files:
            file = request.files["photo"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(image_path)
                image_filename = filename  # Store only filename, not full path

        # Prepare update data
        update_data = {"specialization": specialization, "more_details": more_details}

        if image_filename:
            update_data["photo"] = image_filename

        if branch_id:  # Update the branch if selected
            try:
                branch_obj = branches_collection.find_one({"_id": ObjectId(branch_id)})
                if branch_obj:
                    update_data["branch"] = ObjectId(branch_id)
                    update_data["branch_name"] = branch_obj.get("name", "Unknown Branch")
                    update_data["branch_address"] = branch_obj.get("address", "No address available")
                else:
                    flash("Invalid branch selection!", "danger")
                    return redirect(url_for("profile"))
            except Exception as e:
                flash(f"Error: {str(e)}", "danger")
                return redirect(url_for("profile"))

        # Update the doctor's profile based on their username (from the session)
        doctors_collection.update_one(
            {"username": doctor_name}, {"$set": update_data}
        )

        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile"))

    # Fetch the current doctor's details
    doctor = doctors_collection.find_one({"username": doctor_name})

    # Fetch all branches from the branch collection
    branches = list(branches_collection.find({}, {"_id": 1, "name": 1, "address": 1}))

    return render_template("profile.html", doctor=doctor, branches=branches)

@app.route("/doctors")
def doctors():
    doctors_list = list(doctors_collection.find({}, {"_id": 0, "password": 0}))  # Exclude password
    return render_template("doctors.html", doctors=doctors_list)


@app.route("/branches")
def branches():
    branches_list = list(branches_collection.find({}))  # Fetch branches from MongoDB
    
    # Convert ObjectId to string for JSON compatibility
    for branch in branches_list:
        branch["_id"] = str(branch["_id"])

    return render_template("branches.html", branches=branches_list)




# Booking Page Route
@app.route('/booking', methods=['GET'])
def booking():
    doctors = list(doctors_collection.find({}, {"_id": 1, "username": 1, "branch": 1, "branch_address": 1}))

    for doctor in doctors:
        doctor["branch"] = doctor.get("branch", "No branch assigned")
        doctor["branch_address"] = doctor.get("branch_address", "Address not available")

    if not doctors:
        flash('No doctors available at the moment.', 'warning')
        return render_template("no_doctors.html")  # Show a friendly page

    return render_template("booking.html", doctors=doctors)


# Booking appointment route to handle form submission
@app.route("/book_appointment", methods=["POST"])
def book_appointment():
    name = request.form.get("name", "").strip()
    doctor_id = request.form.get("doctor", "").strip()
    date = request.form.get("date", "").strip()
    time = request.form.get("time", "").strip()

    # Ensure all fields are provided
    if not name or not doctor_id or not date or not time:
        flash("All fields are required!", "danger")
        return redirect(url_for("booking"))

    # Validate date and time format
    try:
        datetime.strptime(date, "%Y-%m-%d")
        datetime.strptime(time, "%H:%M")
    except ValueError:
        flash("Invalid date or time format!", "danger")
        return redirect(url_for("booking"))

    # Validate ObjectId for doctor_id
    try:
        doctor_object_id = ObjectId(doctor_id)
    except errors.InvalidId:
        flash("Invalid doctor selection!", "danger")
        return redirect(url_for("booking"))

    # Fetch doctor details from MongoDB
    doctor = doctors_collection.find_one({"_id": doctor_object_id})
    if not doctor:
        flash("Doctor not found!", "danger")
        return redirect(url_for("booking"))

    # Fetch branch details
    branch = doctor.get("branch", "No branch assigned")
    branch_address = doctor.get("branch_address", "Address not available")  # Get stored branch address

    # Store appointment in MongoDB
    appointment_id = appointments_collection.insert_one({
        "name": name,
        "doctor_id": doctor_object_id,
        "doctor_name": doctor["username"],
        "date": date,
        "time": time,
        "branch": branch,
        "branch_address": branch_address  # Store branch address
    }).inserted_id

    # Store booking details in session
    session["booking"] = {
        "name": name,
        "date": date,
        "time": time,
        "doctor_name": doctor["username"],
        "branch": branch,
        "branch_address": branch_address  # Include branch address in session
    }

    flash("Appointment booked successfully!", "success")
    return redirect(url_for("receipt"))
# Receipt Route
@app.route("/receipt")
def receipt():
    booking_details = session.get("booking", None)
    if not booking_details:
        flash("No appointment details found!", "danger")
        return redirect(url_for("booking"))
    return render_template("receipt.html", booking=booking_details)



@app.route("/get_branch_address")
def get_branch_address():
    branch_name = request.args.get("branch", "").strip()
    branch_data = branches_collection.find_one({"name": branch_name}, {"_id": 0, "address": 1})
    return jsonify({"address": branch_data["address"] if branch_data else None})










# Logout Route
@app.route("/logout")
def logout():
    session.pop("doctor", None)
    flash("Logged out successfully!", "info")
    return redirect(url_for("home"))





if __name__ == '__main__':
    app.run(debug=True)