from flask import request
from datetime import datetime
from functools import wraps
from flask import Blueprint, jsonify, render_template, request
from flask import Blueprint, jsonify, render_template
from auth import current_user
from db import connection
from datetime import datetime, timedelta
from flask import request
admin = Blueprint("admin", __name__)


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = current_user()

        if not user:
            return jsonify(error="Please log in first."), 401

        if user["role"] != "admin" or not user["is_active"]:
            return jsonify(error="Admin access required."), 403

        return func(*args, **kwargs)

    return wrapper


@admin.get("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin.html")


@admin.get("/api/admin/stats")
@admin_required
def admin_stats():
    with connection() as db:
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM parking_slots")
            total_slots = cur.fetchone()["total"]

            cur.execute(
                "SELECT COUNT(*) AS total FROM users WHERE role = 'customer'"
            )
            total_customers = cur.fetchone()["total"]

            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM bookings
                WHERE status IN ('confirmed', 'pending')
                """
            )
            total_bookings = cur.fetchone()["total"]

            cur.execute(
                """
                SELECT COALESCE(SUM(total_price), 0) AS total
                FROM bookings
                WHERE status = 'confirmed'
                """
            )
            total_revenue = float(cur.fetchone()["total"])

            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM scan_state
                WHERE is_occupied = 1
                """
            )
            occupied_slots = cur.fetchone()["total"]

    return jsonify(
        total_slots=total_slots,
        total_customers=total_customers,
        total_bookings=total_bookings,
        total_revenue=total_revenue,
        occupied_slots=occupied_slots
    )

@admin.get("/api/admin/bookings")
@admin_required
def admin_bookings():
    with connection() as db:
        with db.cursor() as cur:
            cur.execute("""
                SELECT
                    b.booking_id,
                    b.slot_id,
                    b.guest_name,
                    b.guest_email,
                    b.vehicle_number,
                    b.start_time,
                    b.end_time,
                    b.total_price,
                    b.status,
                    u.full_name AS account_name,
                    u.email AS account_email
                FROM bookings b
                LEFT JOIN users u ON b.user_id = u.user_id
                ORDER BY b.start_time DESC
            """)
            rows = cur.fetchall()

    bookings = []

    for b in rows:
        bookings.append({
            "booking_id": b["booking_id"],
            "slot_id": b["slot_id"],
            "customer": b["guest_name"],
            "email": b["guest_email"] or b["account_email"],
            "vehicle_number": b["vehicle_number"],
            "start_time": b["start_time"].isoformat(),
            "end_time": b["end_time"].isoformat(),
            "amount": float(b["total_price"]),
            "status": b["status"]
        })

    return jsonify(bookings=bookings)


@admin.post("/api/admin/bookings/<booking_id>/cancel")
@admin_required
def admin_cancel_booking(booking_id):
    with connection() as db:
        with db.cursor() as cur:
            cur.execute("""
                UPDATE bookings
                SET status = 'cancelled'
                WHERE booking_id = %s
                  AND status IN ('confirmed', 'pending')
            """, (booking_id,))

            changed = cur.rowcount

        db.commit()

    if changed == 0:
        return jsonify(
            error="Booking not found or already inactive."
        ), 404

    return jsonify(
        message="Booking cancelled successfully.",
        booking_id=booking_id
    )

from decimal import Decimal, InvalidOperation


@admin.get('/api/admin/slots')
@admin_required
def admin_slots():
    with connection() as db:
        with db.cursor() as cur:
            cur.execute("""
                SELECT
                    p.slot_id,
                    p.hourly_rate,
                    COALESCE(s.is_occupied, 0) AS is_occupied
                FROM parking_rates p
                LEFT JOIN scan_state s
                    ON p.slot_id = s.slot_id
                ORDER BY p.slot_id
            """)
            rows = cur.fetchall()

    slots = [
        {
            "slot_id": row["slot_id"],
            "hourly_rate": float(row["hourly_rate"]),
            "status": (
                "Occupied" if row["is_occupied"]
                else "Empty"
            )
        }
        for row in rows
    ]

    return jsonify(slots=slots)


