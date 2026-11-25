# 🚗 ParkVision --- AI-Powered Smart Parking Management System {#red_car-parkvision--ai-powered-smart-parking-management-system}

![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python) ![Flask](https://img.shields.io/badge/Flask-Backend-black?logo=flask) ![MySQL](https://img.shields.io/badge/MySQL-Database-blue?logo=mysql) ![YOLO11](https://img.shields.io/badge/YOLO11-Object%20Detection-purple) ![JavaScript](https://img.shields.io/badge/JavaScript-Frontend-yellow?logo=javascript) ![Status](https://img.shields.io/badge/Status-Prototype-orange)

## Overview

ParkVision is an AI-powered smart parking management prototype that combines computer vision with time-based parking reservations. It uses Ultralytics YOLO11 to detect cars in uploaded parking-area images and maps detections to predefined parking-slot polygons. Customers can check availability, reserve slots, view booking history and download receipts. Administrators can manage reservations, pricing, customers and analytical reports.

The project aims to reduce manual parking management, improve visibility of available spaces and prevent conflicting reservations.

## Key Features

### AI Parking Detection

-   Car detection using the YOLO11n pretrained model.
-   Image upload and processing through the Flask backend.
-   Polygon-based parking-slot occupancy detection using Shapely.
-   Color-coded parking slots: green (available), red (occupied), purple (booked), gray (unknown).
-   Image resizing to match the reference annotation dimensions.

### Customer Features

-   Guest access to parking availability.
-   Customer registration and email OTP verification.
-   Secure password hashing and login/logout.
-   Future parking reservations in minutes, hours or days.
-   Time-based availability and overlapping reservation prevention.
-   Slot-specific pricing and simulated payment confirmation.
-   Personal booking history and downloadable text receipts.

### Admin Features

-   Role-based admin authentication.
-   Dashboard statistics and booking management.
-   Booking cancellation and customer management.
-   Parking-slot rate management.
-   Reports filtered by scheduled parking start date.
-   Daily booking trends, slot-wise performance and booking value summaries.
-   Detailed booking records with creation date, parking start/end, duration, amount and status.
-   CSV report export.

## Technology Stack

  Layer                Technology
  -------------------- -------------------------------------------
  Frontend             HTML, CSS, JavaScript, SVG
  Backend              Python, Flask
  Database             MySQL, PyMySQL
  Computer vision      Ultralytics YOLO11n
  Image processing     Pillow, NumPy
  Spatial analysis     Shapely
  Authentication       Flask sessions, Werkzeug password hashing
  Email verification   SMTP, Gmail app password
  Configuration        python-dotenv

## System Architecture

``` mermaid
flowchart TD
    U[Guest / Customer / Admin] --> F[Web Interface]
    F --> A[Flask REST API]
    A --> AU[Authentication and OTP]
    A --> D[Parking Detection]
    A --> B[Booking and Pricing]
    A --> R[Admin and Reports]
    D --> Y[YOLO11n]
    Y --> P[Polygon Occupancy Analysis]
    P --> DB[(MySQL Database)]
    AU --> DB
    AU --> M[SMTP Email Service]
    B --> DB
    R --> DB
```

## How Parking Detection Works

1.  Upload an image of the configured parking area.
2.  Resize the image to the reference annotation dimensions if necessary.
3.  Run YOLO11n inference for the COCO car class (class ID 2).
4.  Compare detected car bounding boxes against predefined parking-slot polygons.
5.  Mark a slot as physically occupied when a detected car overlaps more than 50% of its polygon area.
6.  Save occupancy information to MySQL and combine it with reservations for the selected time interval.
7.  Display the resulting parking status through the web interface.

Images must represent the same fixed camera view as the annotations. Different perspectives or crops require new annotations. Physical occupancy is based on the most recent uploaded image, not a live video feed.

## Booking Logic

Two reservations conflict when they refer to the same slot, have a blocking status (pending or confirmed), and satisfy:

``` text
existing_start < requested_end AND existing_end > requested_start
```

Adjacent reservations are allowed because an existing reservation ending exactly when a new one starts does not overlap.

The backend uses database row locking and checks for conflicts before inserting a reservation. Cancelled bookings do not block availability. Expired booking intervals no longer block subsequent time periods.

### Pricing

The system reads the slot\'s hourly rate from MySQL and rounds the requested duration up to the next 15-minute billing interval:

``` text
Amount = ceil(duration_in_minutes / 15) × hourly_rate / 4
```

Example: At ₹30 per hour, a 50-minute reservation costs ₹30. Rates can be changed by the administrator. Payments are simulated for demonstration purposes.

## Project Structure

The following shows the main known components; additional assets, scripts and SQL files may exist in the repository.

``` text
ParkVision/
├── app.py                  # Flask application, detection and booking APIs
├── auth.py                 # Registration, login and email verification
├── admin.py                # Admin routes and reporting
├── db.py                   # MySQL connection helper
├── config.py               # Configuration, if retained in the project
├── migrate_sqlite_to_mysql.py  # Migration utility, if retained
├── annotations/
│   └── parking_slots.json  # Reference dimensions and slot polygons
├── templates/
│   ├── index.html
│   ├── login.html
│   ├── signup.html
│   ├── verify.html
│   └── admin.html
├── static/
│   ├── app.js
│   ├── admin.js
│   ├── style.css
│   └── auth.css
├── yolo11n.pt              # YOLO model weights (obtain separately if excluded)
├── .env                    # Local secrets (never commit)
├── .env.example            # Recommended public configuration template
├── requirements.txt        # Recommended dependency manifest
├── .gitignore
└── README.md
```

## Installation and Setup

### 1. Prerequisites {#1-prerequisites}

-   Python 3 with a version supported by the installed PyTorch and Ultralytics packages
-   MySQL Server (MySQL Workbench is optional)
-   Git
-   Gmail account with an app password for OTP delivery

### 2. Clone the repository {#2-clone-the-repository}

Replace the placeholders with the actual GitHub username and repository name.

``` bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

### 3. Create a virtual environment {#3-create-a-virtual-environment}

Windows PowerShell:

``` powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install dependencies {#4-install-dependencies}

If the repository includes a requirements file:

``` bash
pip install -r requirements.txt
```

Otherwise, install the known core dependencies:

``` bash
pip install flask ultralytics shapely pillow numpy python-dotenv pymysql werkzeug
```

Use the working development environment to generate and verify the final dependency manifest before publishing.

### 5. Configure MySQL {#5-configure-mysql}

Create the database:

``` sql
CREATE DATABASE IF NOT EXISTS parkvision CHARACTER SET utf8mb4;
```

Import the project\'s actual MySQL schema and required initial slot/rate records using MySQL Workbench or the MySQL CLI. Creating an empty database alone is not sufficient. The schema export is not included in this README; the repository maintainer should provide a sanitized schema-only SQL file and any necessary seed data.

Main database tables:

  Table             Purpose
  ----------------- ------------------------------------------
  `users`           Customer and administrator accounts
  `email_otps`      Verification codes, expiry and attempts
  `parking_slots`   Parking-slot definitions
  `parking_rates`   Slot-specific hourly rates
  `scan_state`      Latest physical occupancy information
  `bookings`        Reservations, dates, prices and status
  `payments`        Payment-related records where configured

### 6. Configure environment variables {#6-configure-environment-variables}

Create a `.env` file in the project root. Example configuration (replace placeholders):

``` dotenv
DATABASE_URL=mysql+pymysql://YOUR_DB_USER:YOUR_DB_PASSWORD@localhost:3306/parkvision
SECRET_KEY=YOUR_RANDOM_SECRET_KEY
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password
SMTP_FROM=your_email@gmail.com
COOKIE_SECURE=0
```

Check `db.py` and `config.py` for the exact database variables required by your version. URL-encode special characters in the database password when using a connection URL.

Generate a random secret key:

``` bash
python -c "import secrets; print(secrets.token_hex(32))"
```

For Gmail OTP, enable two-step verification and create an app password if your Google account supports it. Never publish real credentials. Use `COOKIE_SECURE=1` when deploying behind HTTPS.

### 7. Prepare model and annotations {#7-prepare-model-and-annotations}

Ensure `yolo11n.pt` is available in the project root. If necessary, obtain it using Ultralytics from that directory:

``` bash
python -c "from ultralytics import YOLO; YOLO('yolo11n.pt')"
```

Provide `annotations/parking_slots.json` (or `parking_slots.json` in the root), containing the actual reference image dimensions and slot polygon coordinates. Use matching parking-area images and initialize the corresponding database slot and rate records.

### 8. Run the application {#8-run-the-application}

``` bash
python app.py
```

Open <http://127.0.0.1:5000> in your browser.

Register a customer through the signup page. Provision an administrator separately using the database schema and a Werkzeug-generated password hash; do not publish default admin credentials.

## Selected API Endpoints

  Method   Endpoint                               Purpose
  -------- -------------------------------------- --------------------------------------------
  GET      `/`                                    Parking interface
  GET      `/api/state`                           Parking state for a selected time interval
  POST     `/api/detect`                          Upload and process parking image
  GET      `/api/rates`                           Read slot rates
  POST     `/api/book`                            Create authenticated reservation
  GET      `/api/bookings`                        Customer booking history
  GET      `/api/bookings/<booking_id>/receipt`   Download booking receipt
  POST     `/api/auth/signup`                     Register and request OTP
  POST     `/api/auth/verify`                     Verify email OTP
  POST     `/api/auth/login`                      Authenticate account
  POST     `/api/auth/logout`                     Clear login session
  GET      `/api/auth/me`                         Current user information
  GET      `/admin`                               Admin dashboard
  GET      `/api/admin/reports`                   Admin reports and date filtering

Example report request: `/api/admin/reports?start=2026-11-01&end=2026-11-30`. Reports group bookings by scheduled start date rather than creation date. Booking value is not verified payment revenue.

## Security and Testing

-   Password hashing with Werkzeug.
-   Hashed email OTPs, ten-minute expiry, retry limits and resend throttling.
-   Role-based access restrictions and authenticated booking history/receipts.
-   HTTP-only session cookies and SameSite configuration.
-   Parameterized SQL queries and booking conflict checks.
-   Browser-session login configuration and explicit logout. Browser session restoration can retain cookies; shared-device users should always log out.

Authentication testing has passed for guest mode, guest booking restrictions, guest/admin restrictions, customer/admin restrictions and admin login. Further booking boundary, database integrity, detection accuracy and end-to-end tests are part of the ongoing validation phase. No benchmark accuracy or production security certification is claimed.

## Screenshots

Add screenshots of the following screens to the repository to demonstrate the project:

-   Parking detection and availability interface
-   Customer login and booking history
-   Booking confirmation and receipt
-   Admin dashboard and rate management
-   Reports and analytics

## Current Limitations

-   Fixed-camera image upload prototype; no live CCTV stream.
-   Occupancy depends on the latest image and detection quality.
-   Annotations must match the camera perspective.
-   Simulated payments; no real payment gateway.
-   Local Flask development server is not intended for production deployment.

## Future Enhancements

-   Real-time CCTV or IP camera integration.
-   Multiple parking locations and camera views.
-   Real payment gateway and payment verification.
-   SMS OTP and reservation notifications.
-   Improved vehicle detection and occupancy evaluation.
-   Mobile-friendly deployment and navigation to parking locations.
-   Production deployment, stronger session management and automated tests.

## Contributing

Suggestions and improvements are welcome. Fork the repository, create a feature branch, commit your changes and open a pull request. Avoid including secrets, private customer information or database dumps containing personal records.

## License and Acknowledgments

A repository license should be selected by the project owner before granting reuse rights. Review the applicable Ultralytics YOLO licensing terms and other third-party dependency licenses before distributing or deploying the project.

Built using Python, Flask, MySQL, Ultralytics YOLO11 and the open-source Python ecosystem.

------------------------------------------------------------------------

**ParkVision --- Smarter Parking Through Artificial Intelligence.**
