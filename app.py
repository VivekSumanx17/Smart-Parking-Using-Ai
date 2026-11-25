from flask import Flask, render_template, request, jsonify, send_file
from ultralytics import YOLO
from shapely.geometry import Polygon, box
from pathlib import Path
from datetime import datetime, timedelta
from threading import Lock
from PIL import Image
import json, uuid, io, base64, math, os
from dotenv import load_dotenv
from flask import session
from db import connection
from auth import auth, current_user
from admin import admin
load_dotenv(Path(__file__).resolve().parent / ".env")

ROOT = Path(__file__).resolve().parent

app = Flask(
    __name__,
    template_folder=str(ROOT / 'templates'),
    static_folder=str(ROOT / 'static')
)

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.secret_key = os.environ['SECRET_KEY']

# Session security settings
app.config.update(
    SESSION_PERMANENT=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE', '0') == '1',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2)
)

app.register_blueprint(auth)
app.register_blueprint(admin)

app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024
ANNOTATION_FILE = ROOT / 'annotations' / 'parking_slots.json'
if not ANNOTATION_FILE.exists():
    ANNOTATION_FILE = ROOT / 'parking_slots.json'
annotations = json.loads(ANNOTATION_FILE.read_text())
model = YOLO(str(ROOT / 'yolo11n.pt'))
lock = Lock()
DB = "MySQL: parkvision"
RATE_PER_HOUR = 30.0  # INR, adjustable demo rate
latest = {'image': None, 'statuses': {str(s['id']): 'unknown' for s in annotations['slots']}}

def active_bookings(start=None, end=None):
    now = datetime.now(); start=start or now; end=end or (now+timedelta(seconds=1))
    with connection() as db:
        with db.cursor() as cur:
            cur.execute("SELECT booking_id AS id,slot_id,guest_name AS customer,start_time,end_time,total_price AS amount,created_at FROM bookings WHERE status IN ('confirmed','pending') AND start_time < %s AND end_time > %s",(end,start))
            return [serialize_booking(b) for b in cur.fetchall()]

def serialize_booking(b):
    return {**b, 'start_time':b['start_time'].isoformat(), 'end_time':b['end_time'].isoformat(), 'created_at':b['created_at'].isoformat(), 'amount':float(b['amount'])}


