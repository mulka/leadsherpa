from django.apps import AppConfig


class BraintreeConfig(AppConfig):
    default = True
    name = "bt"
    verbose_name = "Braintree"

    # def ready(self):
    #     import bt.signals
