
const $ = (id) => document.getElementById(id);

const money = (amount) =>
    '₹' + Number(amount).toFixed(2);

async function loadAdmin() {
    try {
        const response = await fetch('/api/auth/me');
        const data = await response.json();

        if (!response.ok || !data.user ||
            data.user.role !== 'admin') {
            window.location.href = '/login';
            return;
        }

        $('adminName').textContent =
            data.user.full_name || 'Administrator';

    } catch (error) {
        console.error('Admin authentication error:', error);
    }
}

async function loadStats() {
    const button = $('refreshBtn');
    button.disabled = true;

    try {
        const response = await fetch('/api/admin/stats');
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to load statistics');
        }

        $('totalSlots').textContent = data.total_slots;
        $('occupiedSlots').textContent = data.occupied_slots;
        $('totalBookings').textContent = data.total_bookings;
        $('totalCustomers').textContent = data.total_customers;
        $('totalRevenue').textContent = money(data.total_revenue);

        const total = Number(data.total_slots);
        const occupied = Number(data.occupied_slots);

        const percentage = total > 0
            ? (occupied / total) * 100
            : 0;

        $('occupancyPercent').textContent =
            percentage.toFixed(1) + '%';

        $('occupancyBar').style.width =
            Math.min(100, percentage) + '%';

        $('occupiedSummary').textContent =
            occupied + ' occupied';

        $('availableSummary').textContent =
            Math.max(0, total - occupied) + ' not occupied';

        $('lastUpdated').textContent =
            'Last updated: ' + new Date().toLocaleTimeString();

    } catch (error) {
        $('lastUpdated').textContent =
            'Error: ' + error.message;
    } finally {
        button.disabled = false;
    }
}

$('refreshBtn').addEventListener('click', loadStats);

$('logoutBtn').addEventListener('click', async () => {
    try {
        const response = await fetch('/api/auth/logout', {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error('Logout failed');
        }

        window.location.href = '/login';

    } catch (error) {
        alert(error.message);
    }
});

loadAdmin();
loadStats();

setInterval(loadStats, 30000);

let adminBookings = [];

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[c]));
}

function formatDate(value) {
    return value ? value.replace('T', ' ').slice(0, 16) : '-';
}

function renderBookings() {
    const filter = $('bookingFilter').value;

    const bookings = adminBookings.filter(b =>
        filter === 'all' || b.status === filter
    );

    if (!bookings.length) {
        $('bookingRows').innerHTML =
            '<tr><td colspan="8">No bookings found.</td></tr>';
        return;
    }

    $('bookingRows').innerHTML = bookings.map(b => {
        const active = ['confirmed', 'pending'].includes(b.status);

        return `
            <tr>
                <td>${escapeHtml(b.booking_id)}</td>
                <td>${escapeHtml(b.customer)}</td>
                <td>Slot ${escapeHtml(b.slot_id)}</td>
                <td>${escapeHtml(formatDate(b.start_time))}</td>
                <td>${escapeHtml(formatDate(b.end_time))}</td>
                <td>${money(b.amount)}</td>
                <td>
                    <span class="booking-status ${escapeHtml(b.status)}">
                        ${escapeHtml(b.status)}
                    </span>
                </td>
                <td>
                    ${active
                        ? `<button class="cancel-booking"
                                   data-id="${escapeHtml(b.booking_id)}">
                               Cancel
                           </button>`
                        : '-'}
                </td>
            </tr>
        `;
    }).join('');
}

async function loadBookings() {
    try {
        const response = await fetch('/api/admin/bookings');
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to load bookings');
        }

        adminBookings = data.bookings;
        renderBookings();

    } catch (error) {
        $('bookingRows').textContent =
            'Error: ' + error.message;
    }
}

$('bookingFilter').addEventListener('change', renderBookings);

$('refreshBookings').addEventListener('click', loadBookings);

$('bookingRows').addEventListener('click', async (event) => {
    const button = event.target.closest('.cancel-booking');

    if (!button) return;

    const bookingId = button.dataset.id;

    if (!confirm(`Cancel booking ${bookingId}?`)) return;

    button.disabled = true;

    try {
        const response = await fetch(
            `/api/admin/bookings/${encodeURIComponent(bookingId)}/cancel`,
            { method: 'POST' }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Cancellation failed');
        }

        await Promise.all([loadBookings(), loadStats()]);

    } catch (error) {
        alert(error.message);
        button.disabled = false;
    }
});

