from rest_framework import viewsets
from rest_framework import permissions

from .models import Customer, CreditCard
from .serializers import CustomerSerializer, PaymentMethodSerializer


class CustomerViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows customers to be viewed or edited.
    """
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]


class PaymentMethodViewSet(viewsets.ModelViewSet):
    queryset = CreditCard.objects.all()
    serializer_class = PaymentMethodSerializer
