from typing import Union

import sentry_sdk

from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from core.logging import get_logger
from integrations.braintree.client import get_braintree_gateway
from .base import PriceModel, QuantityModel, Source
from .payment_method import CreditCard
from .plan import (
    AddOn,
    BaseModifierModel,
    BaseNonPlanModel,
    BasePlanSubscriptionModel,
    Discount,
    Plan,
)

logger = get_logger(__name__)


class SubscriptionStatus:
    ACTIVE = "Active"
    CANCELED = "Canceled"
    EXPIRED = "Expired"
    PAST_DUE = "PastDue"
    PENDING = "Pending"

    choices = (
        (ACTIVE, ACTIVE),
        (CANCELED, CANCELED),
        (EXPIRED, EXPIRED),
        (PAST_DUE, PAST_DUE),
        (PENDING, PENDING),
    )


class BaseRecurringInstanceModel(models.Model):
    """A abstract used by Subscription, SubscriptionAddOn, and SubscriptionDiscount."""

    current_billing_cycle = models.PositiveIntegerField(
        help_text="The object's current billing cycle. It is incremented each time the object "
        "is successfully billed or applied.",
    )

    class Meta:
        abstract = True


class BaseModifierInstanceModel(BaseModifierModel, BaseRecurringInstanceModel, QuantityModel):
    """A abstract used by SubscriptionAddOn and SubscriptionDiscount."""

    id = models.AutoField(primary_key=True)
    subscription = models.ForeignKey(to="Subscription", on_delete=models.CASCADE)

    class Meta:
        abstract = True


class SubscriptionAddOn(BaseModifierInstanceModel):
    """Braintree Add On

    See: https://developer.paypal.com/braintree/docs/reference/response/add-on
    """

    subscription = models.ForeignKey(
        to="Subscription", on_delete=models.CASCADE, related_name="subscription_add_ons"
    )
    add_on = models.ForeignKey(
        to=AddOn, on_delete=models.CASCADE, related_name="subscription_add_ons"
    )


class SubscriptionDiscount(BaseModifierInstanceModel):
    """Braintree Discount

    See: https://developer.paypal.com/braintree/docs/reference/response/discount
    """

    subscription = models.ForeignKey(
        to="Subscription", on_delete=models.CASCADE, related_name="subscription_discounts"
    )
    discount = models.ForeignKey(
        to=Discount, on_delete=models.CASCADE, related_name="subscription_discounts"
    )


class BaseSubscriptionStatusModel(PriceModel):

    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="The balance of the subscription.",
    )

    status = models.CharField(
        max_length=32,
        choices=SubscriptionStatus.choices,
        help_text="The subscription status.",
    )

    class Meta:
        abstract = True


class SubscriptionManager(models.Manager):
    def update_or_create_from_remote_object(self, remote_obj):
        credit_card = CreditCard.objects.get_or_sync(
            token=remote_obj.payment_method_token,
        )

        try:
            instance, updated = self.update_or_create(
                id=remote_obj.id,
                defaults=dict(
                    payment_method=credit_card,
                    plan=Plan.objects.get(id=remote_obj.plan_id),
                    **Subscription.get_default_fields(remote_obj),
                ),
            )
            for subscription_modifiers, modifier_manager, related_id in (
                (remote_obj.add_ons, instance.subscription_add_ons, "add_on_id"),
                (remote_obj.discounts, instance.subscription_discounts, "discount_id"),
            ):
                for modifier in subscription_modifiers:
                    modifier_manager.update_or_create(
                        **{related_id: modifier.id},
                        defaults=dict(
                            amount=modifier.amount,
                            current_billing_cycle=modifier.current_billing_cycle,
                            name=modifier.name,
                            never_expires=modifier.never_expires,
                            number_of_billing_cycles=modifier.number_of_billing_cycles,
                            quantity=modifier.quantity,
                        ),
                    )
            return instance, updated
        except Exception:
            logger.exception(f"error syncing {remote_obj.id}")

    def update_or_create_from_sync(self, subscription_ids):
        # todo: add SubscriptionHistory
        gateway = get_braintree_gateway()
        bt_subscriptions = gateway.get_subscriptions_by_id(subscription_ids)
        logger.info(f"Sync {len(bt_subscriptions.ids)} Subscriptions")
        for bt_subscription in bt_subscriptions:
            self.update_or_create_from_remote_object(bt_subscription)