loadBookings();

const adminPages = {
    dashboard: 'dashboardPage',
    bookings: 'bookingsPage',
    slots: 'slotsPage',
    customers: 'customersPage',
    reports: 'reportsPage'
};

const pageTitles = {
    dashboard: 'Dashboard Overview',
    bookings: 'Booking Management',
    slots: 'Parking Slot Management',
    customers: 'Customer Management',
    reports: 'Reports'
};

function showAdminPage(page) {
    if (!adminPages[page]) {
        page = 'dashboard';
    }

    // Hide every page except the selected one
    Object.entries(adminPages).forEach(([key, id]) => {
        document.getElementById(id).hidden = key !== page;
    });

    // Highlight selected sidebar link
    document.querySelectorAll('.sidebar-nav .nav-link')
        .forEach(link => {
            link.classList.toggle(
                'active',
                link.dataset.page === page
            );
        });

    // Change main heading
    document.querySelector('.topbar h1').textContent =
        pageTitles[page];

    // Load data when opening the relevant page
    if (page === 'dashboard') {
        loadStats();
    } else if (page === 'bookings') {
        loadBookings();
    }
    else if (page === 'slots') {
        loadAdminSlots();
    }
    else if (page === 'customers') {
        loadCustomers();
    }
    else if (page === 'reports') {
        loadReports();
    }
}

// Handle sidebar clicks
document.querySelectorAll('.sidebar-nav .nav-link')
    .forEach(link => {
        link.addEventListener('click', (event) => {
            event.preventDefault();

            const page = link.dataset.page;

            history.pushState(null, '', '#' + page);
            showAdminPage(page);
        });
    });

// Handle browser back/forward navigation
window.addEventListener('popstate', () => {
    showAdminPage(location.hash.slice(1) || 'dashboard');
});

// Open the correct page on refresh
showAdminPage(location.hash.slice(1) || 'dashboard');

async function loadAdminSlots() {
    const rows = $('adminSlotRows');

    try {
        const response = await fetch('/api/admin/slots');
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to load slots');
        }

        rows.innerHTML = data.slots.map(slot => `
            <tr>
                <td><strong>Slot ${slot.slot_id}</strong></td>
                <td>${escapeHtml(slot.status)}</td>
                <td>
                    <input
                        type="number"
                        class="slot-rate-input"
                        data-slot="${slot.slot_id}"
                        value="${slot.hourly_rate.toFixed(2)}"
                        min="0.01"
                        max="10000"
                        step="0.01"
                    >
                </td>
                <td>
                    <button
                        class="refresh-btn save-slot-rate"
                        data-slot="${slot.slot_id}"
                        type="button">
                        Save Price
                    </button>
                </td>
            </tr>
        `).join('');

        $('slotNotice').textContent = '';

    } catch (error) {
        rows.textContent = 'Error: ' + error.message;
    }
}

$('refreshSlots').addEventListener('click', loadAdminSlots);

$('adminSlotRows').addEventListener('click', async (event) => {
    const button = event.target.closest('.save-slot-rate');

    if (!button) return;

    const slotId = button.dataset.slot;
    const input = $('adminSlotRows').querySelector(
        `.slot-rate-input[data-slot="${slotId}"]`
    );

    const rate = Number(input.value);

    if (!input.value.trim() ||
        !Number.isFinite(rate) ||
        rate <= 0 ||
        rate > 10000 ||
        !/^\d+(\.\d{1,2})?$/.test(input.value)) {
        $('slotNotice').textContent =
            'Enter a valid price between ₹0.01 and ₹10,000.';
        return;
    }

    button.disabled = true;

    try {
        const response = await fetch(
            `/api/admin/slots/${slotId}/rate`,
            {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    hourly_rate: rate
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to update price');
        }

        $('slotNotice').textContent =
            `Slot ${slotId} price updated to ₹${rate.toFixed(2)}/hour.`;

    } catch (error) {
        $('slotNotice').textContent = error.message;

    } finally {
        button.disabled = false;
    }
});

// =====================================================
// CUSTOMER MANAGEMENT
// =====================================================

let adminCustomers = [];

async function loadCustomers() {
    const rows = document.getElementById('customerRows');

    try {
        const response = await fetch('/api/admin/customers');
        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || 'Unable to load customers'
            );
        }

        adminCustomers = data.customers;

        renderCustomers();

    } catch (error) {
        rows.innerHTML = `
            <tr>
                <td colspan="9">
                    ${escapeHtml(error.message)}
                </td>
            </tr>
        `;
    }
}

