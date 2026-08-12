from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("orders/", views.order_list, name="order-list"),
    path("orders/new/", views.order_form_view, name="order-create"),
    path("orders/<int:pk>/edit/", views.order_form_view, name="order-edit"),
    path("orders/<int:pk>/", views.order_detail, name="order-detail"),
    path("orders/<int:pk>/mark-finished/", views.order_mark_finished, name="order-mark-finished"),
    path("orders/<int:pk>/mark-paid/", views.order_mark_paid, name="order-mark-paid"),
    path("orders/<int:pk>/mark-unpaid/", views.order_mark_unpaid, name="order-mark-unpaid"),
    path("orders/<int:pk>/invoice/", views.order_invoice, name="order-invoice"),
    path("orders/<int:pk>/delete/", views.order_delete, name="order-delete"),
    path("orders/<int:pk>/unfinish/", views.order_mark_unfinished, name="order-mark-unfinished"),
    path("orders/<int:pk>/expenses/", views.expense_management, name="order-expenses"),
    path("customers/", views.customer_list, name="customer-list"),
    path("customers/<int:pk>/", views.customer_detail, name="customer-detail"),
    path("customers/<int:pk>/export/", views.customer_export, name="customer-export"),
    path("orders/<int:pk>/expenses/export/", views.expense_export, name="order-expenses-export"),
    path("expenses/", views.expense_list, name="expense-list"),
    path("reports/", views.reports, name="reports"),
    path("settings/", views.settings_page, name="settings"),
    path("support/", views.support_page, name="support"),
    path("health/", views.health_check, name="health"),
]
