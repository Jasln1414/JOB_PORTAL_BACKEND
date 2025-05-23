from rest_framework import serializers
from .models import SubscriptionPlan
import logging

logger = logging.getLogger(__name__)

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ['id', 'name', 'description', 'price', 'duration', 'job_limit']
        read_only_fields = ['id']
        extra_kwargs = {
            'name': {'error_messages': {'invalid': 'Invalid plan name'}},
            'price': {'error_messages': {'invalid': 'Price must be a positive number'}},
            'duration': {'error_messages': {'invalid': 'Duration must be a positive integer'}},
            'job_limit': {'error_messages': {'invalid': 'Job limit must be a positive integer'}}
        }

    def validate_name(self, value):
        valid_names = ['basic', 'standard', 'premium']  # Lowercase only
        if value.lower() not in valid_names:
            raise serializers.ValidationError(
                f"Invalid plan name. Must be one of: {', '.join(valid_names)}"
            )
        return value.lower()

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0")
        return round(value, 2)

    def validate_duration(self, value):
        if value <= 0:
            raise serializers.ValidationError("Duration must be greater than 0")
        return value

    def validate_job_limit(self, value):
        if value <= 0:
            raise serializers.ValidationError("Job limit must be greater than 0")
        return value