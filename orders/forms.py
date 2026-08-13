from django import forms
from django.forms import inlineformset_factory

from .models import Customer, Employee, EmployeeAttendance, Expense, Order, OrderItem, Payment, Payroll
from .models import Fabric
from django import forms as _forms


class CustomerForm(_forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "phone", "email", "address"]
        widgets = {
            "name": _forms.TextInput(attrs={"placeholder": "Customer name"}),
            "phone": _forms.TextInput(attrs={"placeholder": "Mobile number"}),
            "email": _forms.EmailInput(attrs={"placeholder": "Email address"}),
            "address": _forms.Textarea(attrs={"rows": 2, "placeholder": "Address"}),
        }
from .models import Fabric


class FabricForm(forms.ModelForm):
    class Meta:
        model = Fabric
        fields = ["name", "fabric_type", "color", "unit", "price_per_unit", "stock_quantity"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Product name"}),
            "fabric_type": forms.TextInput(attrs={"placeholder": "Fabric type e.g. Cotton"}),
            "color": forms.TextInput(attrs={"placeholder": "Color"}),
            "unit": forms.Select(),
            "price_per_unit": forms.NumberInput(attrs={"step": "0.01"}),
            "stock_quantity": forms.NumberInput(attrs={"step": "0.01"}),
        }


