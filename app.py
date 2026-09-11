from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3
import os
import smtplib
from email.message import EmailMessage
from functools import wraps
from werkzeug.utils import secure_filename


app = Flask(__name__)

app.secret_key = "change-this-secret-before-production"

app.config["UPLOAD_FOLDER"] = "static/assets/uploads"

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


DB = "realestate.db"


# =========================================================
# ADMIN LOGIN SETTINGS
# =========================================================

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@12345"


# =========================================================
# EMAIL SETTINGS
# =========================================================
# We will configure Gmail App Password later.

YOUR_EMAIL = "taranjeetsingh2557@gmail.com"
YOUR_APP_PASSWORD = "your-gmail-app-password"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():

    conn = db()

    # Existing properties table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            property_type TEXT NOT NULL,
            purpose TEXT NOT NULL,
            price TEXT NOT NULL,
            location TEXT NOT NULL,
            area TEXT,
            bedrooms INTEGER,
            bathrooms INTEGER,
            description TEXT,
            image TEXT,
            featured INTEGER DEFAULT 0
        )
    """)

    # NEW: enquiries table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS enquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            property_name TEXT,
            message TEXT,
            status TEXT DEFAULT 'New',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# ADMIN LOGIN REQUIRED
# =========================================================

def admin_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))

        return function(*args, **kwargs)

    return decorated_function


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    conn = db()

    featured = conn.execute(
        """
        SELECT *
        FROM properties
        ORDER BY featured DESC, id DESC
        LIMIT 6
        """
    ).fetchall()

    stats = {

        "total": conn.execute(
            "SELECT COUNT(*) FROM properties"
        ).fetchone()[0],

        "sale": conn.execute(
            "SELECT COUNT(*) FROM properties WHERE purpose='Sale'"
        ).fetchone()[0],

        "rent": conn.execute(
            "SELECT COUNT(*) FROM properties WHERE purpose='Rent'"
        ).fetchone()[0]
    }

    conn.close()

    return render_template(
        "index.html",
        properties=featured,
        stats=stats
    )


# =========================================================
# PROPERTIES
# =========================================================

@app.route("/properties")
def properties():

    q = request.args.get("q", "").strip()

    purpose = request.args.get(
        "purpose",
        ""
    )

    ptype = request.args.get(
        "type",
        ""
    )

    conn = db()

    sql = """
        SELECT *
        FROM properties
        WHERE 1=1
    """

    params = []

    if q:

        sql += """
            AND (
                title LIKE ?
                OR location LIKE ?
            )
        """

        params += [
            f"%{q}%",
            f"%{q}%"
        ]

    if purpose:

        sql += " AND purpose=?"

        params.append(purpose)

    if ptype:

        sql += " AND property_type=?"

        params.append(ptype)

    rows = conn.execute(
        sql + " ORDER BY featured DESC, id DESC",
        params
    ).fetchall()

    conn.close()

    return render_template(
        "properties.html",
        properties=rows
    )


# =========================================================
# PROPERTY DETAIL
# =========================================================

@app.route("/property/<int:property_id>")
def property_detail(property_id):

    conn = db()

    prop = conn.execute(
        """
        SELECT *
        FROM properties
        WHERE id=?
        """,
        (property_id,)
    ).fetchone()

    conn.close()

    if not prop:

        return "Property not found", 404

    return render_template(
        "property_detail.html",
        property=prop
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if (
            username == ADMIN_USERNAME
            and password == ADMIN_PASSWORD
        ):

            session["admin_logged_in"] = True

            return redirect(
                url_for("admin")
            )

        flash(
            "Invalid username or password.",
            "error"
        )

    return render_template(
        "admin_login.html"
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route("/admin/logout")
def admin_logout():

    session.pop(
        "admin_logged_in",
        None
    )

    return redirect(
        url_for("admin_login")
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route(
    "/admin",
    methods=["GET", "POST"]
)
@admin_required
def admin():

    # -----------------------------------------------------
    # ADD PROPERTY
    # -----------------------------------------------------

    if request.method == "POST":

        image = request.files.get("image")

        image_name = ""

        if image and image.filename:

            image_name = secure_filename(
                image.filename
            )

            image.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    image_name
                )
            )

        conn = db()

        conn.execute(
            """
            INSERT INTO properties
            (
                title,
                property_type,
                purpose,
                price,
                location,
                area,
                bedrooms,
                bathrooms,
                description,
                image,
                featured
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.form["title"],
                request.form["property_type"],
                request.form["purpose"],
                request.form["price"],
                request.form["location"],
                request.form.get("area", ""),
                request.form.get("bedrooms") or None,
                request.form.get("bathrooms") or None,
                request.form.get("description", ""),
                image_name,
                1 if request.form.get("featured") else 0
            )
        )

        conn.commit()
        conn.close()

        flash(
            "Property added successfully!"
        )

        return redirect(
            url_for("admin")
        )


    # -----------------------------------------------------
    # GET PROPERTIES
    # -----------------------------------------------------

    conn = db()

    rows = conn.execute(
        """
        SELECT *
        FROM properties
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()


    # -----------------------------------------------------
    # GET ENQUIRIES
    # -----------------------------------------------------

    conn = db()

    enquiries = conn.execute(
        """
        SELECT *
        FROM enquiries
        ORDER BY created_at DESC
        """
    ).fetchall()

    conn.close()


    return render_template(
        "admin.html",
        properties=rows,
        enquiries=enquiries
    )


# =========================================================
# DELETE PROPERTY
# =========================================================

@app.route(
    "/delete/<int:property_id>",
    methods=["POST"]
)
@admin_required
def delete_property(property_id):

    conn = db()

    conn.execute(
        """
        DELETE FROM properties
        WHERE id=?
        """,
        (property_id,)
    )

    conn.commit()
    conn.close()

    flash(
        "Property deleted."
    )

    return redirect(
        url_for("admin")
    )


# =========================================================
# SUBMIT ENQUIRY
# =========================================================

@app.route(
    "/submit-enquiry",
    methods=["POST"]
)
def submit_enquiry():

    name = request.form.get(
        "name",
        ""
    ).strip()

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip()

    property_name = request.form.get(
        "property_name",
        ""
    ).strip()

    message = request.form.get(
        "message",
        ""
    ).strip()


    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    if not name or not phone or not email:

        flash(
            "Please fill in your name, phone and email.",
            "error"
        )

        return redirect(
            request.referrer or url_for("home")
        )


    # -----------------------------------------------------
    # SAVE ENQUIRY TO DATABASE
    # -----------------------------------------------------

    conn = db()

    conn.execute(
        """
        INSERT INTO enquiries
        (
            name,
            phone,
            email,
            property_name,
            message
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            name,
            phone,
            email,
            property_name,
            message
        )
    )

    conn.commit()
    conn.close()


    # -----------------------------------------------------
    # SEND EMAIL
    # -----------------------------------------------------

    send_enquiry_email(
        name,
        phone,
        email,
        property_name,
        message
    )


    flash(
        "Thank you! Your enquiry has been received."
    )

    return redirect(
        request.referrer or url_for("home")
    )


