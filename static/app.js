
/* =========================================================
   PARKVISION - CUSTOMER PARKING SYSTEM
   Features:
   - Customer authentication
   - YOLO parking detection
   - Time-based slot availability
   - Individual slot pricing from MySQL
   - Parking reservations
   - Booking history and receipts
   ========================================================= */


// =========================================================
// 1. GLOBAL VARIABLES AND HELPERS
// =========================================================

const $ = (id) => document.getElementById(id);

let state = {
    slots: [],
    bookings: []
};

let latestReceipt = null;
let signedInUser = null;
let parkingRates = {};
let refreshVersion = 0;

const money = (amount) => {
    return '₹' + Number(amount).toFixed(2);
};

const nowLocal = () => {
    const date = new Date();

    return new Date(
        date.getTime() - date.getTimezoneOffset() * 60000
    ).toISOString().slice(0, 16);
};

function escapeHtml(value) {
    return String(value ?? '').replace(
        /[&<>"']/g,
        (char) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[char])
    );
}

function message(text, type = 'info', target = 'message') {
    const element = $(target);

    element.hidden = false;
    element.textContent = text;
    element.className =
        'notice ' + (type === 'info' ? '' : type);
}


// =========================================================
// 2. CUSTOMER AUTHENTICATION
// =========================================================

async function loadAccount() {
    const response = await fetch('/api/auth/me');
    const data = await response.json();

    signedInUser = data.user;

    const accountBar = $('accountBar');

    if (signedInUser) {
        accountBar.innerHTML = `
            Signed in as <strong></strong> ·
            <button type="button" id="logout">
                Log out
            </button>
        `;

        accountBar.querySelector('strong').textContent =
            signedInUser.full_name;

        $('customer').value = signedInUser.full_name;
        $('customer').readOnly = true;

        $('logout').onclick = async () => {
            await fetch('/api/auth/logout', {
                method: 'POST'
            });

            location.reload();
        };

    } else {
        accountBar.innerHTML = `
            <a href="/login">Log in</a> ·
            <a href="/signup">Sign up</a>
        `;

        $('customer').placeholder =
            'Log in to make a reservation';

        $('bookingForm')
            .querySelector('button[type=submit]')
            .textContent = 'Log in to book →';
    }
}


// =========================================================
// 3. PARKING RATES FROM MYSQL
// =========================================================

async function loadParkingRates() {
    const response = await fetch('/api/rates');

    if (!response.ok) {
        throw new Error('Unable to load parking rates.');
    }

    const data = await response.json();

    parkingRates = data.rates || {};

    updatePrice();
}


// =========================================================
// 4. DYNAMIC BOOKING PRICE CALCULATION
// =========================================================

function pricing() {
    const slotId = $('slot').value;

    if (!slotId) {
        return null;
    }

    const hourlyRate = parkingRates[slotId];

    if (hourlyRate === undefined) {
        return null;
    }

    const duration = Number($('duration').value) || 0;

    const multiplier = {
        minutes: 1,
        hours: 60,
        days: 1440
    }[$('unit').value];

    if (!multiplier || duration <= 0) {
        return null;
    }

    const totalMinutes = duration * multiplier;

    return Math.ceil(totalMinutes / 15) * hourlyRate / 4;
}

function updatePrice() {
    const amount = pricing();

    $('amount').textContent =
        amount === null
            ? 'Select a slot'
            : money(amount);
}


// =========================================================
// 5. INITIAL DATE AND FORM EVENTS
// =========================================================

$('start').value = nowLocal();
$('start').min = nowLocal();

['duration', 'unit'].forEach((id) => {
    $(id).addEventListener('input', () => {
        updatePrice();
        refresh();
    });
});

$('start').addEventListener('change', refresh);

$('slot').addEventListener('change', updatePrice);


// =========================================================
// 6. BOOKING RECEIPTS
// =========================================================