@admin.put('/api/admin/slots/<int:slot_id>/rate')
@admin_required
def update_slot_rate(slot_id):
    data = request.get_json(silent=True) or {}

    try:
        rate = Decimal(str(data.get("hourly_rate")))

        if not rate.is_finite():
            raise ValueError()

        if rate <= 0 or rate > 10000:
            raise ValueError()

        if rate.as_tuple().exponent < -2:
            raise ValueError()

    except (InvalidOperation, ValueError, TypeError):
        return jsonify(
            error="Enter a valid hourly rate between ₹0.01 and ₹10,000."
        ), 400

    user = current_user()

    with connection() as db:
        with db.cursor() as cur:
            cur.execute("""
                UPDATE parking_rates
                SET hourly_rate = %s,
                    updated_by = %s,
                    updated_at = NOW()
                WHERE slot_id = %s
            """, (rate, user["id"], slot_id))

            changed = cur.rowcount

        db.commit()

    if changed == 0:
        return jsonify(error="Slot not found or rate unchanged."), 404

    return jsonify(
        message="Parking rate updated successfully.",
        slot_id=slot_id,
        hourly_rate=float(rate)
    )

# =====================================================
# CUSTOMER MANAGEMENT
# =====================================================

@admin.get('/api/admin/customers')
@admin_required
def admin_customers():
    with connection() as db:
        with db.cursor() as cur:
            cur.execute("""
                SELECT
                    u.user_id,
                    u.full_name,
                    u.email,
                    u.phone,
                    u.email_verified,
                    u.is_active,
                    u.created_at,
                    COUNT(b.booking_id) AS total_bookings
                FROM users u
                LEFT JOIN bookings b
                    ON b.user_id = u.user_id
                WHERE u.role = 'customer'
                GROUP BY
                    u.user_id,
                    u.full_name,
                    u.email,
                    u.phone,
                    u.email_verified,
                    u.is_active,
                    u.created_at
                ORDER BY u.created_at DESC
            """)

            rows = cur.fetchall()

    customers = [
        {
            "user_id": row["user_id"],
            "full_name": row["full_name"],
            "email": row["email"],
            "phone": row["phone"],
            "email_verified": bool(row["email_verified"]),
            "is_active": bool(row["is_active"]),
            "created_at": (
                row["created_at"].isoformat()
                if row["created_at"] else None
            ),
            "total_bookings": row["total_bookings"]
        }
        for row in rows
    ]

    return jsonify(customers=customers)


@admin.patch('/api/admin/customers/<int:user_id>/status')
@admin_required
def update_customer_status(user_id):
    data = request.get_json(silent=True) or {}

    if type(data.get("is_active")) is not bool:
        return jsonify(
            error="is_active must be true or false."
        ), 400

    active = int(data["is_active"])

    with connection() as db:
        with db.cursor() as cur:
            cur.execute("""
                UPDATE users
                SET is_active = %s
                WHERE user_id = %s
                  AND role = 'customer'
            """, (active, user_id))

            if cur.rowcount == 0:
                cur.execute("""
                    SELECT is_active
                    FROM users
                    WHERE user_id = %s
                      AND role = 'customer'
                """, (user_id,))

                existing = cur.fetchone()

                if not existing:
                    return jsonify(
                        error="Customer not found."
                    ), 404

        db.commit()

    return jsonify(
        message="Customer status updated successfully.",
        user_id=user_id,
        is_active=bool(active)
    )


@admin.get('/api/admin/customers/<int:user_id>/bookings')
@admin_required
def customer_booking_history(user_id):
    with connection() as db:
        with db.cursor() as cur:
            cur.execute("""
                SELECT user_id
                FROM users
                WHERE user_id = %s
                  AND role = 'customer'
            """, (user_id,))

            if not cur.fetchone():
                return jsonify(
                    error="Customer not found."
                ), 404

            cur.execute("""
                SELECT
                    booking_id,
                    slot_id,
                    start_time,
                    end_time,
                    total_price,
                    status
                FROM bookings
                WHERE user_id = %s
                ORDER BY start_time DESC
            """, (user_id,))

            rows = cur.fetchall()

    bookings = [
        {
            "booking_id": row["booking_id"],
            "slot_id": row["slot_id"],
            "start_time": row["start_time"].isoformat(),
            "end_time": row["end_time"].isoformat(),
            "amount": float(row["total_price"]),
            "status": row["status"]
        }
        for row in rows
    ]

    return jsonify(bookings=bookings)

