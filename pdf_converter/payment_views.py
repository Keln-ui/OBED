from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import ConvertedFile, Payment
import json
import logging
import uuid
import time

logger = logging.getLogger(__name__)

# IntaSend Configuration
INTASEND_CONFIG = {
    'publishable_key': getattr(settings, 'INTASEND_PUBLISHABLE_KEY', ''),
    'secret_key': getattr(settings, 'INTASEND_SECRET_KEY', ''),
    'callback_url': getattr(settings, 'INTASEND_CALLBACK_URL', ''),
    'environment': getattr(settings, 'INTASEND_ENVIRONMENT', 'sandbox'),
}

INTASEND_ENABLED = bool(INTASEND_CONFIG['publishable_key'] and INTASEND_CONFIG['secret_key'])

def get_intasend_base_url():
    """Get IntaSend API base URL based on environment"""
    if INTASEND_CONFIG['environment'] == 'production':
        return 'https://api.intasend.com/v1'
    return 'https://sandbox.intasend.com/v1'


def initiate_intasend_payment(phone_number, amount, conversion):
    """Initiate IntaSend M-Pesa payment"""
    if not INTASEND_ENABLED:
        return {'success': False, 'error': 'IntaSend is not configured.'}
    
    try:
        import requests
        
        url = f"{get_intasend_base_url()}/payment/mpesa-pay/"
        
        headers = {
            'Authorization': f'Bearer {INTASEND_CONFIG["secret_key"]}',
            'Content-Type': 'application/json',
        }
        
        payload = {
            'phone_number': phone_number,
            'amount': float(amount),
            'currency': 'KES',
            'api_ref': f'CONV-{conversion.id}',
            'callback_url': INTASEND_CONFIG['callback_url'],
            'customer_name': conversion.user.username if conversion.user else 'Guest',
            'customer_email': conversion.user.email if conversion.user and conversion.user.email else '',
            'transaction_description': f'PDF to Word conversion - {conversion.page_count} pages'
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code in [200, 201]:
            data = response.json()
            return {
                'success': True,
                'transaction_id': data.get('id'),
                'invoice_id': data.get('invoice', {}).get('invoice_id'),
            }
        else:
            return {'success': False, 'error': f'HTTP {response.status_code}: {response.text}'}
            
    except Exception as e:
        logger.error(f"Error initiating IntaSend payment: {str(e)}")
        return {'success': False, 'error': str(e)}


def payment_page(request, conversion_id):
    """Display payment page for a conversion"""
    conversion = get_object_or_404(ConvertedFile, id=conversion_id)
    
    if conversion.payment_status == 'paid':
        return render(request, 'payment/already_paid.html', {'conversion': conversion})
    
    context = {
        'conversion': conversion,
        'page_count': conversion.page_count,
        'cost_per_page': 2.00,
        'total_cost': conversion.cost,
        'intasend_enabled': INTASEND_ENABLED,
    }
    return render(request, 'payment/payment.html', context)


@csrf_exempt
def initiate_payment(request):
    """Initiate IntaSend payment"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        conversion_id = data.get('conversion_id')
        phone_number = data.get('phone_number')
        
        if not conversion_id or not phone_number:
            return JsonResponse({'error': 'Missing required fields'}, status=400)
        
        conversion = get_object_or_404(ConvertedFile, id=conversion_id)
        
        if conversion.payment_status == 'paid':
            return JsonResponse({'error': 'Payment already completed'}, status=400)
        
        # Create payment record
        payment = Payment.objects.create(
            conversion=conversion,
            amount=conversion.cost,
            phone_number=phone_number,
            status='pending'
        )
        
        if not INTASEND_ENABLED:
            # Demo mode: simulate successful payment
            payment.status = 'completed'
            payment.mpesa_receipt = f'DEMO-{uuid.uuid4().hex[:8].upper()}'
            payment.save()
            
            conversion.payment_status = 'paid'
            conversion.mpesa_receipt = payment.mpesa_receipt
            conversion.save()
            
            logger.info(f"Demo payment {payment.id} completed (IntaSend not configured)")
            
            return JsonResponse({
                'success': True,
                'payment_id': payment.id,
                'demo_mode': True,
                'message': 'Demo mode: Payment simulated successfully. You can now download your file.',
                'redirect_url': f'/payment/success/{conversion.id}/'
            })
        
        # Initiate IntaSend Payment
        result = initiate_intasend_payment(
            phone_number=phone_number,
            amount=conversion.cost,
            conversion=conversion
        )
        
        if result.get('success'):
            payment.transaction_id = result.get('transaction_id')
            try:
                payment.save()
            except Exception:
                pass
            
            return JsonResponse({
                'success': True,
                'payment_id': payment.id,
                'transaction_id': result.get('transaction_id'),
                'message': 'Payment initiated. Please check your phone to complete the transaction.'
            })
        else:
            payment.status = 'failed'
            payment.save()
            return JsonResponse({'error': result.get('error', 'Payment initiation failed')}, status=500)
            
    except Exception as e:
        logger.error(f"Error initiating payment: {str(e)}")
        import traceback
        return JsonResponse({'error': f'Error: {str(e)} - {traceback.format_exc()}'}, status=500)


@csrf_exempt
def intasend_callback(request):
    """Handle IntaSend callback"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        logger.info(f"IntaSend callback received: {json.dumps(data)}")
        
        # IntaSend sends status in the payload
        transaction_id = data.get('id') or data.get('transaction_id')
        status = data.get('status', '').lower()
        mpesa_receipt = data.get('receipt_number') or data.get('invoice', {}).get('invoice_id')
        
        # Find payment by transaction ID
        try:
            payment = Payment.objects.get(transaction_id=transaction_id)
        except Payment.DoesNotExist:
            logger.warning(f"Payment not found for IntaSend transaction: {transaction_id}")
            return JsonResponse({'error': 'Payment not found'}, status=404)
        
        if status == 'success' or data.get('success'):
            # Payment successful
            payment.status = 'completed'
            payment.mpesa_receipt = mpesa_receipt or f'INSTASEND-{transaction_id}'
            payment.save()
            
            # Update conversion status
            conversion = payment.conversion
            conversion.payment_status = 'paid'
            conversion.mpesa_receipt = payment.mpesa_receipt
            conversion.save()
            
            logger.info(f"Payment {payment.id} completed successfully via IntaSend")
        else:
            # Payment failed
            payment.status = 'failed'
            payment.save()
            logger.warning(f"Payment {payment.id} failed via IntaSend: {status}")
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Error processing IntaSend callback: {str(e)}")
        return JsonResponse({'error': 'Callback processing failed'}, status=500)


def check_intasend_payment_status(transaction_id):
    """Check IntaSend payment status via API"""
    if not INTASEND_ENABLED:
        return None
    
    try:
        import requests
        url = f"{get_intasend_base_url()}/payment/status/{transaction_id}/"
        headers = {
            'Authorization': f'Bearer {INTASEND_CONFIG["secret_key"]}',
            'Content-Type': 'application/json',
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        logger.error(f"Error checking IntaSend payment status: {str(e)}")
        return None


def payment_status(request, payment_id):
    """Check payment status"""
    try:
        payment = get_object_or_404(Payment, id=payment_id)
        
        return JsonResponse({
            'status': payment.status,
            'amount': float(payment.amount),
            'mpesa_receipt': payment.mpesa_receipt,
            'conversion_id': payment.conversion.id,
        })
    except Exception as e:
        logger.error(f"Error checking payment status: {str(e)}")
        return JsonResponse({'error': 'Failed to check payment status'}, status=500)


def payment_success(request, conversion_id):
    """Payment success page"""
    conversion = get_object_or_404(ConvertedFile, id=conversion_id)
    
    if conversion.payment_status != 'paid':
        return render(request, 'payment/failed.html', {
            'conversion': conversion,
            'error': 'Payment not completed'
        })
    
    # Check if converted file exists
    has_file = bool(conversion.converted_file)
    
    return render(request, 'payment/success.html', {
        'conversion': conversion,
        'has_file': has_file
    })


def payment_failed(request, conversion_id):
    """Payment failed page"""
    conversion = get_object_or_404(ConvertedFile, id=conversion_id)
    return render(request, 'payment/failed.html', {'conversion': conversion})


# Keep for backwards compatibility
mpesa_callback = intasend_callback