# =========================================================
# SEND ENQUIRY EMAIL
# =========================================================

def send_enquiry_email(
    name,
    phone,
    email,
    property_name,
    message
):

    # Don't try to send email until Gmail settings
    # have been configured.

    if (
        YOUR_EMAIL == "your-email@gmail.com"
        or YOUR_APP_PASSWORD == "your-gmail-app-password"
    ):

        print(
            "Email is not configured yet."
        )

        return


    try:

        msg = EmailMessage()

        msg["Subject"] = (
            f"New Real Estate Enquiry - {name}"
        )

        msg["From"] = YOUR_EMAIL

        msg["To"] = YOUR_EMAIL


        body = f"""
NEW REAL ESTATE WEBSITE ENQUIRY

================================

Customer Name:
{name}

Phone:
{phone}

Email:
{email}

Property:
{property_name}

Message:
{message}

================================

Please contact the customer.
"""


        msg.set_content(body)


        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465
        ) as smtp:

            smtp.login(
                YOUR_EMAIL,
                YOUR_APP_PASSWORD
            )

            smtp.send_message(msg)


        print(
            "Enquiry email sent successfully."
        )


    except Exception as e:

        print(
            "Email sending failed:"
        )

        print(e)


# =========================================================
# MARK ENQUIRY AS CONTACTED
# =========================================================

@app.route(
    "/admin/enquiry/<int:enquiry_id>/contacted"
)
@admin_required
def mark_contacted(enquiry_id):

    conn = db()

    conn.execute(
        """
        UPDATE enquiries
        SET status='Contacted'
        WHERE id=?
        """,
        (enquiry_id,)
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin")
    )


# =========================================================
# DELETE ENQUIRY
# =========================================================

@app.route(
    "/admin/enquiry/<int:enquiry_id>/delete"
)
@admin_required
def delete_enquiry(enquiry_id):

    conn = db()

    conn.execute(
        """
        DELETE FROM enquiries
        WHERE id=?
        """,
        (enquiry_id,)
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("admin")
    )


# =========================================================
# CONTACT PAGE
# =========================================================

@app.route(
    "/contact",
    methods=["GET", "POST"]
)
def contact():

    if request.method == "POST":

        flash(
            "Thank you! Your enquiry has been received."
        )

        return redirect(
            url_for("contact")
        )

    return render_template(
        "contact.html"
    )


# =========================================================
# SITEMAP
# =========================================================

@app.route("/sitemap.xml")
def sitemap():

    return app.send_static_file(
        "sitemap.xml"
    )


# =========================================================
# ROBOTS
# =========================================================

@app.route("/robots.txt")
def robots():

    return app.send_static_file(
        "robots.txt"
    )


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    init_db()

    app.run(
        host="0.0.0.0",
        port=3000,
        debug=True
    )