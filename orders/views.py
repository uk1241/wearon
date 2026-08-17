import csv
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import connection
from django.db.utils import OperationalError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import (
    AttendanceSegmentFormSet,
    ExpenseFormSet,
    EmployeeAttendanceForm,
    EmployeeForm,
    OrderForm,
    OrderItemFormSet,
    PaymentFormSet,
    PayrollForm,
)
from .forms import FabricForm, CustomerForm
from .models import (
    Customer,
    Employee,
    EmployeeAttendance,
    Expense,
    Order,
    OrderItem,
    OrderProgress,
    Fabric,
    Payroll,
)
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum

ORDER_STATUS_TABS = [
    (Order.STATUS_IN_PROGRESS, "In Progress"),
    (Order.STATUS_FINISHED, "Completed"),
]

NEUTRAL_CHART_COLOR = "rgba(148, 168, 175, 0.45)"


def _filter_by_status(queryset, status):
    if status not in {Order.STATUS_IN_PROGRESS, Order.STATUS_FINISHED}:
        status = Order.STATUS_IN_PROGRESS
    if status == Order.STATUS_IN_PROGRESS:
        return queryset.filter(status__in=[Order.STATUS_IN_PROGRESS, Order.STATUS_PENDING])
    return queryset.filter(status=status)


def _months_back(first_of_month, months):
    """Return the first day of the month `months` before `first_of_month`, crossing year boundaries."""
    month_index = first_of_month.month - 1 - months
    year = first_of_month.year + month_index // 12
    month = month_index % 12 + 1
    return first_of_month.replace(year=year, month=month, day=1)


def _donut_chart(segments):
    """segments: list of (css_color, value, label). Returns (conic-gradient stops, legend rows)."""
    total = sum((Decimal(value) for _, value, _ in segments), Decimal("0"))
    if total <= 0:
        return f"{NEUTRAL_CHART_COLOR} 0deg 360deg", [
            {"label": label, "value": 0, "pct": Decimal("0"), "color": color} for color, _, label in segments
        ]
    stops = []
    legend = []
    cursor = Decimal("0")
    for color, value, label in segments:
        value = Decimal(value)
        pct = value / total * 100
        start_deg = cursor / 100 * 360
        cursor += pct
        end_deg = cursor / 100 * 360
        stops.append(f"{color} {start_deg:.2f}deg {end_deg:.2f}deg")
        legend.append({"label": label, "value": value, "pct": pct.quantize(Decimal("0.1")), "color": color})
    return ", ".join(stops), legend


