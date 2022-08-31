from rest_framework import serializers

from .models import Customer


class CustomerSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Customer
        fields = [fld.name for fld in Customer.DEFAULT_FIELDS] + ['payment_methods']
