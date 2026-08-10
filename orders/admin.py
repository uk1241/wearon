from django.contrib import admin

from .models import Customer, Expense, Fabric, Order, OrderItem, OrderProgress


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


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "category", "quantity", "unit_cost", "total")
    list_filter = ("category",)
    search_fields = ("name", "order__order_number")
