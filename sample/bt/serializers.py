from rest_framework import serializers

from .models import Customer, CreditCard


class CustomerSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Customer
        fields = ['url'] + [fld.name for fld in Customer.DEFAULT_FIELDS] + ['payment_methods']


class PaymentMethodSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = CreditCard
        fields = ['customer'] + [fld.name for fld in CreditCard.DEFAULT_FIELDS]
