from django.urls import path
from . import payment_views

urlpatterns = [
    path('<int:conversion_id>/', payment_views.payment_page, name='payment_page'),
    path('initiate/', payment_views.initiate_payment, name='initiate_payment'),
    path('callback/', payment_views.mpesa_callback, name='mpesa_callback'),
    path('intasend/callback/', payment_views.intasend_callback, name='intasend_callback'),
    path('status/<int:payment_id>/', payment_views.payment_status, name='payment_status'),
    path('success/<int:conversion_id>/', payment_views.payment_success, name='payment_success'),
    path('failed/<int:conversion_id>/', payment_views.payment_failed, name='payment_failed'),
]
