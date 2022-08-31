from django.db import models

from .base import BaseModel, DescriptionModel, NameModel, PriceModel, TimestampModel


class BaseRecurringModel(BaseModel):
    """A abstract used by all recurring models."""

    number_of_billing_cycles = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Specifies the number of billing cycles for the object.",
    )

    class Meta:
        abstract = True


class BaseNonPlanModel(BaseRecurringModel):
    """An abstract used by all but recurring models but Plan."""

    never_expires = models.BooleanField(
        help_text="Whether a billing cycle is set to never expire instead of "
        "running for a specific number of billing cycles.",
    )

    class Meta:
        abstract = True


class BaseModifierModel(BaseNonPlanModel, NameModel):
    """An abstract used by (Subscription)AddOn and (Subscription)Discount."""

    amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="The modifier amount.",
    )

    class Meta:
        abstract = True


class BaseModifierTemplateModel(BaseModifierModel, DescriptionModel):
    """A abstract used by AddOn and Discount."""

    class Meta:
        abstract = True


class AddOn(BaseModifierTemplateModel):
    """Braintree Add On

    See: https://developer.paypal.com/braintree/docs/reference/response/add-on
    """


class Discount(BaseModifierTemplateModel):
    """Braintree Discount

    See: https://developer.paypal.com/braintree/docs/reference/response/discount
    """


class BasePlanSubscriptionModel(DescriptionModel, TimestampModel):
    """A abstract used by Plan and Subscription."""

    billing_day_of_month = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        help_text="The value that specifies the day of the month that the gateway will charge "
        "the subscription on every billing cycle.",
    )

    trial_duration = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="The trial timeframe duration.",
    )

    trial_duration_unit = models.CharField(
        max_length=16,
        blank=True,
        null=True,
        help_text="The trial timeframe duration unit. Specify day or month.",
        choices=(("day", "day"), ("month", "month")),
    )

    trial_period = models.BooleanField(
        default=False,
        help_text="A value indicating whether a subscription should begin with a trial period.",
    )

    class Meta(TimestampModel.Meta):
        abstract = True


class Plan(BasePlanSubscriptionModel, BaseRecurringModel, NameModel, PriceModel):
    """Braintree Plan

    See: https://developer.paypal.com/braintree/docs/reference/response/plan
    """

    DEFAULT_FIELDS_EXCLUDED = ("id", "add_ons", "discounts")

    add_ons = models.ManyToManyField(
        to=AddOn,
        blank=True,
        help_text="The collection of AddOn objects associated with an object.",
    )

    billing_frequency = models.PositiveIntegerField(
        help_text="Specifies the billing interval of the plan in months.",
    )

    discounts = models.ManyToManyField(
        to=Discount,
        blank=True,
        help_text="The collection of Discount objects associated with an object.",
    )
