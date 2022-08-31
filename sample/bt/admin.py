from django.urls import reverse
from django.utils.html import mark_safe

from django.contrib import admin
from . import models


class ReadOnlyAdmin(admin.ModelAdmin):
    readonly_fields = []

    def get_readonly_fields(self, request, obj=None):
        return list(self.readonly_fields) + \
               [field.name for field in obj._meta.fields] + \
               [field.name for field in obj._meta.many_to_many]


    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class AddressInline(admin.StackedInline):
    model = models.Address


class SubscriptionHistoryInline(admin.TabularInline):
    model = models.SubscriptionHistory


class SubscriptionAddOnInline(admin.TabularInline):
    model = models.SubscriptionAddOn


class SubscriptionDiscountInline(admin.TabularInline):
    model = models.SubscriptionDiscount


@admin.register(models.Customer)
class CustomerAdmin(ReadOnlyAdmin):
    list_display = [
        "email",
        "phone",
    ]
    inlines = [
        AddressInline,
    ]


@admin.register(models.CreditCard)
class CreditCardAdmin(ReadOnlyAdmin):
    list_display = [
        "customer",
        "bin",
        "card_type",
        "expiration_date",
        "expiration_month",
        "expiration_year",
        "masked_number",
    ]


@admin.register(models.Plan)
class PlanAdmin(ReadOnlyAdmin):
    list_display = [
        "name",
        "price",
        "billing_frequency",
    ]


@admin.register(models.Subscription)
class SubscriptionAdmin(ReadOnlyAdmin):
    list_display = [
        "id",
        "payment_method",
        "plan",
        "days_past_due",
        "next_billing_date",
    ]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "description",
                    "status",
                    "price",
                    "customer",
                    "plan",
                    "payment_method",
                    "merchant_account_id",
                    "balance",
                    "never_expires",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
        (
            "Billing",
            {
                "fields": (
                    "billing_day_of_month",
                    "current_billing_cycle",
                    "billing_period_end_date",
                    "billing_period_start_date",
                    "days_past_due",
                    "failure_count",
                    "first_billing_date",
                    "next_billing_date",
                    "number_of_billing_cycles",
                    "paid_through_date",
                ),
            },
        ),
        (
            "Trial",
            {
                "fields": (
                    "trial_duration",
                    "trial_duration_unit",
                    "trial_period",
                ),
            },
        ),
    )
    inlines = [
        SubscriptionAddOnInline,
        SubscriptionDiscountInline,
        SubscriptionHistoryInline,
    ]

    def customer(self, obj):
        customer = obj.payment_method.billing_address.customer
        url = reverse(
            f"admin:{customer._meta.app_label}_{customer._meta.model_name}_change",
            args=[customer.id],
        )
        return mark_safe(f'<a href="{url}">{customer.__str__()}</a>')