@login_required
def dashboard(request):
    orders = Order.objects.select_related("customer").prefetch_related("items", "expenses")
    today = date.today()
    active_employee_count = Employee.objects.filter(status=Employee.EMPLOYEE_STATUS_ACTIVE).count()

    # Single pass over orders for revenue, expenses, status mix, payment mix, and per-customer revenue.
    total_revenue = Decimal("0")
    total_expenses = Decimal("0")
    revenue_today = Decimal("0")
    status_counts = defaultdict(int)
    payment_counts = defaultdict(int)
    customer_revenue = defaultdict(Decimal)
    customer_names = {}
    for order in orders:
        grand_total = order.grand_total
        total_revenue += grand_total
        total_expenses += order.total_expenses
        if order.order_date == today:
            revenue_today += grand_total
        status_counts[order.status] += 1
        payment_counts[order.payment_status_label] += 1
        customer_revenue[order.customer_id] += grand_total
        customer_names[order.customer_id] = order.customer.name
    total_revenue = total_revenue.quantize(Decimal("0.01"))
    total_expenses = total_expenses.quantize(Decimal("0.01"))
    revenue_today = revenue_today.quantize(Decimal("0.01"))

    expenses_today = sum(
        (e.total for e in Expense.objects.filter(created_at__date=today)), Decimal("0")
    ).quantize(Decimal("0.01"))
    payroll_this_month = sum(
        (p.net_pay for p in Payroll.objects.filter(pay_period_start__month=today.month, pay_period_start__year=today.year)),
        Decimal("0"),
    ).quantize(Decimal("0.01"))

    # Revenue vs expenses trend for the last 6 months.
    window_start = _months_back(today.replace(day=1), 5)
    monthly_revenue = defaultdict(Decimal)
    for order in Order.objects.filter(order_date__gte=window_start).prefetch_related("items"):
        key = (order.order_date.year, order.order_date.month)
        monthly_revenue[key] += order.grand_total
    monthly_expenses = defaultdict(Decimal)
    for expense in Expense.objects.filter(created_at__date__gte=window_start):
        expense_date = expense.created_at.date()
        key = (expense_date.year, expense_date.month)
        monthly_expenses[key] += expense.total

    trend_data = []
    for i in range(5, -1, -1):
        month_date = _months_back(today.replace(day=1), i)
        key = (month_date.year, month_date.month)
        trend_data.append(
            {
                "label": month_date.strftime("%b"),
                "revenue": monthly_revenue.get(key, Decimal("0")).quantize(Decimal("0.01")),
                "expenses": monthly_expenses.get(key, Decimal("0")).quantize(Decimal("0.01")),
            }
        )
    max_trend_value = max(
        (max(item["revenue"], item["expenses"]) for item in trend_data), default=Decimal("0")
    ) or Decimal("1")
    for item in trend_data:
        item["revenue_pct"] = int(item["revenue"] / max_trend_value * 100)
        item["expenses_pct"] = int(item["expenses"] / max_trend_value * 100)

    # Order status mix (mirrors the pill colors used elsewhere in the app).
    order_status_gradient, order_status_legend = _donut_chart(
        [
            ("var(--muted)", status_counts.get(Order.STATUS_PENDING, 0), "Pending"),
            ("var(--success)", status_counts.get(Order.STATUS_IN_PROGRESS, 0), "In Progress"),
            ("var(--primary)", status_counts.get(Order.STATUS_FINISHED, 0), "Finished"),
            ("var(--danger)", status_counts.get(Order.STATUS_CANCELLED, 0), "Cancelled"),
        ]
    )

    # Payment status mix.
    payment_status_gradient, payment_status_legend = _donut_chart(
        [
            ("var(--success)", payment_counts.get("Paid", 0), "Paid"),
            ("var(--warning)", payment_counts.get("Partial", 0), "Partial"),
            ("var(--danger)", payment_counts.get("Unpaid", 0), "Unpaid"),
        ]
    )

    # Employee attendance for today.
    attendance_today = EmployeeAttendance.objects.filter(date=today)
    present_count = attendance_today.filter(status=EmployeeAttendance.ATTENDANCE_PRESENT).count()
    half_day_count = attendance_today.filter(status=EmployeeAttendance.ATTENDANCE_HALF_DAY).count()
    absent_count = attendance_today.filter(status=EmployeeAttendance.ATTENDANCE_ABSENT).count()
    leave_count = attendance_today.filter(status=EmployeeAttendance.ATTENDANCE_LEAVE).count()
    marked_count = present_count + half_day_count + absent_count + leave_count
    not_marked_count = max(active_employee_count - marked_count, 0)
    today_present_count = present_count + half_day_count
    attendance_gradient, attendance_legend = _donut_chart(
        [
            ("var(--success)", present_count, "Present"),
            ("var(--warning)", half_day_count, "Half Day"),
            ("var(--danger)", absent_count, "Absent"),
            ("var(--primary-soft-strong)", leave_count, "On Leave"),
            (NEUTRAL_CHART_COLOR, not_marked_count, "Not Marked"),
        ]
    )

    # Top 5 customers by revenue.
    top_customers = sorted(customer_revenue.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_customers_data = [
        {"name": customer_names[customer_id], "revenue": revenue.quantize(Decimal("0.01"))}
        for customer_id, revenue in top_customers
    ]
    max_customer_revenue = max((row["revenue"] for row in top_customers_data), default=Decimal("0")) or Decimal("1")
    for row in top_customers_data:
        row["pct"] = int(row["revenue"] / max_customer_revenue * 100)

    # Expenses by category.
    expense_amount = ExpressionWrapper(
        F("quantity") * F("unit_cost"), output_field=DecimalField(max_digits=12, decimal_places=2)
    )
    category_totals = (
        Expense.objects.values("category").annotate(total=Sum(expense_amount)).order_by("-total")
    )
    expense_categories = []
    other_total = Decimal("0")
    for index, row in enumerate(category_totals):
        total = row["total"] or Decimal("0")
        if index < 5:
            expense_categories.append({"label": row["category"] or "Uncategorized", "total": total})
        else:
            other_total += total
    if other_total > 0:
        expense_categories.append({"label": "Other", "total": other_total})
    max_category_total = max((row["total"] for row in expense_categories), default=Decimal("0")) or Decimal("1")
    for row in expense_categories:
        row["pct"] = int(row["total"] / max_category_total * 100)

    context = {
        "total_orders": orders.count(),
        "in_progress_count": status_counts.get(Order.STATUS_IN_PROGRESS, 0) + status_counts.get(Order.STATUS_PENDING, 0),
        "finished_count": status_counts.get(Order.STATUS_FINISHED, 0),
        "revenue_today": revenue_today,
        "expenses_today": expenses_today,
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "net_profit": total_revenue - total_expenses,
        "active_employee_count": active_employee_count,
        "today_present_count": today_present_count,
        "payroll_this_month": payroll_this_month,
        "trend_data": trend_data,
        "order_status_gradient": order_status_gradient,
        "order_status_legend": order_status_legend,
        "payment_status_gradient": payment_status_gradient,
        "payment_status_legend": payment_status_legend,
        "attendance_gradient": attendance_gradient,
        "attendance_legend": attendance_legend,
        "attendance_marked_count": marked_count,
        "top_customers": top_customers_data,
        "expense_categories": expense_categories,
    }
    return render(request, "orders/dashboard.html", context)


@login_required
def order_list(request):
    orders = Order.objects.select_related("customer").prefetch_related("items")
    status = request.GET.get("status", Order.STATUS_IN_PROGRESS)
    context = {
        "orders": _filter_by_status(orders, status),
        "active_status": status,
        "status_tabs": ORDER_STATUS_TABS,
    }
    return render(request, "orders/order_list.html", context)


@login_required
def customer_list(request):
    customers = Customer.objects.order_by("name").prefetch_related("orders")
    return render(request, "orders/customer_list.html", {"customers": customers})


@login_required
def product_list(request):
    products = Fabric.objects.order_by("name").annotate(used_count=Count("order_items"))
    return render(request, "orders/product_list.html", {"products": products, "next_url": request.get_full_path()})


@login_required
def employee_list(request):
    employees = Employee.objects.order_by("name")
    return render(request, "orders/employee_list.html", {"employees": employees})


@login_required
def employee_create(request, pk=None):
    employee = get_object_or_404(Employee, pk=pk) if pk else None
    is_new = employee is None
    next_url = request.GET.get("next") or request.POST.get("next") or None
    if request.method == "POST":
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            employee = form.save()
            if next_url:
                return redirect(next_url)
            if is_new:
                attendance_url = reverse("employee-attendance-create") + f"?employee={employee.pk}"
                return redirect(attendance_url)
            return redirect("employee-detail", pk=employee.pk)
    else:
        form = EmployeeForm(instance=employee)
    return render(
        request,
        "orders/employee_form.html",
        {"form": form, "next": next_url, "is_new": is_new, "employee": employee},
    )


@login_required
def employee_detail(request, pk):
    employee = get_object_or_404(
        Employee.objects.prefetch_related("attendance_records", "payrolls"),
        pk=pk,
    )
    attendance_records = employee.attendance_records.order_by("-date")
    payroll_records = employee.payrolls.order_by("-pay_period_end")
    return render(
        request,
        "orders/employee_detail.html",
        {"employee": employee, "attendance_records": attendance_records, "payroll_records": payroll_records},
    )


@login_required
def employee_attendance_list(request):
    attendances = EmployeeAttendance.objects.select_related("employee").order_by("-date")
    return render(request, "orders/employee_attendance_list.html", {"attendances": attendances})


@login_required
def employee_attendance_create(request):
    employee_id = request.GET.get("employee") or request.POST.get("employee")
    if request.method == "POST":
        form = EmployeeAttendanceForm(request.POST)
        if form.is_valid():
            attendance = form.save()
            return redirect("employee-attendance-edit", pk=attendance.pk)
    else:
        initial = {"employee": employee_id} if employee_id else {}
        form = EmployeeAttendanceForm(initial=initial)
    return render(request, "orders/employee_attendance_form.html", {"form": form})


@login_required
def employee_attendance_edit(request, pk):
    attendance = get_object_or_404(EmployeeAttendance.objects.select_related("employee"), pk=pk)
    if request.method == "POST":
        form = EmployeeAttendanceForm(request.POST, instance=attendance)
        segment_formset = AttendanceSegmentFormSet(request.POST, instance=attendance, prefix="segments")
        if form.is_valid() and segment_formset.is_valid():
            attendance = form.save()
            segment_formset.instance = attendance
            segment_formset.save()
            EmployeeAttendance.objects.filter(pk=attendance.pk).update(
                work_hours=attendance.compute_total_hours()
            )
            return redirect("employee-detail", pk=attendance.employee.pk)
    else:
        form = EmployeeAttendanceForm(instance=attendance)
        segment_formset = AttendanceSegmentFormSet(instance=attendance, prefix="segments")
    return render(
        request,
        "orders/employee_attendance_form.html",
        {"form": form, "attendance": attendance, "editing": True, "segment_formset": segment_formset},
    )


@login_required
def payroll_list(request):
    payrolls = Payroll.objects.select_related("employee").order_by("-pay_period_end")
    return render(request, "orders/payroll_list.html", {"payrolls": payrolls})


@login_required
def payroll_create(request):
    employee_id = request.GET.get("employee") or request.POST.get("employee")
    if request.method == "POST":
        form = PayrollForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("payroll-list")
    else:
        initial = {"employee": employee_id} if employee_id else {}
        form = PayrollForm(initial=initial)
    return render(request, "orders/payroll_form.html", {"form": form})


@login_required
def payroll_edit(request, pk):
    payroll = get_object_or_404(Payroll.objects.select_related("employee"), pk=pk)
    if request.method == "POST":
        form = PayrollForm(request.POST, instance=payroll)
        if form.is_valid():
            payroll = form.save()
            return redirect("employee-detail", pk=payroll.employee.pk)
    else:
        form = PayrollForm(instance=payroll)
    return render(request, "orders/payroll_form.html", {"form": form, "payroll": payroll, "editing": True})


@login_required
def payroll_attendance_summary(request):
    """Return attendance counts, hours, and daily rows for an employee over a date range."""
    employee_id = request.GET.get("employee")
    start = request.GET.get("start")
    end = request.GET.get("end")
    if not (employee_id and start and end):
        return JsonResponse({"error": "missing params"}, status=400)
    try:
        employee = Employee.objects.get(pk=employee_id)
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
        end_date = datetime.strptime(end, "%Y-%m-%d").date()
    except (Employee.DoesNotExist, ValueError):
        return JsonResponse({"error": "invalid params"}, status=400)
    if end_date < start_date:
        return JsonResponse({"error": "invalid range"}, status=400)

    records = EmployeeAttendance.objects.filter(
        employee=employee, date__gte=start_date, date__lte=end_date
    ).order_by("date")

    present_days = 0
    half_days = 0
    absent_days = 0
    leave_days = 0
    total_hours = Decimal("0.00")
    rows = []
    for record in records:
        if record.status == EmployeeAttendance.ATTENDANCE_PRESENT:
            present_days += 1
        elif record.status == EmployeeAttendance.ATTENDANCE_HALF_DAY:
            half_days += 1
        elif record.status == EmployeeAttendance.ATTENDANCE_ABSENT:
            absent_days += 1
        elif record.status == EmployeeAttendance.ATTENDANCE_LEAVE:
            leave_days += 1
        total_hours += record.work_hours
        rows.append(
            {
                "date": record.date.strftime("%Y-%m-%d"),
                "status": record.get_status_display(),
                "check_in": record.check_in.strftime("%H:%M") if record.check_in else None,
                "check_out": record.check_out.strftime("%H:%M") if record.check_out else None,
                "hours": str(record.work_hours),
            }
        )

    return JsonResponse(
        {
            "present_days": present_days + half_days,
            "half_days": half_days,
            "absent_days": absent_days,
            "leave_days": leave_days,
            "working_days": (end_date - start_date).days + 1,
            "total_hours": str(total_hours.quantize(Decimal("0.01"))),
            "records": rows,
        }
    )


@login_required
def order_form_view(request, pk=None):
    order = get_object_or_404(Order, pk=pk) if pk else None
    is_new = order is None

    customers = Customer.objects.order_by("name")
    item_names = (
        OrderItem.objects.order_by("item_name")
        .values_list("item_name", flat=True)
        .distinct()
    )

    products = Fabric.objects.order_by("name")
    # prepare simple customers data for client-side auto-fill
    customers_data = list(
        Customer.objects.order_by("name").values("name", "phone", "email", "address")
    )

    if request.method == "POST":
        form = OrderForm(request.POST, instance=order)
        formset = OrderItemFormSet(request.POST, instance=order, prefix="items")
        payment_formset = PaymentFormSet(request.POST, instance=order, prefix="payments")
        if form.is_valid() and formset.is_valid() and payment_formset.is_valid():
            # prepare order instance but don't save yet; compute collected amount from payments
            order = form.save(commit=False)
            # compute total from validated payment formset cleaned data (skip deleted forms)
            total_paid = Decimal("0")
            for pform in payment_formset.cleaned_data:
                if pform and not pform.get("DELETE", False):
                    amt = pform.get("amount") or Decimal("0")
                    try:
                        total_paid += Decimal(str(amt))
                    except Exception:
                        total_paid += Decimal("0")
            # set aggregated amount on order before saving so it's persisted on first save
            order.amount_paid = total_paid.quantize(Decimal("0.01"))
            order.save()
            # save items and payments referencing the saved order
            formset.instance = order
            formset.save()
            payment_formset.instance = order
            payment_formset.save()
            if is_new:
                OrderProgress.objects.create(order=order, title="Order Created")
            return redirect("order-detail", pk=order.pk)
    else:
        form = OrderForm(instance=order)
        formset = OrderItemFormSet(instance=order, prefix="items")
        payment_formset = PaymentFormSet(instance=order, prefix="payments")

    return render(
        request,
        "orders/order_form.html",
        {
            "form": form,
            "formset": formset,
            "payment_formset": payment_formset,
            "order": order,
            "is_new": is_new,
            "customers": customers,
            "item_names": item_names,
            "products": products,
            "next_url": request.get_full_path(),
            "customers_data": customers_data,
        },
    )


@login_required
def customer_create(request):
    next_url = request.GET.get("next") or request.POST.get("next") or None
    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            if next_url:
                return redirect(next_url)
            return redirect("customer-list")
    else:
        form = CustomerForm()
    return render(request, "orders/customer_form.html", {"form": form, "next": next_url})


@login_required
def product_create(request):
    next_url = request.GET.get("next") or request.POST.get("next") or None
    if request.method == "POST":
        form = FabricForm(request.POST)
        if form.is_valid():
            form.save()
            if next_url:
                return redirect(next_url)
            return redirect("product-list")
    else:
        form = FabricForm()
    return render(request, "orders/product_form.html", {"form": form, "next": next_url})


@login_required
def product_price(request):
    """Return JSON price for a product name lookup.

    Accepts GET param `name` and returns {"price": "0.00"} or 404 when not found.
    """
    name = request.GET.get("name")
    if not name:
        return JsonResponse({"error": "missing name"}, status=400)
    try:
        fabric = Fabric.objects.get(name=name)
    except Fabric.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)
    # return as string to avoid Decimal -> JSON issues
    return JsonResponse({"price": str(fabric.price_per_unit)})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related("customer").prefetch_related("items", "progress_steps"),
        pk=pk,
    )
    return render(request, "orders/order_detail.html", {"order": order})


