from decimal import Decimal

from django.db import models
from django.urls import reverse
from django.utils import timezone


class Customer(models.Model):
    name = models.CharField(max_length=150)
    company_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Fabric(models.Model):
    UNIT_CHOICES = [
        ("meter", "Meter"),
        ("yard", "Yard"),
        ("piece", "Piece"),
        ("kg", "Kilogram"),
    ]

    name = models.CharField(max_length=150)
    fabric_type = models.CharField(max_length=100, help_text="e.g. Cotton, Silk, Polyester", blank=True)
    color = models.CharField(max_length=50, blank=True)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default="meter")
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.color})" if self.color else self.name


class Order(models.Model):
    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_FINISHED = "finished"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_FINISHED, "Finished"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    PRIORITY_LOW = "low"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_HIGH = "high"

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_HIGH, "High"),
    ]

    PAYMENT_METHOD_BANK = "bank_transfer"
    PAYMENT_METHOD_CHECK = "check"
    PAYMENT_METHOD_CARD = "card"
    PAYMENT_METHOD_ONLINE = "online_payment"
    PAYMENT_METHOD_OTHER = "other"

    PAYMENT_METHOD_CHOICES = [
        ("", "Select payment method"),
        (PAYMENT_METHOD_BANK, "Bank Transfer"),
        (PAYMENT_METHOD_CHECK, "Check"),
        (PAYMENT_METHOD_CARD, "Card"),
        (PAYMENT_METHOD_ONLINE, "Online Payment"),
        (PAYMENT_METHOD_OTHER, "Other"),
    ]

    order_number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_IN_PROGRESS)
    is_paid = models.BooleanField(default=False)
    order_date = models.DateField(default=timezone.localdate)
    expected_delivery_date = models.DateField(null=True, blank=True)
    reference_number = models.CharField("Reference / PO Number", max_length=50, blank=True)
    shipping_address = models.TextField(blank=True, help_text="Leave blank to use customer address")
    assigned_tailor = models.CharField(max_length=100, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    payment_method = models.CharField(
        max_length=30,
        choices=PAYMENT_METHOD_CHOICES,
        blank=True,
        default="",
    )
    payment_method_details = models.CharField(max_length=255, blank=True)
    customer_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_number

    def save(self, *args, **kwargs):
        if not self.order_number:
            last_order = Order.objects.order_by("id").last()
            next_id = (last_order.id + 1) if last_order else 1
            self.order_number = f"ORD-{next_id:04d}"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("order-detail", args=[self.pk])

    @property
    def subtotal(self):
        total = sum((item.subtotal for item in self.items.all()), Decimal("0"))
        return total.quantize(Decimal("0.01"))

    @property
    def discount_amount(self):
        return (self.subtotal * self.discount_percent / Decimal("100")).quantize(Decimal("0.01"))

    @property
    def grand_total(self):
        return self.subtotal - self.discount_amount

    @property
    def amount_due(self):
        due = self.grand_total - self.amount_paid
        if due <= Decimal("0"):
            return Decimal("0.00")
        return due.quantize(Decimal("0.01"))

    @property
    def total_expenses(self):
        total = sum((expense.total for expense in self.expenses.all()), Decimal("0"))
        return total.quantize(Decimal("0.01"))

    @property
    def profit(self):
        return self.grand_total - self.total_expenses

    @property
    def payment_status_label(self):
        if self.amount_paid >= self.grand_total and self.grand_total > Decimal("0"):
            return "Paid"
        if self.amount_paid > Decimal("0"):
            return "Partial"
        return "Unpaid"

    def save(self, *args, **kwargs):
        if not self.order_number:
            last_order = Order.objects.order_by("id").last()
            next_id = (last_order.id + 1) if last_order else 1
            self.order_number = f"ORD-{next_id:04d}"

        created = self.pk is None
        if created:
            super().save(*args, **kwargs)
            return

        if self.grand_total > Decimal("0") and self.amount_paid >= self.grand_total:
            self.is_paid = True
        else:
            self.is_paid = False

        super().save(*args, **kwargs)

    @property
    def profit_margin_percent(self):
        if self.grand_total == 0:
            return Decimal("0")
        return (self.profit / self.grand_total * Decimal("100")).quantize(Decimal("0.1"))


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    fabric = models.ForeignKey(
        Fabric, on_delete=models.SET_NULL, related_name="order_items", null=True, blank=True
    )
    item_name = models.CharField(max_length=150)
    description = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField("Rate", max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.item_name} x {self.quantity}"

    @property
    def subtotal(self):
        return self.quantity * self.unit_price


class Payment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    payer_name = models.CharField(max_length=150, blank=True)
    method = models.CharField(
        max_length=30,
        choices=Order.PAYMENT_METHOD_CHOICES,
        blank=True,
        default="",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        ordering = ["id"]

    def __str__(self):
        label = self.payer_name or "Payment"
        return f"{label} ({self.method}) - {self.amount}"


class OrderProgress(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="progress_steps")
    title = models.CharField(max_length=100)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name_plural = "Order progress steps"

    def __str__(self):
        return f"{self.order.order_number} - {self.title}"


class Expense(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="expenses")
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=50, blank=True, help_text="e.g. Fabric, Thread, Labour")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.name} ({self.order.order_number})"

    @property
    def total(self):
        return self.quantity * self.unit_cost
