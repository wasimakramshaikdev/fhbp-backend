# from rest_framework import serializers
# from apps.availability.models import TimeSlot, SlotStatus

# class AvailabilityCheckRequestSerializer(serializers.Serializer):
#     date = serializers.DateField(required=True)
#     slot = serializers.ChoiceField(choices=TimeSlot.choices, required=True)
#     guest_count = serializers.IntegerField(required=False, min_value=1)
#     has_catering = serializers.BooleanField(required=False, default=False)
#     catering_type = serializers.ChoiceField(choices=['VEG', 'NON_VEG'], required=False, default='VEG')
#     has_decor = serializers.BooleanField(required=False, default=False)
#     has_dj = serializers.BooleanField(required=False, default=False)


# class SlotBlockRequestSerializer(serializers.Serializer):
#     date = serializers.DateField(required=True)
#     slot = serializers.ChoiceField(choices=TimeSlot.choices, required=True)
#     reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


# class SlotUnblockRequestSerializer(serializers.Serializer):
#     date = serializers.DateField(required=True)
#     slot = serializers.ChoiceField(choices=TimeSlot.choices, required=True)


from rest_framework import serializers

from apps.availability.models import TimeSlot


class AvailabilityCheckRequestSerializer(serializers.Serializer):
    date = serializers.DateField(required=True)
    slot = serializers.ChoiceField(
        choices=TimeSlot.choices,
        required=True,
    )
    guest_count = serializers.IntegerField(
        required=False,
        min_value=1,
    )
    has_catering = serializers.BooleanField(
        required=False,
        default=False,
    )
    catering_type = serializers.ChoiceField(
        choices=[
            ("VEG", "Vegetarian"),
            ("NON_VEG", "Non-Vegetarian"),
        ],
        required=False,
        default="VEG",
    )
    has_decor = serializers.BooleanField(
        required=False,
        default=False,
    )
    has_dj = serializers.BooleanField(
        required=False,
        default=False,
    )


class SlotBlockRequestSerializer(serializers.Serializer):
    date = serializers.DateField(required=True)
    slot = serializers.ChoiceField(
        choices=TimeSlot.choices,
        required=True,
    )
    reason = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )


class SlotUnblockRequestSerializer(serializers.Serializer):
    date = serializers.DateField(required=True)
    slot = serializers.ChoiceField(
        choices=TimeSlot.choices,
        required=True,
    )