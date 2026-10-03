from django.utils import timezone
from .models import PaymentSettings


def get_payment_settings():
    return PaymentSettings.get_active_settings()


def is_free_period():
    settings = get_payment_settings()
    if settings.is_free_period:
        return True
    if settings.free_period_start and settings.free_period_end:
        today = timezone.now().date()
        return settings.free_period_start <= today <= settings.free_period_end
    return False


def get_conversion_cost(page_count):
    if is_free_period():
        return 0
    settings = get_payment_settings()
    return float(settings.conversion_cost_per_page) * page_count


def get_revision_material_price(material):
    if is_free_period():
        return 0
    if material.is_free:
        return 0
    if material.price and material.price > 0:
        return float(material.price)
    settings = get_payment_settings()
    return float(settings.global_revision_price)


def payment_required_for_conversion():
    return not is_free_period()


def payment_required_for_revision(material):
    if is_free_period():
        return False
    return not material.is_free