@login_required
@require_POST
def order_mark_finished(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if order.status != Order.STATUS_FINISHED:
        order.status = Order.STATUS_FINISHED
        order.save()
        OrderProgress.objects.create(order=order, title="Order Finished")
    return redirect("order-detail", pk=order.pk)


@login_required
@require_POST
def order_mark_unfinished(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if order.status == Order.STATUS_FINISHED:
        order.status = Order.STATUS_IN_PROGRESS
        order.save()
        OrderProgress.objects.create(order=order, title="Order Reopened")
    return redirect("order-detail", pk=order.pk)


@login_required
@require_POST
def order_mark_paid(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if not order.is_paid:
        # mark fully paid: set amount_paid to grand_total and mark is_paid
        try:
            order.amount_paid = order.grand_total
        except Exception:
            order.amount_paid = Decimal("0")
        order.is_paid = True
        order.save()
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url:
        return redirect(next_url)
    return redirect("order-detail", pk=order.pk)


@login_required
@require_POST
def order_mark_unpaid(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if order.is_paid:
        # mark unpaid: clear is_paid and reset amount_paid to 0.00
        order.is_paid = False
        try:
            order.amount_paid = Decimal("0.00")
        except Exception:
            order.amount_paid = Decimal("0")
        order.save()
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url:
        return redirect(next_url)
    return redirect("order-detail", pk=order.pk)


@login_required
@require_POST
def order_delete(request, pk):
    order = get_object_or_404(Order, pk=pk)
    order.delete()
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url:
        return redirect(next_url)
    return redirect("order-list")


@login_required
def order_invoice(request, pk):
    order = get_object_or_404(
        Order.objects.select_related("customer").prefetch_related("items"), pk=pk
    )
    return render(request, "orders/invoice.html", {"order": order})


@login_required
def expense_management(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == "POST":
        formset = ExpenseFormSet(request.POST, instance=order, prefix="expenses")
        if formset.is_valid():
            formset.save()
            return redirect("order-expenses", pk=order.pk)
    else:
        formset = ExpenseFormSet(instance=order, prefix="expenses")
    return render(request, "orders/expense_management.html", {"order": order, "formset": formset})


@login_required
def expense_export(request, pk):
    order = get_object_or_404(Order, pk=pk)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{order.order_number}-expenses.csv"'
    writer = csv.writer(response)
    writer.writerow(["Expense Name", "Category", "Quantity", "Unit Cost", "Total"])
    for expense in order.expenses.all():
        writer.writerow(
            [expense.name, expense.category, expense.quantity, expense.unit_cost, expense.total]
        )
    return response


@login_required
def expense_list(request):
    orders = (
        Order.objects.select_related("customer")
        .prefetch_related("expenses")
        .order_by("-created_at")
    )
    return render(request, "orders/expense_list.html", {"orders": orders})


@login_required
def reports(request):
    orders = list(Order.objects.prefetch_related("items", "expenses"))
    total_revenue = sum((o.grand_total for o in orders), Decimal("0"))
    total_expenses = sum((o.total_expenses for o in orders), Decimal("0"))
    net_profit = total_revenue - total_expenses
    order_count = len(orders)
    avg_order_value = (total_revenue / order_count) if order_count else Decimal("0")

    status_breakdown = []
    for code, label in Order.STATUS_CHOICES:
        count = sum(1 for o in orders if o.status == code)
        pct = (count / order_count * 100) if order_count else 0
        status_breakdown.append({"label": label, "count": count, "pct": pct})

    customers = Customer.objects.prefetch_related("orders", "orders__items")
    customer_rows = []
    for customer in customers:
        revenue = sum((o.grand_total for o in customer.orders.all()), Decimal("0"))
        if revenue:
            customer_rows.append({"customer": customer, "revenue": revenue})
    customer_rows.sort(key=lambda row: row["revenue"], reverse=True)
    top_customers = customer_rows[:5]
    max_revenue = top_customers[0]["revenue"] if top_customers else Decimal("0")
    for row in top_customers:
        row["pct"] = (row["revenue"] / max_revenue * 100) if max_revenue else 0

    context = {
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "order_count": order_count,
        "avg_order_value": avg_order_value,
        "status_breakdown": status_breakdown,
        "top_customers": top_customers,
    }
    return render(request, "orders/reports.html", context)


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(
        Customer.objects.prefetch_related("orders__items", "orders__expenses"),
        pk=pk,
    )
    # Calculate paid and unpaid totals for the customer.
    # unpaid_total is the sum of outstanding due amounts across orders where:
    # - order.amount_due > 0 AND order.status == finished AND not order.is_paid
    orders = list(customer.orders.all())
    paid_total = sum((o.amount_paid for o in orders), Decimal("0"))
    unpaid_total = sum(
        (o.amount_due for o in orders if o.amount_due > Decimal("0") and o.status == Order.STATUS_FINISHED and not o.is_paid),
        Decimal("0"),
    )

    return render(
        request,
        "orders/customer_detail.html",
        {
            "customer": customer,
            "paid_total": paid_total,
            "unpaid_total": unpaid_total,
        },
    )


@login_required
def customer_due_invoice(request, pk):
    customer = get_object_or_404(
        Customer.objects.prefetch_related("orders__items", "orders__expenses"),
        pk=pk,
    )
    # select orders that are finished, marked unpaid, and have outstanding due
    orders = list(customer.orders.order_by("-created_at").all())
    due_orders = [o for o in orders if o.amount_due > Decimal("0") and o.status == Order.STATUS_FINISHED and not o.is_paid]
    total_due = sum((o.amount_due for o in due_orders), Decimal("0"))
    return render(
        request,
        "orders/customer_due_invoice.html",
        {
            "customer": customer,
            "due_orders": due_orders,
            "total_due": total_due,
        },
    )


@login_required
def customer_export(request, pk):
    customer = get_object_or_404(
        Customer.objects.prefetch_related("orders__items", "orders__expenses"),
        pk=pk,
    )
    orders = customer.orders.order_by("-created_at").all()
    total_revenue = sum((order.grand_total for order in orders), Decimal("0"))
    total_expenses = sum((order.total_expenses for order in orders), Decimal("0"))
    net_profit = total_revenue - total_expenses
    paid_total = sum((order.grand_total for order in orders if order.status == Order.STATUS_FINISHED), Decimal("0"))
    unpaid_total = sum((order.grand_total for order in orders if order.status != Order.STATUS_FINISHED), Decimal("0"))
    return render(
        request,
        "orders/customer_export.html",
        {
            "customer": customer,
            "orders": orders,
            "total_revenue": total_revenue,
            "total_expenses": total_expenses,
            "net_profit": net_profit,
            "paid_total": paid_total,
            "unpaid_total": unpaid_total,
        },
    )


@login_required
def settings_page(request):
    return render(request, "orders/settings.html", {"page_title": "Settings"})


@login_required
def support_page(request):
    return render(request, "orders/placeholder.html", {"page_title": "Support"})



@login_required
def health_check(request):
    db_settings = connection.settings_dict
    db_status = "healthy"
    error_message = ""

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except OperationalError as exc:
        db_status = "unhealthy"
        error_message = str(exc)

    context = {
        "page_title": "System Health",
        "db_name": db_settings.get("NAME"),
        "db_host": db_settings.get("HOST") or "localhost",
        "db_engine": db_settings.get("ENGINE", "").rsplit(".", 1)[-1],
        "db_status": db_status,
        "error_message": error_message,
    }
    return render(request, "orders/health.html", context)

