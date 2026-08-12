import csv
from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import connection
from django.db.utils import OperationalError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ExpenseFormSet, OrderForm, OrderItemFormSet
from .models import Customer, Expense, Order, OrderItem, OrderProgress

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
    orders = Order.objects.select_related("customer").prefetch_related("items")
    today = date.today()
    status = request.GET.get("status", Order.STATUS_IN_PROGRESS)

    todays_orders = orders.filter(order_date=today)
    revenue_today = sum((o.grand_total for o in todays_orders), Decimal("0"))
    expenses_today = sum(
        (e.total for e in Expense.objects.filter(created_at__date=today)), Decimal("0")
    ).quantize(Decimal("0.01"))

    context = {
        "total_orders": orders.count(),
        "in_progress_count": orders.filter(status__in=[Order.STATUS_IN_PROGRESS, Order.STATUS_PENDING]).count(),
        "finished_count": orders.filter(status=Order.STATUS_FINISHED).count(),
        "revenue_today": revenue_today,
        "expenses_today": expenses_today,
        "net_profit_today": revenue_today - expenses_today,
        "orders": _filter_by_status(orders, status)[:30],
        "active_status": status,
        "status_tabs": ORDER_STATUS_TABS,
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
def order_form_view(request, pk=None):
    order = get_object_or_404(Order, pk=pk) if pk else None
    is_new = order is None

    customers = Customer.objects.order_by("name")
    item_names = (
        OrderItem.objects.order_by("item_name")
        .values_list("item_name", flat=True)
        .distinct()
    )

    if request.method == "POST":
        form = OrderForm(request.POST, instance=order)
        formset = OrderItemFormSet(request.POST, instance=order, prefix="items")
        if form.is_valid() and formset.is_valid():
            order = form.save()
            formset.instance = order
            formset.save()
            if is_new:
                OrderProgress.objects.create(order=order, title="Order Created")
            return redirect("order-detail", pk=order.pk)
    else:
        form = OrderForm(instance=order)
        formset = OrderItemFormSet(instance=order, prefix="items")

    return render(
        request,
        "orders/order_form.html",
        {
            "form": form,
            "formset": formset,
            "order": order,
            "is_new": is_new,
            "customers": customers,
            "item_names": item_names,
        },
    )


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
        order.is_paid = False
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
    return render(request, "orders/customer_detail.html", {"customer": customer})


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
    return render(
        request,
        "orders/customer_export.html",
        {
            "customer": customer,
            "orders": orders,
            "total_revenue": total_revenue,
            "total_expenses": total_expenses,
            "net_profit": net_profit,
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

