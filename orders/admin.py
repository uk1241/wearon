from django.contrib import admin

from .models import (
    Customer,
    Employee,
    EmployeeAttendance,
    Expense,
    Fabric,
    Order,
    OrderItem,
    OrderProgress,
    Payroll,
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "company_name", "email", "phone")
    search_fields = ("name", "company_name", "email")


@admin.register(Fabric)
class FabricAdmin(admin.ModelAdmin):
    list_display = ("name", "fabric_type", "color", "unit", "price_per_unit", "stock_quantity")
    list_filter = ("fabric_type", "unit")
    search_fields = ("name", "fabric_type", "color")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


class OrderProgressInline(admin.TabularInline):
    model = OrderProgress
    extra = 0
    readonly_fields = ("created_at",)


class ExpenseInline(admin.TabularInline):
    model = Expense
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "customer", "status", "priority", "order_date", "expected_delivery_date", "grand_total")
    list_filter = ("status", "priority", "order_date")
    search_fields = ("order_number", "customer__name")
    inlines = [OrderItemInline, ExpenseInline, OrderProgressInline]

    def save_model(self, request, obj, form, change):
        is_new = obj.pk is None
        status_changed = change and "status" in form.changed_data
        super().save_model(request, obj, form, change)
        if is_new:
            OrderProgress.objects.create(order=obj, title="Order Created")
        elif status_changed and obj.status == Order.STATUS_FINISHED:
            OrderProgress.objects.create(order=obj, title="Order Finished")


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "name", "department", "designation", "phone", "monthly_salary", "status")
    list_filter = ("status", "department")
    search_fields = ("name", "employee_id", "email", "phone")


@admin.register(EmployeeAttendance)
class EmployeeAttendanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "date", "status", "check_in", "check_out", "work_hours")
    list_filter = ("status", "date")
    search_fields = ("employee__name", "remarks")


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ("employee", "pay_period_start", "pay_period_end", "present_days", "basic_salary", "net_pay", "payment_status")
    list_filter = ("payment_status", "pay_period_start")
    search_fields = ("employee__name", "notes")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "category", "quantity", "unit_cost", "total")
    list_filter = ("category",)
    search_fields = ("name", "order__order_number")