function renderCustomers() {
    const search = document.getElementById(
        'customerSearch'
    ).value.toLowerCase().trim();

    const filtered = adminCustomers.filter(customer => {
        return (
            customer.full_name.toLowerCase().includes(search) ||
            customer.email.toLowerCase().includes(search)
        );
    });

    const rows = document.getElementById('customerRows');

    if (!filtered.length) {
        rows.innerHTML = `
            <tr>
                <td colspan="9">No customers found.</td>
            </tr>
        `;
        return;
    }

    rows.innerHTML = filtered.map(customer => `
        <tr>
            <td>${customer.user_id}</td>

            <td>
                <strong>
                    ${escapeHtml(customer.full_name)}
                </strong>
            </td>

            <td>${escapeHtml(customer.email)}</td>

            <td>${escapeHtml(customer.phone || '-')}</td>

            <td>
                ${customer.email_verified ? 'Yes' : 'No'}
            </td>

            <td>${customer.total_bookings}</td>

            <td>
                ${customer.created_at
                    ? escapeHtml(formatDate(customer.created_at))
                    : '-'}
            </td>

            <td>
                <span class="booking-status">
                    ${customer.is_active ? 'Active' : 'Inactive'}
                </span>
            </td>

            <td>
                <div class="customer-actions">

                    <button
                        type="button"
                        class="refresh-btn customer-history-btn"
                        data-id="${customer.user_id}">
                        Bookings
                    </button>

                    <button
                        type="button"
                        class="refresh-btn customer-status-btn"
                        data-id="${customer.user_id}">
                        ${customer.is_active
                            ? 'Deactivate'
                            : 'Activate'}
                    </button>

                </div>
            </td>
        </tr>
    `).join('');
}


// =====================================================
// CUSTOMER ACTION BUTTONS
// =====================================================

document.getElementById('customerRows')
    .addEventListener('click', async (event) => {

        const statusButton = event.target.closest(
            '.customer-status-btn'
        );

        const historyButton = event.target.closest(
            '.customer-history-btn'
        );

        if (statusButton) {
            const userId = Number(statusButton.dataset.id);

            const customer = adminCustomers.find(
                item => item.user_id === userId
            );

            if (!customer) return;

            const newStatus = !customer.is_active;

            const confirmed = confirm(
                `${newStatus ? 'Activate' : 'Deactivate'} ` +
                `${customer.full_name}?`
            );

            if (!confirmed) return;

            statusButton.disabled = true;

            try {
                const response = await fetch(
                    `/api/admin/customers/${userId}/status`,
                    {
                        method: 'PATCH',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            is_active: newStatus
                        })
                    }
                );

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error);
                }

                document.getElementById(
                    'customerNotice'
                ).textContent = data.message;

                await loadCustomers();

            } catch (error) {
                document.getElementById(
                    'customerNotice'
                ).textContent = error.message;

                statusButton.disabled = false;
            }
        }

        if (historyButton) {
            const userId = Number(historyButton.dataset.id);

            const customer = adminCustomers.find(
                item => item.user_id === userId
            );

            if (customer) {
                await loadCustomerHistory(customer);
            }
        }
    });


// =====================================================
// CUSTOMER BOOKING HISTORY
// =====================================================