function receiptText(booking) {
    return [
        'PARKVISION - PARKING BOOKING RECEIPT',
        '===================================',
        `Booking ID: ${booking.id || booking.booking_id}`,
        `Customer: ${booking.customer}`,
        `Parking slot: ${booking.slot_id}`,
        `Start: ${booking.start_time.replace('T', ' ')}`,
        `End: ${booking.end_time.replace('T', ' ')}`,
        `Amount: INR ${Number(booking.amount).toFixed(2)}`,
        'Payment: SIMULATED (no real payment charged)',
        '===================================',
        'This receipt is for prototype demonstration only.'
    ].join('\n');
}

function downloadReceipt(booking) {
    const bookingId = booking.id || booking.booking_id;

    const link = document.createElement('a');

    link.href =
        '/api/bookings/' +
        encodeURIComponent(bookingId) +
        '/receipt';

    link.download =
        'ParkVision_Receipt_' + bookingId + '.txt';

    document.body.appendChild(link);

    link.click();
    link.remove();
}


// =========================================================
// 7. BOOKING DETAILS HTML
// =========================================================

function bookingDetails(booking) {
    return `
        <dl>
            <div>
                <dt>Booking ID</dt>
                <dd>${escapeHtml(booking.id)}</dd>
            </div>

            <div>
                <dt>Customer</dt>
                <dd>${escapeHtml(booking.customer)}</dd>
            </div>

            <div>
                <dt>Slot number</dt>
                <dd>${escapeHtml(booking.slot_id)}</dd>
            </div>

            <div>
                <dt>Amount</dt>
                <dd>${money(booking.amount)}</dd>
            </div>

            <div>
                <dt>Start</dt>
                <dd>
                    ${escapeHtml(
                        booking.start_time.replace('T', ' ')
                    )}
                </dd>
            </div>

            <div>
                <dt>End</dt>
                <dd>
                    ${escapeHtml(
                        booking.end_time.replace('T', ' ')
                    )}
                </dd>
            </div>

            <div>
                <dt>Payment</dt>
                <dd>Demo payment</dd>
            </div>

            <div>
                <dt>Booked on</dt>
                <dd>
                    ${escapeHtml(
                        booking.created_at.replace('T', ' ')
                    )}
                </dd>
            </div>
        </dl>

        <button
            class="secondary-btn receipt-download"
            type="button"
            data-id="${escapeHtml(booking.id)}">
            ↓ Download receipt
        </button>
    `;
}


// =========================================================
// 8. RENDER PARKING SLOTS AND BOOKINGS
// =========================================================

