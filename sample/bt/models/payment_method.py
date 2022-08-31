import logging
from django.db import models

from ..bt_gateway import get_braintree_gateway
from .base import TimestampModel, YesNoUnknown
from .customer import Address, Customer

logger = logging.getLogger(__name__)


class BasePaymentMethodModel(TimestampModel):
    """Technically this is a concrete model from which others should inherit, but for performance
    and efficiency will leave abstract for now and use in one-and-only model of interest.
    """

    customer = models.ForeignKey(
        to=Customer,
        on_delete=models.CASCADE,
        help_text="An existing customer in your Vault associated with this payment method.",
        related_name="payment_methods",
    )

    token = models.CharField(
        max_length=10,
        primary_key=True,
        help_text="An alphanumeric value that references a specific payment method stored in your "
        "Vault.",
    )

    class Meta(TimestampModel.Meta):
        abstract = True


class CreditCardManager(models.Manager):
    def update_or_create_from_remote_object(self, remote_obj):

        customer = Customer.objects.get_or_sync(
            id=remote_obj.customer_id,
        )

        billing_address = None
        if remote_obj.billing_address:
            billing_address, _ = Address.objects.update_or_create_from_remote_object(
                remote_obj.billing_address,
            )
        else:
            logger.warning(f"no address for CC for customer {remote_obj.customer_id}")

        return CreditCard.objects.update_or_create(
            token=remote_obj.token,
            defaults=dict(
                billing_address=billing_address,
                customer_id=customer.id,
                **CreditCard.get_default_fields(remote_obj),
            ),
        )

    def update_or_create_from_sync(self, token):
        gateway = get_braintree_gateway()
        bt_credit_card = gateway.credit_card.find(token)
        return self.update_or_create_from_remote_object(bt_credit_card)

    def get_or_sync(self, token):
        try:
            obj = self.get(token=token)
        except self.model.DoesNotExist:
            obj, _ = self.update_or_create_from_sync(token)
        return obj


class CreditCard(BasePaymentMethodModel):

    DEFAULT_FIELDS_EXCLUDED = ("id", "billing_address", "customer", "token")

    objects = CreditCardManager()

    class CardFlag:
        MASTER_FAILED = "00"
        MASTER_ATTEMPTED = "01"
        MASTER_SUCCESS = "02"
        MASTER_DATAONLY = "04"
        FAILED = "07"
        ATTEMPTED = "06"
        SUCCESS = "05"

        choices = (
            (MASTER_FAILED, MASTER_FAILED),
            (MASTER_ATTEMPTED, MASTER_ATTEMPTED),
            (MASTER_SUCCESS, MASTER_SUCCESS),
            (MASTER_DATAONLY, MASTER_DATAONLY),
            (FAILED, FAILED),
            (ATTEMPTED, ATTEMPTED),
            (SUCCESS, SUCCESS),
        )

    billing_address = models.ForeignKey(
        to=Address,
        on_delete=models.CASCADE,
        help_text="The billing Address associated with this credit card.",
        related_name="credit_cards",
        null=True,
    )

    bin = models.CharField(
        max_length=6,
        help_text="The first 6 digits of the credit card, known as the bank identification "
        "number (BIN).",
    )

    card_type = models.CharField(
        max_length=32,
        help_text="The type of the credit card.",
    )

    cardholder_name = models.CharField(
        max_length=175,
        null=True,
        help_text="The cardholder name associated with the credit card.",
    )

    commercial = models.CharField(
        max_length=8,
        choices=YesNoUnknown.choices,
        help_text="Whether the card type is a commercial card and is capable of processing "
        "Level 2 transactions.",
    )

    country_of_issuance = models.CharField(
        max_length=8,
        help_text="The country that issued the credit card. Possible country values follow "
        "ISO 3166-1.",
    )

    # created_at (timestamp)

    # customer (base payment)

    customer_location = models.CharField(
        max_length=14,
        help_text='This is "US" if the billing address is in the US or if a country is not '
        'specified. The location is "International" if the billing country passed is not the US.',
        choices=(("US", "US"), ("International", "International")),
    )

    debit = models.CharField(
        max_length=8,
        choices=YesNoUnknown.choices,
        help_text="Whether the card is a debit card.",
    )

    default = models.BooleanField(
        help_text="Whether the card is the default for the customer.",
        default=False,
    )

    # durbin_regulated (skipped)

    expiration_date = models.CharField(
        max_length=7,
        help_text="The expiration date, formatted MM/YY or MM/YYYY. May be used instead of "
        "expiration month and expiration year.",
    )

    expiration_month = models.CharField(
        max_length=7,
        help_text="The expiration month of a credit card, formatted MM. May be used with "
        "expiration year, and instead of expiration date.",
    )

    expiration_year = models.CharField(
        max_length=7,
        help_text="The two or four digit year associated with a credit card, formatted YYYY "
        "or YY. May be used with expiration month, and instead of expiration date.",
    )

    expired = models.BooleanField(
        help_text="Whether the card is expired.",
        default=False,
    )

    healthcare = models.CharField(
        max_length=8,
        choices=YesNoUnknown.choices,
        help_text="Whether the card is a healthcare card.",
    )

    image_url = models.URLField(
        help_text="A URL that points to a payment method image resource (a PNG file) hosted by "
        "Braintree.",
    )

    issuing_bank = models.CharField(
        max_length=120,
        help_text="The bank that issued the credit card.",
    )

    last_4 = models.CharField(
        max_length=4,
        help_text="The last 4 digits of the credit card number.",
    )

    masked_number = models.CharField(
        max_length=19,
        help_text="A value comprising the bank identification number (BIN), 6 asterisks blocking "
        "out the middle numbers (regardless of the number of digits present), and the last 4 "
        "digits of the card number. This complies with PCI security standards.",
    )

    payroll = models.CharField(
        max_length=8,
        choices=YesNoUnknown.choices,
        help_text="Whether the card is a payroll card.",
    )

    prepaid = models.CharField(
        max_length=8,
        choices=YesNoUnknown.choices,
        help_text="Whether the card is a prepaid card.",
    )

    # product_id (skipped)

    # subscriptions - reverse of FK

    token = models.CharField(
        max_length=36,
        help_text="An alphanumeric value that references a specific payment method "
        "stored in your Vault.",
    )

    unique_number_identifier = models.CharField(
        max_length=50,
        help_text="A randomly-generated string that uniquely identifies a credit card number in "
        "the Vault. If the same credit card is added to a merchant's Vault multiple times, each "
        "Vault entry will have the same unique identifier. This value is randomly generated by "
        "merchant gateway account, so it will be different for each merchant's Vault.",
    )

    # updated_at (timestamp)

    # verification (skipped)