class Subscription(
    BaseRecurringInstanceModel,
    BaseNonPlanModel,
    BasePlanSubscriptionModel,
    BaseSubscriptionStatusModel,
):
    """Braintree Subscription

    See: https://developer.paypal.com/braintree/docs/reference/response/subscription
    """

    DEFAULT_FIELDS_EXCLUDED = ("id", "add_ons", "discounts", "payment_method", "plan")

    objects = SubscriptionManager()

    add_ons = models.ManyToManyField(
        to=AddOn,
        through=SubscriptionAddOn,
        related_name="subscriptions",
        blank=True,
        help_text="The collection of AddOn objects associated with an object.",
    )

    # balance (status model)

    billing_period_end_date = models.DateField(
        help_text="The end date for the current billing period, regardless of subscription "
        "status. Automatic retries on past due subscriptions do not change the start and end "
        "dates of the current billing period.",
    )

    billing_period_start_date = models.DateField(
        help_text="The start date for the current billing period, regardless of subscription "
        "status. Automatic retries on past due subscriptions do not change the start and end "
        "dates of the current billing period.",
    )

    days_past_due = models.IntegerField(
        null=True,
        help_text="The number of days that the subscription is past due. Read more about the "
        "past due status in the Recurring Billing guide.",
    )

    discounts = models.ManyToManyField(
        to=Discount,
        through=SubscriptionDiscount,
        related_name="subscriptions",
        blank=True,
        help_text="The collection of Discount objects associated with an object.",
    )

    failure_count = models.IntegerField(
        help_text="The number of consecutive failed attempts by our recurring billing engine to "
        "charge a subscription. This count includes the transaction attempt that caused the "
        "subscription's status to become past due, starting at 0 and increasing for each failed "
        "attempt. If the subscription is active and no charge attempts failed, the count is 0.",
    )

    first_billing_date = models.DateField(
        help_text="The day the subscription starts billing.",
    )

    merchant_account_id = models.CharField(
        max_length=256,
        help_text="The merchant account ID used for the subscription. Currency is also determined "
        "by merchant account ID.",
    )

    # next_bill_amount (deprecated)

    next_billing_date = models.DateField(
        help_text="The date that the gateway will try to bill the subscription again. The gateway "
        "adjusts this date each time it tries to charge the subscription. If the subscription is "
        "past due and you have set your processing options to automatically retry failed "
        "transactions, the gateway will continue to adjust this date, advancing it based on the "
        "settings that you configured in advanced settings.",
    )

    next_billing_period_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="The total subscription amount for the next billing period. This amount "
        "includes add-ons and discounts but does not include the current balance.",
    )

    paid_through_date = models.DateField(
        help_text="The date through which the subscription has been paid. It is the "
        "billing_period_end_date at the time of the last successful transaction. If the "
        "subscription is pending (has a future start date), this field is None.",
    )

    payment_method = models.ForeignKey(
        to=CreditCard,
        on_delete=models.PROTECT,
        help_text="An alphanumeric value that references a specific payment method stored in "
        "your Vault.",
        related_name="subscriptions",
        null=True,
    )

    plan = models.ForeignKey(
        to=Plan,
        on_delete=models.PROTECT,
        help_text="The plan identifier.",
        related_name="subscriptions",
    )

    def _subscription_gateway(self):
        gateway = get_braintree_gateway()
        try:
            return gateway.subscription.find(self.id)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return None

    def _update_subscription(self, payload) -> None:
        subscription = self._subscription_gateway()
        if subscription:
            gateway = get_braintree_gateway()
            gateway.subscription.update(self.id, payload)

    def cancel(self):
        gateway = get_braintree_gateway()
        return gateway.subscription.cancel(self.id)

    def add_on_quantity(self, add_on: AddOn) -> int:
        try:
            return self.subscription_add_ons.get(add_on=add_on).quantity
        except ObjectDoesNotExist:
            return 0

    def discount_quantity(self, discount: Discount) -> int:
        try:
            return self.subscription_discounts.get(discount=discount).quantity
        except ObjectDoesNotExist:
            return 0

    def has_add_on(self, add_on: AddOn) -> bool:
        return self.add_on_quantity(add_on=add_on) > 0

    def has_discount(self, discount: Discount) -> bool:
        return self.discount_quantity(discount=discount) > 0

    def set_add_on(self, add_on: AddOn, quantity: int) -> None:
        self._set_item(item=add_on, quantity=quantity)

    def set_discount(self, discount: Discount, quantity: int) -> None:
        self._set_item(item=discount, quantity=quantity)

    def _set_item(self, item: Union[AddOn, Discount], quantity: int) -> None:
        if isinstance(item, AddOn):
            checker = self.has_add_on(add_on=item)
            item_key = "add_on"
            getter = self.subscription_add_ons
            creator = SubscriptionAddOn
        else:
            checker = self.has_discount(discount=item)
            item_key = "discount"
            getter = self.subscription_discounts
            creator = SubscriptionDiscount

        mod_str = "add"
        id_str = "inherited_from_id"
        if checker:
            mod_str = "update"
            id_str = "existing_id"

        self._update_subscription(
            {
                f"{item_key}s": {
                    mod_str: [
                        {
                            id_str: item.id,
                            "quantity": quantity,
                        }
                    ],
                },
            }
        )

        if mod_str == "update":
            sub_item = getter.get(**{item_key: item})
            sub_item.quantity = quantity
            sub_item.save()
        else:
            creator.objects.create(
                subscription=self,
                quantity=quantity,
                current_billing_cycle=self.current_billing_cycle,
                never_expires=True,
                **{
                    item_key: item,
                    "amount": item.amount,
                },
            )

    def remove_add_on(self, add_on: AddOn) -> None:
        if not self.has_add_on(add_on=add_on):
            sentry_sdk.capture_message(
                f"Subscription {self.id} does not have add on: {add_on.id}",
            )
            return

        payload = {"add_ons": {"remove": [add_on.id]}}
        self._update_subscription(payload=payload)
        sub_add_on = self.subscription_add_ons.get(add_on=add_on)
        sub_add_on.delete()

    def remove_discount(self, discount: Discount) -> None:
        if not self.has_discount(discount=discount):
            sentry_sdk.capture_message(
                f"Subscription {self.id} does not have discount: {discount.id}",
            )
            return

        payload = {"discounts": {"remove": [discount.id]}}
        self._update_subscription(payload=payload)
        sub_discount = self.subscription_discounts.get(discount=discount)
        sub_discount.delete()


class SubscriptionHistory(BaseSubscriptionStatusModel):

    subscription_source = models.CharField(
        max_length=32,
        choices=Source.choices,
        help_text="Where the subscription event was created.",
    )

    subscription = models.ForeignKey(
        to=Subscription,
        on_delete=models.CASCADE,
        related_name="status_history",
    )

    timestamp = models.DateTimeField(
        help_text="The date/time of the event. Returned in UTC.",
    )