class OrderForm(forms.ModelForm):
    customer_name = forms.CharField(max_length=150, label="Customer Name")
    customer_mobile = forms.CharField(max_length=20, required=False, label="Mobile Number")
    customer_email = forms.EmailField(required=False, label="Email")

    class Meta:
        model = Order
        fields = [
            "order_date",
            "expected_delivery_date",
            "reference_number",
            "shipping_address",
            "assigned_tailor",
            "priority",
            "discount_percent",
            "customer_notes",
            "amount_paid",
        ]
        widgets = {
            "order_date": forms.DateInput(attrs={"type": "date"}),
            "expected_delivery_date": forms.DateInput(attrs={"type": "date"}),
            "reference_number": forms.TextInput(attrs={"placeholder": "e.g. PO-8890"}),
            "shipping_address": forms.Textarea(attrs={"rows": 2, "placeholder": "123 Industrial Estate, Sector 4..."}),
            "assigned_tailor": forms.TextInput(attrs={"placeholder": "e.g. Ramesh Kumar"}),
            "discount_percent": forms.NumberInput(attrs={"step": "0.01", "min": "0", "max": "100"}),
            "amount_paid": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "customer_notes": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Notes to appear on the invoice or order receipt..."}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.customer_id:
            customer = self.instance.customer
            self.fields["customer_name"].initial = customer.name
            self.fields["customer_mobile"].initial = customer.phone
            self.fields["customer_email"].initial = customer.email
        self.fields["customer_name"].widget.attrs.setdefault(
            "placeholder", "Select or type customer name"
        )
        self.fields["customer_name"].widget.attrs.setdefault("list", "customer-options")
        self.fields["customer_mobile"].widget.attrs.setdefault("placeholder", "+91 98765 43210")
        self.fields["customer_email"].widget.attrs.setdefault("placeholder", "contact@example.com")

        # configure amount_paid widget
        self.fields["amount_paid"].widget = _forms.NumberInput(attrs={"step": "0.01", "min": "0"})
        pass

    def save(self, commit=True):
        customer, _ = Customer.objects.get_or_create(name=self.cleaned_data["customer_name"])
        customer.phone = self.cleaned_data.get("customer_mobile", "")
        customer.email = self.cleaned_data.get("customer_email", "")
        shipping_address = self.cleaned_data.get("shipping_address", "")
        if shipping_address:
            customer.address = shipping_address
        customer.save()

        order = super().save(commit=False)
        order.customer = customer
        if commit:
            order.save()
        return order


class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ["item_name", "description", "quantity", "unit_price"]
        widgets = {
            "item_name": forms.TextInput(
                attrs={"placeholder": "Select or type item name...", "class": "item-name"}
            ),
            "description": forms.TextInput(
                attrs={"placeholder": "Add description...", "class": "item-desc"}
            ),
            "quantity": forms.NumberInput(attrs={"step": "0.01", "min": "0", "class": "item-qty"}),
            "unit_price": forms.NumberInput(attrs={"step": "0.01", "min": "0", "class": "item-rate"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item_name"].widget.attrs.setdefault("list", "item-options")


OrderItemFormSet = inlineformset_factory(
    Order, OrderItem, form=OrderItemForm, extra=1, can_delete=True
)


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["payer_name", "method", "amount"]
        widgets = {
            "payer_name": forms.TextInput(
                attrs={"placeholder": "Payer name", "class": "payment-name"}
            ),
            "method": forms.Select(attrs={"class": "payment-method-select"}),
            "amount": forms.NumberInput(
                attrs={"placeholder": "Amount paid", "class": "payment-amount", "step": "0.01", "min": "0"}
            ),
        }


PaymentFormSet = inlineformset_factory(
    Order,
    Payment,
    form=PaymentForm,
    extra=1,
    can_delete=True,
)


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["name", "category", "quantity", "unit_cost"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Expense name", "class": "exp-name"}),
            "category": forms.TextInput(
                attrs={"placeholder": "e.g. Fabric, Thread, Labour", "class": "exp-category"}
            ),
            "quantity": forms.NumberInput(attrs={"step": "0.01", "min": "0", "class": "exp-qty"}),
            "unit_cost": forms.NumberInput(attrs={"step": "0.01", "min": "0", "class": "exp-cost"}),
        }


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "name",
            "department",
            "designation",
            "phone",
            "email",
            "address",
            "joining_date",
            "monthly_salary",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Employee name"}),
            "department": forms.TextInput(attrs={"placeholder": "Department"}),
            "designation": forms.TextInput(attrs={"placeholder": "Designation"}),
            "phone": forms.TextInput(attrs={"placeholder": "Mobile number"}),
            "email": forms.EmailInput(attrs={"placeholder": "Email address"}),
            "address": forms.Textarea(attrs={"rows": 3, "placeholder": "Address"}),
            "joining_date": forms.DateInput(attrs={"type": "date"}),
            "monthly_salary": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "status": forms.Select(),
        }


class EmployeeAttendanceForm(forms.ModelForm):
    class Meta:
        model = EmployeeAttendance
        fields = ["employee", "date", "check_in", "check_out", "status", "work_hours", "remarks"]
        widgets = {
            "employee": forms.Select(),
            "date": forms.DateInput(attrs={"type": "date"}),
            "check_in": forms.TimeInput(attrs={"type": "time"}),
            "check_out": forms.TimeInput(attrs={"type": "time"}),
            "status": forms.Select(),
            "work_hours": forms.NumberInput(attrs={"step": "0.25", "min": "0"}),
            "remarks": forms.TextInput(attrs={"placeholder": "Remarks"}),
        }


class PayrollForm(forms.ModelForm):
    class Meta:
        model = Payroll
        fields = [
            "employee",
            "pay_period_start",
            "pay_period_end",
            "present_days",
            "working_days",
            "basic_salary",
            "allowances",
            "overtime",
            "deductions",
            "net_pay",
            "payment_status",
            "payment_date",
            "notes",
        ]
        widgets = {
            "employee": forms.Select(),
            "pay_period_start": forms.DateInput(attrs={"type": "date"}),
            "pay_period_end": forms.DateInput(attrs={"type": "date"}),
            "present_days": forms.NumberInput(attrs={"min": "0"}),
            "working_days": forms.NumberInput(attrs={"min": "0"}),
            "basic_salary": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "allowances": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "overtime": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "deductions": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "net_pay": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "payment_status": forms.Select(),
            "payment_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Payroll notes"}),
        }


ExpenseFormSet = inlineformset_factory(
    Order, Expense, form=ExpenseForm, extra=1, can_delete=True
)