def all_bookings():
    user = current_user()

    if not user:
        return []

    with connection() as db:
        with db.cursor() as cur:
            cur.execute("""
                SELECT
                    booking_id AS id,
                    slot_id,
                    guest_name AS customer,
                    start_time,
                    end_time,
                    total_price AS amount,
                    status,
                    created_at
                FROM bookings
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (user['id'],))

            return [
                serialize_booking(b)
                for b in cur.fetchall()
            ]



def slot_payload(start=None, end=None):
    now = datetime.now()

    if start is None:
        start = now
    if end is None:
        end = start + timedelta(hours=1)

    with connection() as db:
        with db.cursor() as cur:
            cur.execute(
                "SELECT slot_id, is_occupied FROM scan_state"
            )
            statuses = {
                str(r["slot_id"]): (
                    "occupied" if r["is_occupied"] else "empty"
                )
                for r in cur.fetchall()
            }

            cur.execute(
                """
                SELECT DISTINCT slot_id
                FROM bookings
                WHERE status IN ('confirmed', 'pending')
                  AND start_time < %s
                  AND end_time > %s
                """,
                (end, start)
            )
            booked = {r["slot_id"] for r in cur.fetchall()}

    slots = []

    for s in annotations["slots"]:
        physical_status = statuses.get(str(s["id"]), "unknown")

        if s["id"] in booked:
            status = "booked"
        elif physical_status == "occupied" and start <= now < end:
            status = "occupied"
        elif physical_status == "unknown":
            status = "unknown"
        else:
            status = "empty"

        slots.append({
            "id": s["id"],
            "polygon": s["polygon"],
            "status": status
        })

    return slots


@app.before_request
def expire_inactive_session():
    if 'user_id' not in session:
        return

    now = datetime.now()
    last_activity = session.get('last_activity')

    if last_activity:
        try:
            last = datetime.fromisoformat(last_activity)
            if now - last > timedelta(minutes=30):
                session.clear()
                return
        except (ValueError, TypeError):
            session.clear()
            return

    session['last_activity'] = now.isoformat()


@app.before_request
def protect_mutations():
    if request.method in ('POST','PUT','PATCH','DELETE'):
        origin=request.headers.get('Origin')
        if origin:
            from urllib.parse import urlsplit
            if urlsplit(origin).netloc != request.host:
                return jsonify(error='Cross-origin request rejected'),403

@app.after_request
def no_cache(response):
    if response.mimetype in ('text/html','text/css','application/javascript','application/json'):
        response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response

@app.get('/')
def index():
    return render_template('index.html')


@app.get('/api/state')
def state():
    try:
        start_text = request.args.get("start_time")
        duration = int(request.args.get("duration", 1))
        unit = request.args.get("unit", "hours")

        multiplier = {
            "minutes": 1,
            "hours": 60,
            "days": 1440
        }.get(unit)

        if multiplier is None or duration < 1 or duration > 365:
            raise ValueError("Invalid duration.")

        minutes = duration * multiplier

        if minutes > 30 * 1440:
            raise ValueError("Maximum booking is 30 days.")

        start = (
            datetime.fromisoformat(start_text)
            if start_text
            else datetime.now()
        )

        if start.tzinfo is not None:
            raise ValueError("Use local date and time.")

        end = start + timedelta(minutes=minutes)

        return jsonify(
            slots=slot_payload(start, end),
            image=latest["image"],
            width=annotations["image_width"],
            height=annotations["image_height"],
            rate=RATE_PER_HOUR,
            bookings=all_bookings(),
            database=str(DB),
            user=current_user()
        )

    except (ValueError, TypeError, OverflowError) as exc:
        return jsonify(error=str(exc)), 400


@app.post('/api/detect')
def detect():
    file = request.files.get('image')
    if not file:
        return jsonify(error='Please upload an image.'), 400
    try:
        raw = file.read()
        picture = Image.open(io.BytesIO(raw)).convert('RGB')
        # Normalize images to the annotation coordinate system before detection.
        # This supports different resolutions of the SAME fixed camera view.
        # Different crops/perspectives still require new annotations.
        reference_size = (int(annotations['image_width']), int(annotations['image_height']))
        original_size = picture.size
        if picture.size != reference_size:
            picture = picture.resize(reference_size, Image.Resampling.LANCZOS)
        import numpy as np
        rgb = np.asarray(picture)
        with lock:
            result = model.predict(source=rgb, classes=[2], verbose=False)[0]
        boxes = [box(*map(float, b.xyxy[0].tolist())) for b in result.boxes]
        statuses = {}
        for s in annotations['slots']:
            polygon = Polygon(s['polygon'])
            statuses[str(s['id'])] = 'occupied' if any(polygon.intersection(car).area / polygon.area > 0.50 for car in boxes) else 'empty'
        latest['statuses'] = statuses
        with connection() as db:
            with db.cursor() as cur:
                cur.executemany('INSERT INTO scan_state(slot_id,is_occupied) VALUES (%s,%s) ON DUPLICATE KEY UPDATE is_occupied=VALUES(is_occupied),last_scanned_at=CURRENT_TIMESTAMP', [(int(k),int(v=='occupied')) for k,v in statuses.items()])
            db.commit()
        latest['image'] = 'data:image/jpeg;base64,' + base64.b64encode(_jpeg(picture)).decode()
        return jsonify(
            image=latest["image"],
            count=len(boxes),
            uploaded_width=original_size[0],
            uploaded_height=original_size[1]
        )
    except Exception as exc:
        return jsonify(error=f'Could not process image: {str(exc)}'), 400

def _jpeg(picture):
    stream = io.BytesIO()
    picture.save(stream, format='JPEG', quality=90)
    return stream.getvalue()

@app.post('/api/book')
def book():
    user=current_user()
    if not user: return jsonify(error='Please log in to book a slot.'),401
    payload = request.get_json(silent=True) or {}
    try:
        slot_id = int(payload.get('slot_id'))
        customer = str(payload.get('customer', '')).strip()
        amount_minutes = int(payload.get('duration'))
        unit = str(payload.get('unit'))
        if slot_id not in [s['id'] for s in annotations['slots']] or not customer or len(customer) > 100 or amount_minutes < 1 or amount_minutes > 365:
            raise ValueError('Invalid booking information.')
        multiplier = {'minutes': 1, 'hours': 60, 'days': 1440}.get(unit)
        if multiplier is None:
            raise ValueError('Invalid duration unit.')
        minutes = amount_minutes * multiplier
        if minutes > 30 * 1440:
            raise ValueError('Maximum booking is 30 days.')
        start = datetime.fromisoformat(str(payload.get('start_time')))
        if start.tzinfo is not None:
            raise ValueError('Use local date and time.')
        now = datetime.now()
        if start < now - timedelta(minutes=2) or start > now + timedelta(days=30):
            raise ValueError('Choose a start time within the next 30 days.')
        end = start + timedelta(minutes=minutes)
        with lock:
            with connection() as db:
                with db.cursor() as cur:
                    # Serialize bookings on this slot to prevent simultaneous reservations.
                    cur.execute('SELECT slot_id,is_occupied FROM scan_state WHERE slot_id=%s FOR UPDATE',(slot_id,))
                    scan = cur.fetchone()
                    # Read the current hourly rate from MySQL.
                    cur.execute("""
                                SELECT hourly_rate
                                FROM parking_rates
                                WHERE slot_id = %s
                                    FOR UPDATE
                                """, (slot_id,))

                    rate_row = cur.fetchone()

                    if not rate_row:
                        db.rollback()
                        return jsonify(
                            error="Parking rate not configured for this slot."
                        ), 409

                    hourly_rate = float(rate_row["hourly_rate"])

                    amount = round(
                        math.ceil(minutes / 15) * hourly_rate / 4,
                        2
                    )

                    if not scan:
                        db.rollback()
                        return jsonify(
                            error="Slot has no scan information."
                        ), 409

                    if scan["is_occupied"] and start <= now < end:
                        db.rollback()
                        return jsonify(
                            error="Slot is currently occupied."
                        ), 409
                    cur.execute("SELECT booking_id FROM bookings WHERE slot_id=%s AND status IN ('pending','confirmed') AND start_time < %s AND end_time > %s LIMIT 1",(slot_id,end,start))
                    if cur.fetchone():
                        db.rollback(); return jsonify(error='Slot is already booked for the selected period.'),409
                    booking_id=uuid.uuid4().hex[:10].upper()
                    cur.execute("INSERT INTO bookings(booking_id,user_id,slot_id,guest_name,guest_email,vehicle_number,start_time,end_time,total_price,status,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'confirmed',%s)",(booking_id,user['id'],slot_id,user['full_name'],user['email'],None,start,end,amount,now))
                db.commit()
        return jsonify(booking_id=booking_id, id=booking_id, slot_id=slot_id, customer=customer, amount=amount, start_time=start.isoformat(), end_time=end.isoformat(), duration=amount_minutes, unit=unit, payment='SIMULATED', created_at=now.isoformat()), 201
    except (ValueError, TypeError, OverflowError) as exc:
        return jsonify(error=str(exc)), 400

@app.get('/api/bookings')
def bookings_api():
    if not current_user(): return jsonify(error="Login required"),401
    return jsonify(bookings=all_bookings())

@app.get('/api/rates')
def get_parking_rates():
    with connection() as db:
        with db.cursor() as cur:
            cur.execute("""
                SELECT slot_id, hourly_rate
                FROM parking_rates
                ORDER BY slot_id
            """)
            rows = cur.fetchall()

    rates = {
        str(row['slot_id']): float(row['hourly_rate'])
        for row in rows
    }

    return jsonify(rates=rates)

@app.get('/api/bookings/<booking_id>/receipt')
def receipt(booking_id):
    user=current_user()
    if not user: return jsonify(error='Login required'),401
    with connection() as db:
        with db.cursor() as cur:
            cur.execute('SELECT booking_id AS id,slot_id,guest_name AS customer,start_time,end_time,total_price AS amount,created_at FROM bookings WHERE booking_id=%s AND user_id=%s',(booking_id,user['id']))
            row=cur.fetchone()
    if not row:
        return jsonify(error='Booking not found'), 404
    b = serialize_booking(row)
    lines = ['PARKVISION - BOOKING RECEIPT', '='*35, f"Booking ID: {b['id']}", f"Customer: {b['customer']}", f"Parking slot: {b['slot_id']}", f"Start: {b['start_time']}", f"End: {b['end_time']}", f"Amount: INR {b['amount']:.2f}", 'Payment: SIMULATED - NO REAL CHARGE', '='*35]
    return send_file(io.BytesIO(('\n'.join(lines)+'\n').encode('utf-8')), mimetype='text/plain', as_attachment=True, download_name=f"ParkVision_Receipt_{booking_id}.txt")

if __name__ == '__main__':
    app.run(debug=False, port=5000)
