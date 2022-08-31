from datetime import datetime, time

from django.db import models
from django.utils.timezone import utc

from django.utils.functional import classproperty


class Source:
    API = "api"
    CONTROL_PANEL = "control_panel"
    RECURRING = "recurring"

    choices = (
        (API, API),
        (CONTROL_PANEL, CONTROL_PANEL),
        (RECURRING, RECURRING),
    )


class YesNoUnknown:
    YES = "Yes"
    NO = "No"
    UNKNOWN = "Unknown"

    choices = (
        (YES, YES),
        (NO, NO),
        (UNKNOWN, UNKNOWN),
    )


class DefaultFieldsMixin:

    DEFAULT_FIELDS_EXCLUDED = ()

    @classproperty  # cachedclassproperty desired
    def DEFAULT_FIELDS(cls):
        for fld in cls._meta.get_fields():
            if fld not in cls._meta.related_objects and fld.name not in cls.DEFAULT_FIELDS_EXCLUDED:
                yield fld

    @classmethod
    def get_default_fields(cls, obj):
        ret = {}
        for fld in cls.DEFAULT_FIELDS:
            value = getattr(obj, fld.name)
            # make times TZ-aware (they are all provided as UTC)
            if value and any(issubclass(type(value), timeclass) for timeclass in (datetime, time)):
                value = value.replace(tzinfo=utc)
            ret[fld.name] = value
        return ret


class BaseModel(DefaultFieldsMixin, models.Model):

    DEFAULT_FIELDS_EXCLUDED = ("id",)

    id = models.CharField(max_length=64, primary_key=True)

    class Meta:
        abstract = True


class DescriptionModel(models.Model):

    description = models.TextField(
        blank=True,
        null=True,
        help_text="A description of the object.",
    )

    class Meta:
        abstract = True


class NameModel(models.Model):

    name = models.CharField(
        max_length=64,
        help_text="The name of the object.",
    )

    class Meta:
        abstract = True


class PriceModel(models.Model):

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="The base price of the object.",
    )

    class Meta:
        abstract = True


class QuantityModel(models.Model):

    quantity = models.PositiveIntegerField(
        help_text="The number of times this object is leveraged.",
    )

    class Meta:
        abstract = True


class TimestampModel(DefaultFieldsMixin, models.Model):
    """Common model, sorted by creation date, most recent first."""

    created_at = models.DateTimeField(
        help_text="The date/time the object was created. Returned in UTC.",
    )

    updated_at = models.DateTimeField(
        help_text="The date/time the object was updated. Returned in UTC.",
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]