function render(data) {
    state = {
        ...state,
        ...data
    };

    const slots = state.slots || [];

    // Update parking statistics
    $('total').textContent =
        String(slots.length).padStart(2, '0');

    $('available').textContent =
        String(
            slots.filter(s => s.status === 'empty').length
        ).padStart(2, '0');

    $('occupied').textContent =
        String(
            slots.filter(
                s => s.status === 'occupied' ||
                     s.status === 'booked'
            ).length
        ).padStart(2, '0');

    $('reserved').textContent =
        String(
            slots.filter(s => s.status === 'booked').length
        ).padStart(2, '0');

    // Display analyzed parking image
    if (state.image) {
        $('photo').src = state.image;
        $('photo').hidden = false;

        $('overlay').hidden = false;
        $('emptyview').hidden = true;
    }

    // Rebuild available slot dropdown
    const selectedSlot = $('slot').value;

    $('slot').innerHTML =
        '<option value="">Select available slot</option>' +
        slots
            .filter(s => s.status === 'empty')
            .map(s => `
                <option value="${s.id}">
                    Slot ${s.id} — Available
                </option>
            `)
            .join('');

    // Preserve previous selection when possible
    const slotExists = [...$('slot').options].some(
        option => option.value === selectedSlot
    );

    if (slotExists) {
        $('slot').value = selectedSlot;
    }

    updatePrice();

    // Draw parking polygons
    const svg = $('overlay');
    svg.innerHTML = '';

    const colors = {
        empty: ['#0bbf8c', '#03a877'],
        occupied: ['#ef5555', '#d84141'],
        booked: ['#a078ef', '#8e66df'],
        unknown: ['#8a9bab', '#748598']
    };

    for (const slot of slots) {
        const namespace = 'http://www.w3.org/2000/svg';

        const polygon = document.createElementNS(
            namespace,
            'polygon'
        );

        const label = document.createElementNS(
            namespace,
            'text'
        );

        polygon.setAttribute(
            'points',
            slot.polygon
                .map(point => point.join(','))
                .join(' ')
        );

        polygon.setAttribute(
            'fill',
            colors[slot.status][0]
        );

        polygon.setAttribute('fill-opacity', '.32');

        polygon.setAttribute(
            'stroke',
            colors[slot.status][1]
        );

        polygon.setAttribute('class', 'slot-shape');

        // Click a parking slot on the image
        polygon.addEventListener('click', () => {
            if (slot.status === 'empty') {
                $('slot').value = String(slot.id);

                updatePrice();

                $('slot').scrollIntoView({
                    behavior: 'smooth',
                    block: 'center'
                });

            } else {
                message(
                    `Slot ${slot.id} is ${
                        slot.status === 'booked'
                            ? 'already reserved'
                            : slot.status
                    }.`,
                    'error'
                );
            }
        });

        // Slot number position
        const centerX =
            slot.polygon.reduce(
                (sum, point) => sum + point[0],
                0
            ) / slot.polygon.length;

        const centerY =
            slot.polygon.reduce(
                (sum, point) => sum + point[1],
                0
            ) / slot.polygon.length;

        label.setAttribute('x', centerX);
        label.setAttribute('y', centerY);

        label.setAttribute('text-anchor', 'middle');
        label.setAttribute('dominant-baseline', 'middle');
        label.setAttribute('class', 'slot-label');

        label.textContent = String(slot.id);

        svg.append(polygon, label);
    }

    // Display booking history

const bookings = state.bookings || [];

$('dbStatus').textContent =
    bookings.length + ' total booking(s)';

const opened = new Set(
    [...document.querySelectorAll('.bookingitem[open]')]
        .map(element => element.dataset.id)
);

$('bookings').innerHTML = bookings.length
    ? bookings.map(booking => {

        const status = booking.status || 'confirmed';

        let statusLabel = status;

        if (status === 'cancelled') {
            statusLabel = 'Cancelled by Admin';
        } else if (status === 'confirmed') {
            statusLabel = 'Confirmed';
        } else if (status === 'pending') {
            statusLabel = 'Pending';
        } else if (status === 'completed') {
            statusLabel = 'Completed';
        }

        return `
            <details
                class="bookingitem"
                data-id="${escapeHtml(booking.id)}"
                ${opened.has(booking.id) ? 'open' : ''}>

                <summary class="booking-summary">
                    <span>
                        <b>Slot ${booking.slot_id}</b>
                        · ${escapeHtml(booking.customer)}

                        <small>
                            ${escapeHtml(
                                booking.start_time.replace('T', ' ')
                            )}
                            · Booking #${escapeHtml(booking.id)}
                        </small>

                        <small class="customer-booking-status ${escapeHtml(status)}">
                            ${escapeHtml(statusLabel)}
                        </small>
                    </span>

                    <span>
                        <b>${money(booking.amount)}</b>

                        <small class="booking-status">
                            View details ▾
                        </small>
                    </span>
                </summary>

                <div class="booking-details">
                    ${bookingDetails(booking)}

                    ${status === 'cancelled' ? `
                        <p class="admin-cancel-notice">
                            This booking has been cancelled
                            by the administrator.
                            Your parking slot is no longer reserved.
                        </p>
                    ` : ''}
                </div>
            </details>
        `;
    }).join('')

        : 'No bookings yet. Reserve a slot to get started.';
}


// =========================================================
// 9. RECEIPT BUTTON EVENTS
// =========================================================

