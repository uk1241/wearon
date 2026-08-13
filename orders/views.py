import csv
from collections import defaultdict
from datetime import date
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
from django.db.models import Count

ORDER_STATUS_TABS = [
    (Order.STATUS_IN_PROGRESS, "In Progress"),
    (Order.STATUS_FINISHED, "Completed"),
]


def _filter_by_status(queryset, status):
    if status not in {Order.STATUS_IN_PROGRESS, Order.STATUS_FINISHED}:
        status = Order.STATUS_IN_PROGRESS
    if status == Order.STATUS_IN_PROGRESS:
        return queryset.filter(status__in=[Order.STATUS_IN_PROGRESS, Order.STATUS_PENDING])
    return queryset.filter(status=status)


@login_required
def dashboard(request):
    orders = Order.objects.select_related("customer").prefetch_related("items", "expenses")
    today = date.today()
    active_employee_count = Employee.objects.filter(status=Employee.EMPLOYEE_STATUS_ACTIVE).count()
    today_present_count = EmployeeAttendance.objects.filter(
        date=today,
        status__in=[EmployeeAttendance.ATTENDANCE_PRESENT, EmployeeAttendance.ATTENDANCE_HALF_DAY],
    ).count()
    total_revenue = sum((o.grand_total for o in orders), Decimal("0")).quantize(Decimal("0.01"))
    total_expenses = sum((o.total_expenses for o in orders), Decimal("0")).quantize(Decimal("0.01"))
    revenue_today = sum((o.grand_total for o in orders.filter(order_date=today)), Decimal("0")).quantize(
        Decimal("0.01")
    )
    expenses_today = sum(
        (e.total for e in Expense.objects.filter(created_at__date=today)), Decimal("0")
    ).quantize(Decimal("0.01"))
    payroll_this_month = sum(
        (p.net_pay for p in Payroll.objects.filter(pay_period_start__month=today.month, pay_period_start__year=today.year)),
        Decimal("0"),
    ).quantize(Decimal("0.01"))

    monthly_sales = defaultdict(Decimal)
    for order in Order.objects.filter(order_date__year=today.year):
        month_key = order.order_date.strftime("%b")
        monthly_sales[month_key] += order.grand_total

    sales_chart_data = []
    for i in range(5, -1, -1):
        month_date = today.replace(day=1)
        if i > 0:
            month_date = month_date.replace(month=month_date.month - i)
        else:
            month_date = month_date
        month_label = month_date.strftime("%b")
        month_value = monthly_sales.get(month_label, Decimal("0"))
        sales_chart_data.append({"label": month_label, "value": month_value.quantize(Decimal("0.01"))})

    max_sales = max((item["value"] for item in sales_chart_data), default=Decimal("1"))
    for item in sales_chart_data:
        if item["value"] <= 0:
            item["percent"] = 0
        else:
            item["percent"] = (item["value"] / max_sales * 100).quantize(Decimal("0.1"))

    context = {
        "total_orders": orders.count(),
        "in_progress_count": orders.filter(status__in=[Order.STATUS_IN_PROGRESS, Order.STATUS_PENDING]).count(),
        "finished_count": orders.filter(status=Order.STATUS_FINISHED).count(),
        "revenue_today": revenue_today,
        "expenses_today": expenses_today,
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "net_profit": total_revenue - total_expenses,
        "active_employee_count": active_employee_count,
        "today_present_count": today_present_count,
        "payroll_this_month": payroll_this_month,
        "sales_chart_data": sales_chart_data,
        "sales_chart_max": max_sales,
        "orders": orders[:8],
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
def employee_create(request):
    next_url = request.GET.get("next") or request.POST.get("next") or None
    if request.method == "POST":
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save()
            if next_url:
                return redirect(next_url)
            attendance_url = reverse("employee-attendance-create") + f"?employee={employee.pk}"
            return redirect(attendance_url)
    else:
        form = EmployeeForm()
    return render(request, "orders/employee_form.html", {"form": form, "next": next_url})


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
        if form.is_valid():
            form.save()
            return redirect("employee-detail", pk=attendance.employee.pk)
    else:
        form = EmployeeAttendanceForm(instance=attendance)
    return render(request, "orders/employee_attendance_form.html", {"form": form, "attendance": attendance, "editing": True})


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

