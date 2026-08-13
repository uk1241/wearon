from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Employee, EmployeeAttendance, Payroll


class EmployeePayrollPersistenceTests(TestCase):
    def test_employee_attendance_and_payroll_are_saved(self):
        employee = Employee.objects.create(
            name="Asha Verma",
            employee_id="EMP-1001",
            department="Cutting",
            designation="Tailor",
            phone="9876543210",
            email="asha@example.com",
            monthly_salary=Decimal("25000.00"),
            address="Bengaluru",
        )

        attendance = EmployeeAttendance.objects.create(
            employee=employee,
            date=date(2026, 8, 1),
            check_in="09:00",
            check_out="18:00",
            status="present",
            work_hours=Decimal("9.00"),
            remarks="On time",
        )

        payroll = Payroll.objects.create(
            employee=employee,
            pay_period_start=date(2026, 8, 1),
            pay_period_end=date(2026, 8, 31),
            present_days=22,
            working_days=30,
            basic_salary=Decimal("25000.00"),
            allowances=Decimal("1500.00"),
            overtime=Decimal("1200.00"),
            deductions=Decimal("500.00"),
            net_pay=Decimal("27200.00"),
            payment_status="pending",
            notes="Monthly payroll",
        )

        self.assertEqual(Employee.objects.count(), 1)
        self.assertEqual(EmployeeAttendance.objects.count(), 1)
        self.assertEqual(Payroll.objects.count(), 1)
        self.assertEqual(attendance.employee, employee)
        self.assertEqual(payroll.employee, employee)
        self.assertEqual(payroll.net_pay, Decimal("27200.00"))

    def test_employee_attendance_edit_page_is_available(self):
        employee = Employee.objects.create(
            name="Ravi Kumar",
            employee_id="EMP-2001",
            department="Sewing",
            designation="Operator",
            phone="9123456789",
            email="ravi@example.com",
            monthly_salary=Decimal("18000.00"),
            address="Coimbatore",
        )
        attendance = EmployeeAttendance.objects.create(
            employee=employee,
            date=date(2026, 8, 12),
            check_in="09:15",
            status="present",
            work_hours=Decimal("0.00"),
        )
        user = get_user_model().objects.create_user(username="admin", password="secret123")
        self.client.force_login(user)

        response = self.client.get(reverse("employee-attendance-edit", args=[attendance.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Check Out")