# =====================================================
# REPORTS AND ANALYTICS
# =====================================================

@admin.get('/api/admin/reports')
@admin_required
def admin_reports():
    today = datetime.now().date()

    try:
        start = datetime.strptime(
            request.args.get('start', str(today - timedelta(days=29))),
            '%Y-%m-%d'
        ).date()

        end = datetime.strptime(
            request.args.get('end', str(today)),
            '%Y-%m-%d'
        ).date()

        if start > end:
            return jsonify(error="Start date must be before end date."), 400

        if (end - start).days > 365:
            return jsonify(error="Maximum report range is 366 days."), 400

    except ValueError:
        return jsonify(error="Invalid date format. Use YYYY-MM-DD."), 400

    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(
        end + timedelta(days=1),
        datetime.min.time()
    )

    with connection() as db:
        with db.cursor() as cur:

            # Summary statistics
            cur.execute("""
                SELECT
                    COUNT(*) AS total_bookings,
                    SUM(status = 'confirmed') AS confirmed,
                    SUM(status = 'cancelled') AS cancelled,
                    SUM(status = 'pending') AS pending,
                    COALESCE(
                        SUM(
                            CASE WHEN status = 'confirmed'
                            THEN total_price ELSE 0 END
                        ), 0
                    ) AS booking_value
                FROM bookings
                WHERE start_time >= %s
                AND start_time < %s
            """, (start_dt, end_dt))

            summary = cur.fetchone()

            # Daily booking trends
            cur.execute("""
                SELECT
                    DATE(start_time) AS day,
                    COUNT(*) AS bookings,
                    COALESCE(
                        SUM(
                            CASE WHEN status = 'confirmed'
                            THEN total_price ELSE 0 END
                        ), 0
                    ) AS booking_value
                FROM bookings
                WHERE start_time >= %s
                  AND start_time < %s
                GROUP BY DATE(start_time)
                ORDER BY day
            """, (start_dt, end_dt))

            daily_rows = cur.fetchall()

            # Slot-wise statistics
            cur.execute("""
                SELECT
                    p.slot_id,
                    COUNT(b.booking_id) AS total_bookings,
                    COALESCE(
                        SUM(
                            CASE WHEN b.status = 'confirmed'
                            THEN b.total_price ELSE 0 END
                        ), 0
                    ) AS booking_value
                FROM parking_slots p
                LEFT JOIN bookings b
                    ON p.slot_id = b.slot_id
                   AND b.start_time >= %s
                    AND b.start_time < %s
                GROUP BY p.slot_id
                ORDER BY p.slot_id
            """, (start_dt, end_dt))

            slot_rows = cur.fetchall()

            # Detailed booking records
            cur.execute("""
                SELECT
                    booking_id,
                    slot_id,
                    guest_name AS customer,
                    created_at,
                    start_time,
                    end_time,
                    total_price,
                    status
                FROM bookings
                WHERE start_time >= %s
                  AND start_time < %s
                ORDER BY start_time ASC
            """, (start_dt, end_dt))

            booking_rows = cur.fetchall()

    return jsonify(
        start=str(start),
        end=str(end),
        summary={
            "total_bookings": summary["total_bookings"],
            "confirmed": summary["confirmed"] or 0,
            "cancelled": summary["cancelled"] or 0,
            "pending": summary["pending"] or 0,
            "booking_value": float(summary["booking_value"])
        },
        daily=[
            {
                "date": str(row["day"]),
                "bookings": row["bookings"],
                "booking_value": float(row["booking_value"])
            }
            for row in daily_rows
        ],

        slots=[
            {
                "slot_id": row["slot_id"],
                "total_bookings": row["total_bookings"],
                "booking_value": float(row["booking_value"])
            }
            for row in slot_rows
        ],
        bookings=[
            {
                "booking_id": row["booking_id"],
                "slot_id": row["slot_id"],
                "customer": row["customer"],
                "created_at": row["created_at"].isoformat(),
                "start_time": row["start_time"].isoformat(),
                "end_time": row["end_time"].isoformat(),
                "total_price": float(row["total_price"]),
                "status": row["status"]
            }
            for row in booking_rows
        ]
    )