async function loadCustomerHistory(customer) {
    const panel = document.getElementById(
        'customerHistoryPanel'
    );

    const rows = document.getElementById(
        'customerHistoryRows'
    );

    panel.hidden = false;

    document.getElementById(
        'customerHistoryTitle'
    ).textContent =
        `Booking History — ${customer.full_name}`;

    rows.innerHTML = `
        <tr>
            <td colspan="6">Loading bookings...</td>
        </tr>
    `;

    try {
        const response = await fetch(
            `/api/admin/customers/${customer.user_id}/bookings`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error);
        }

        if (!data.bookings.length) {
            rows.innerHTML = `
                <tr>
                    <td colspan="6">
                        This customer has no bookings.
                    </td>
                </tr>
            `;

            return;
        }

        rows.innerHTML = data.bookings.map(booking => `
            <tr>
                <td>${escapeHtml(booking.booking_id)}</td>
                <td>Slot ${booking.slot_id}</td>
                <td>${escapeHtml(formatDate(booking.start_time))}</td>
                <td>${escapeHtml(formatDate(booking.end_time))}</td>
                <td>₹${Number(booking.amount).toFixed(2)}</td>
                <td>${escapeHtml(booking.status)}</td>
            </tr>
        `).join('');

    } catch (error) {
        rows.innerHTML = `
            <tr>
                <td colspan="6">
                    ${escapeHtml(error.message)}
                </td>
            </tr>
        `;
    }
}


// =====================================================
// CUSTOMER SEARCH AND REFRESH
// =====================================================

document.getElementById('customerSearch')
    .addEventListener('input', renderCustomers);

document.getElementById('refreshCustomers')
    .addEventListener('click', loadCustomers);

document.getElementById('closeCustomerHistory')
    .addEventListener('click', () => {
        document.getElementById(
            'customerHistoryPanel'
        ).hidden = true;
    });

// =====================================================
// REPORTS AND ANALYTICS
// =====================================================

let currentReport = null;

function localDateString(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');

    return `${year}-${month}-${day}`;
}

function initializeReportDates() {
    const today = new Date();
    const start = new Date(today);

    start.setDate(today.getDate() - 29);

    document.getElementById('reportStart').value =
        localDateString(start);

    document.getElementById('reportEnd').value =
        localDateString(today);
}

async function loadReports() {
    const start = document.getElementById('reportStart').value;
    const end = document.getElementById('reportEnd').value;
    const notice = document.getElementById('reportNotice');

    if (!start || !end || start > end) {
        notice.textContent = 'Select a valid date range.';
        return;
    }

    notice.textContent = 'Loading reports...';

    try {
        const params = new URLSearchParams({
            start: start,
            end: end
        });

        const response = await fetch(
            '/api/admin/reports?' + params.toString()
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || 'Unable to load reports'
            );
        }

        currentReport = data;

        renderReportSummary(data.summary);
        renderDailyChart(data.daily);
        renderSlotReport(data.slots);
        renderDetailedBookings(data.bookings || []);

        notice.textContent =
            `Report loaded: ${data.start} to ${data.end}`;

    } catch (error) {
        currentReport = null;
        notice.textContent = error.message;
    }
}


// =====================================================
// SUMMARY CARDS
// =====================================================

function renderReportSummary(summary) {
    document.getElementById('reportTotal').textContent =
        summary.total_bookings;

    document.getElementById('reportConfirmed').textContent =
        summary.confirmed;

    document.getElementById('reportCancelled').textContent =
        summary.cancelled;

    document.getElementById('reportValue').textContent =
        '₹' + Number(summary.booking_value).toFixed(2);
}


// =====================================================
// DAILY BOOKING CHART
// =====================================================

function renderDailyChart(daily) {
    const chart = document.getElementById('dailyChart');

    if (!daily.length) {
        chart.innerHTML =
            '<p>No bookings in the selected date range.</p>';
        return;
    }

    const maximum = Math.max(
        ...daily.map(item => Number(item.bookings)),
        1
    );

    chart.innerHTML = daily.map(item => {
        const percentage =
            (Number(item.bookings) / maximum) * 100;

        return `
            <div class="daily-chart-row">
                <span class="daily-chart-date">
                    ${escapeHtml(item.date)}
                </span>

                <div class="daily-chart-track">
                    <div
                        class="daily-chart-bar"
                        style="width: ${percentage}%">
                    </div>
                </div>

                <strong>${Number(item.bookings)}</strong>
            </div>
        `;
    }).join('');
}


// =====================================================
// SLOT-WISE PERFORMANCE TABLE
// =====================================================

function renderSlotReport(slots) {
    const rows = document.getElementById('reportSlotRows');

    if (!slots.length) {
        rows.innerHTML = `
            <tr>
                <td colspan="3">No parking slots found.</td>
            </tr>
        `;
        return;
    }

    rows.innerHTML = slots.map(slot => `
        <tr>
            <td>
                <strong>Slot ${Number(slot.slot_id)}</strong>
            </td>

            <td>${Number(slot.total_bookings)}</td>

            <td>
                ₹${Number(slot.booking_value).toFixed(2)}
            </td>
        </tr>
    `).join('');
}