$('bookings').addEventListener('click', (event) => {
    const button = event.target.closest(
        '.receipt-download'
    );

    if (!button) return;

    const booking = state.bookings.find(
        item => item.id === button.dataset.id
    );

    if (booking) {
        downloadReceipt(booking);
    }
});

$('downloadLatest').addEventListener('click', () => {
    if (latestReceipt) {
        downloadReceipt(latestReceipt);
    }
});


// =========================================================
// 10. REFRESH PARKING AVAILABILITY
// =========================================================

async function refresh() {
    const version = ++refreshVersion;

    try {
        const params = new URLSearchParams({
            start_time: $('start').value,
            duration: $('duration').value,
            unit: $('unit').value
        });

        const response = await fetch(
            '/api/state?' + params.toString()
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || 'Could not load parking data'
            );
        }

        // Ignore outdated responses
        if (version !== refreshVersion) {
            return;
        }

        render(data);

    } catch (error) {
        if (version !== refreshVersion) {
            return;
        }

        message(
            'Unable to load parking data: ' + error.message,
            'error'
        );
    }
}


// =========================================================
// 11. IMAGE UPLOAD AND YOLO DETECTION
// =========================================================

$('file').addEventListener('change', () => {
    message(
        $('file').files[0]?.name || 'Choose an image.'
    );
});

$('analyze').addEventListener('click', async () => {
    const file = $('file').files[0];

    if (!file) {
        return message(
            'Choose a parking image first.',
            'error'
        );
    }

    const formData = new FormData();
    formData.append('image', file);

    $('analyze').disabled = true;

    message('Analyzing image with YOLO11…');

    try {
        const response = await fetch('/api/detect', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error);
        }

        await refresh();

        message(
            `Analysis complete: ${data.count} car detections. ` +
            'Select a green slot to book.',
            'success'
        );

    } catch (error) {
        message(error.message, 'error');

    } finally {
        $('analyze').disabled = false;
    }
});

// 12. SUBMIT PARKING BOOKING

$('bookingForm').addEventListener('submit', async (event) => {
    event.preventDefault();

    // Customer must be logged in
    if (!signedInUser) {
        location.href = '/login';
        return;
    }

    const slotId = Number($('slot').value);

    if (!slotId) {
        return message(
            'Select an available slot first.',
            'error',
            'bookingNotice'
        );
    }

    const bookingData = {
        slot_id: slotId,
        customer: $('customer').value,
        start_time: $('start').value,
        duration: Number($('duration').value),
        unit: $('unit').value
    };

    const submitButton = $('bookingForm').querySelector(
        'button[type=submit]'
    );

    submitButton.disabled = true;

    message(
        'Processing demo booking…',
        'info',
        'bookingNotice'
    );

    try {
        const response = await fetch('/api/book', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(bookingData)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error);
        }

        // Store latest receipt
        latestReceipt = {
            ...data,
            id: data.booking_id
        };

        $('receiptActions').hidden = false;

        message(
            `Booking confirmed! Slot ${data.slot_id} ` +
            `is now reserved. Booking ID: ${data.booking_id}. ` +
            `Demo payment: ${money(data.amount)}. ` +
            'No real money charged.',
            'success',
            'bookingNotice'
        );

        // Reset form before refreshing availability
        $('slot').value = '';
        $('start').value = nowLocal();

        updatePrice();

        await refresh();

        $('bookings').scrollIntoView({
            behavior: 'smooth',
            block: 'nearest'
        });

    } catch (error) {
        message(
            error.message,
            'error',
            'bookingNotice'
        );

    } finally {
        submitButton.disabled = false;
    }
});

async function initializeApp() {
    try {
        await loadAccount();

        await Promise.all([
            loadParkingRates(),
            refresh()
        ]);

    } catch (error) {
        message(
            'Initialization error: ' + error.message,
            'error'
        );
    }
}

initializeApp();

setInterval(async () => {
    await refresh();

    try {
        await loadParkingRates();

    } catch (error) {
        console.error(
            'Parking rate refresh failed:',
            error
        );
    }
}, 30000);