// =====================================================
// CSV EXPORT
// =====================================================

function csvCell(value) {
    const text = String(value ?? '');

    // Escape spreadsheet formulas and CSV special characters.
    const safe = /^[\s]*[=+\-@\t\r]/.test(text)
        ? "'" + text
        : text;

    return '"' + safe.replace(/"/g, '""') + '"';
}

function exportReportCSV() {
    if (!currentReport) {
        document.getElementById('reportNotice').textContent =
            'Load a report before downloading.';
        return;
    }

    const report = currentReport;

    const rows = [
        ['ParkVision Reports'],
        ['Start Date', report.start],
        ['End Date', report.end],
        [],
        ['SUMMARY'],
        ['Metric', 'Value'],
        ['Total Bookings', report.summary.total_bookings],
        ['Confirmed', report.summary.confirmed],
        ['Cancelled', report.summary.cancelled],
        ['Pending', report.summary.pending],
        ['Demo Booking Value', report.summary.booking_value],
        [],
        ['DAILY BOOKINGS'],
        ['Date', 'Bookings', 'Booking Value']
    ];

    report.daily.forEach(item => {
        rows.push([
            item.date,
            item.bookings,
            item.booking_value
        ]);
    });

    rows.push([]);
    rows.push(['SLOT-WISE PERFORMANCE']);
    rows.push(['Slot ID', 'Total Bookings', 'Booking Value']);

    report.slots.forEach(slot => {
        rows.push([
            slot.slot_id,
            slot.total_bookings,
            slot.booking_value
        ]);
    });

    const csv = rows
        .map(row => row.map(csvCell).join(','))
        .join('\r\n');

    const blob = new Blob(
        ['\uFEFF' + csv],
        { type: 'text/csv;charset=utf-8;' }
    );

    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    link.href = url;
    link.download =
        `ParkVision_Report_${report.start}_to_${report.end}.csv`;

    document.body.appendChild(link);
    link.click();
    link.remove();

    URL.revokeObjectURL(url);
}


// =====================================================
// REPORT EVENTS
// =====================================================

initializeReportDates();

document.getElementById('applyReport')
    .addEventListener('click', loadReports);

document.getElementById('exportReport')
    .addEventListener('click', exportReportCSV);

// =====================================================
// DETAILED BOOKING REPORT
// =====================================================

function renderDetailedBookings(bookings) {
    const tbody = document.getElementById('reportBookingRows');

    if (!bookings.length) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9">
                    No bookings found for the selected parking dates.
                </td>
            </tr>
        `;
        return;
    }

    function formatDateTime(value) {
        const date = new Date(value);

        if (isNaN(date.getTime())) {
            return '-';
        }

        return date.toLocaleString('en-IN', {
            day: '2-digit',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: true
        });
    }

    function durationText(start, end) {
        const startDate = new Date(start);
        const endDate = new Date(end);

        const minutes = Math.round(
            (endDate - startDate) / 60000
        );

        if (!Number.isFinite(minutes) || minutes < 0) {
            return '-';
        }

        const hours = Math.floor(minutes / 60);
        const remainingMinutes = minutes % 60;

        return `${hours}h ${remainingMinutes}m`;
    }

    tbody.innerHTML = bookings.map(booking => {
        const status = String(booking.status || 'unknown');

        return `
            <tr>
                <td>#${escapeHtml(booking.booking_id)}</td>

                <td>${escapeHtml(booking.customer)}</td>

                <td>Slot ${escapeHtml(booking.slot_id)}</td>

                <td>
                    ${formatDateTime(booking.created_at)}
                </td>

                <td>
                    ${formatDateTime(booking.start_time)}
                </td>

                <td>
                    ${formatDateTime(booking.end_time)}
                </td>

                <td>
                    ${durationText(
                        booking.start_time,
                        booking.end_time
                    )}
                </td>

                <td>
                    ₹${Number(booking.total_price).toFixed(2)}
                </td>

                <td>
                    <span class="customer-booking-status ${escapeHtml(status)}">
                        ${escapeHtml(status)}
                    </span>
                </td>
            </tr>
        `;
    }).join('');
}
